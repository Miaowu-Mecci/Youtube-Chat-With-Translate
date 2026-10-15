import { test, expect } from '@playwright/test'

const config = { source: '', target_language: 'zh-Hans', translation_enabled: false,
  style: { font_size: 24, color: '#ffffff', translation_color: '#8de1cb', show_avatar: true, max_messages: 100, custom_css: '' } }

test.beforeEach(async ({ request, page }) => {
  await request.post('/api/disconnect')
  await request.put('/api/config', { data: config })
  await page.route('**/api/languages*', route => {
    const languages = [{ code: 'zh-Hans', name: '简体中文' }, { code: 'ja', name: '日本語' }, { code: 'en', name: 'English' }, { code: 'fr', name: 'Français' }]
    return route.fulfill({ json: { languages } })
  })
})

test('settings preview and standalone overlay share the demo', async ({ page, context }) => {
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '让每一句话，都被听懂。' })).toBeVisible()
  const overlay = await context.newPage()
  await overlay.goto('/overlay')
  await expect(overlay.getByRole('status')).toHaveText('弹幕姬开始工作')
  await page.getByRole('button', { name: '体验演示' }).click()
  const preview = page.frameLocator('iframe')
  const first = preview.locator('[data-message-id="demo-0"]')
  await expect(first.locator('#message')).toContainText('こんにちは')
  await expect(first.locator('.translation')).toContainText('你好！')
  await expect(first).toHaveCount(1)
  await expect(page.locator('.status-pill')).toHaveText('演示中')
  await expect(overlay.locator('[data-message-id="demo-0"] .translation')).toContainText('你好！')
  expect(await overlay.locator('body').evaluate(el => getComputedStyle(el).backgroundColor)).toBe('rgba(0, 0, 0, 0)')
  expect(await overlay.locator('yt-live-chat-renderer').evaluate(el => getComputedStyle(el).backgroundColor)).toBe('rgba(0, 0, 0, 0)')
  await page.screenshot({ path: 'test-results/dashboard.png', fullPage: true })
  await overlay.close()
  expect(errors).toEqual([])
})

test('draft styles update preview and saved styles update OBS', async ({ page, request }) => {
  await page.goto('/')
  await page.getByRole('button', { name: '体验演示' }).click()
  const preview = page.frameLocator('iframe')
  await expect(preview.locator('.translation').first()).toBeVisible()
  await page.locator('#custom-css').fill('yt-live-chat-text-message-renderer { border-left: 3px solid rgb(255, 0, 0); }\n.translation { color: rgb(0, 255, 0); font-weight: 600; }\nyt-live-chat-author-chip #author-name { color: rgb(255, 200, 0); }')
  await expect(preview.locator('.translation').first()).toHaveCSS('color', 'rgb(0, 255, 0)')
  await expect(preview.locator('yt-live-chat-text-message-renderer').first()).toHaveCSS('border-left-width', '3px')
  await expect(preview.locator('#author-name').first()).toHaveCSS('color', 'rgb(255, 200, 0)')
  await page.getByRole('checkbox', { name: '显示头像' }).uncheck()
  await expect(preview.locator('#author-photo').first()).toHaveCSS('display', 'none')
  await page.getByRole('button', { name: '保存设置', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('设置已保存')
  expect((await (await request.get('/api/config')).json()).style.show_avatar).toBe(false)
  await page.goto('/overlay')
  await expect(page.getByRole('status')).toHaveText('弹幕姬开始工作')
  await expect(page.locator('yt-live-chat-text-message-renderer')).toHaveCount(0)
  await request.post('/api/disconnect')
  await request.post('/api/demo')
  await expect(page.locator('.translation').first()).toHaveCSS('color', 'rgb(0, 255, 0)')
})

test('translation events update existing rows and deleted rows stay deleted', async ({ page }) => {
  let socket
  await page.routeWebSocket('**/ws', ws => {
    socket = ws
    ws.send(JSON.stringify({ type: 'snapshot', session: 'test', messages: [], config, status: {} }))
  })
  await page.goto('/overlay')
  await expect.poll(() => Boolean(socket)).toBe(true)
  const message = { id: 'one', author: 'Alice', original: 'Hello', avatar: '', role: 'normal', time: new Date().toISOString(), translation: '' }
  const send = event => socket.send(JSON.stringify({ session: 'test', ...event }))
  send({ type: 'message', message })
  await expect(page.locator('#message')).toHaveText('Hello')
  send({ type: 'translation', id: 'one', translation: '你好' })
  await expect(page.locator('.translation')).toHaveText('你好')
  await expect(page.locator('yt-live-chat-text-message-renderer')).toHaveCount(1)
  const positions = await page.locator('[data-message-id="one"]').evaluate(el => ({ original: el.querySelector('#message').getBoundingClientRect().top, translation: el.querySelector('.translation').getBoundingClientRect().top }))
  expect(positions.translation).toBeGreaterThan(positions.original)
  send({ type: 'delete', ids: ['one'] })
  await expect(page.locator('yt-live-chat-text-message-renderer')).toHaveCount(0)
  send({ type: 'translation', id: 'one', translation: '迟到的译文' })
  await expect(page.locator('yt-live-chat-text-message-renderer')).toHaveCount(0)
})

test('opening and refreshing an overlay skips cached chat independently of other surfaces', async ({ page, context }) => {
  const sockets = []
  const message = id => ({ id, author: 'Alice', original: id, avatar: '', role: 'normal', time: new Date().toISOString(), translations: [] })
  let cached = Array.from({ length: 100 }, (_, i) => message(`history-${i}`))
  await context.routeWebSocket('**/ws', ws => {
    sockets.push(ws)
    ws.send(JSON.stringify({ type: 'snapshot', session: 'fresh-overlay', messages: cached, config, status: {} }))
  })
  const send = (socket, event) => socket.send(JSON.stringify({ session: 'fresh-overlay', ...event }))
  await page.goto('/overlay')
  await expect(page.getByRole('status')).toHaveText('弹幕姬开始工作')
  await expect(page.locator('yt-live-chat-text-message-renderer')).toHaveCount(0)
  const live = message('live-before-refresh')
  send(sockets[0], { type: 'message', message: live })
  await expect(page.locator('#message')).toHaveText(live.original)
  expect(await page.locator('yt-live-chat-item-list-renderer #items').evaluate(el => el.firstElementChild.className)).toContain('overlay-start')
  const second = await context.newPage()
  cached = [...cached, live]
  await second.goto('/overlay')
  await expect(second.getByRole('status')).toHaveText('弹幕姬开始工作')
  await expect(second.locator('yt-live-chat-text-message-renderer')).toHaveCount(0)
  await expect(page.locator('#message')).toHaveText(live.original)
  await page.reload()
  await expect(page.getByRole('status')).toHaveText('弹幕姬开始工作')
  await expect(page.locator('yt-live-chat-text-message-renderer')).toHaveCount(0)
  const current = message('new-after-refresh')
  for (const socket of sockets.slice(1)) {
    send(socket, { type: 'translation', id: live.id, translation: '旧消息的迟到译文' })
    send(socket, { type: 'message', message: current })
    send(socket, { type: 'translation', id: current.id, translations: [{ language: 'zh-Hans', text: '刷新后的新消息', status: 'complete' }] })
  }
  for (const surface of [page, second]) {
    await expect(surface.locator('yt-live-chat-text-message-renderer')).toHaveCount(1)
    await expect(surface.locator('#message')).toHaveText(current.original)
    await expect(surface.locator('.translation')).toHaveText('刷新后的新消息')
    await expect(surface.locator('.overlay-start')).toHaveCount(1)
  }
  await second.close()
})

test('settings snapshots and reconnects update visible chat without replaying history', async ({ page }) => {
  const sockets = []
  const message = id => ({ id, author: 'Alice', original: id, avatar: '', role: 'normal', time: new Date().toISOString(), translations: [] })
  const old = message('old'), live = message('live'), missed = message('missed-while-disconnected')
  const snapshot = (messages, session = 'sync', style = config.style) => ({ type: 'snapshot', session, messages, config: { ...config, style }, status: {} })
  await page.routeWebSocket('**/ws', ws => {
    sockets.push(ws)
    ws.send(JSON.stringify(snapshot(sockets.length === 1 ? [old] : [old, live, missed])))
  })
  await page.goto('/overlay')
  await expect(page.getByRole('status')).toHaveText('弹幕姬开始工作')
  const send = event => sockets.at(-1).send(JSON.stringify({ session: 'sync', ...event }))
  send({ type: 'message', message: live })
  await expect(page.locator('#message')).toHaveText('live')
  const translated = { ...live, translations: [{ language: 'ja', text: 'こんにちは', status: 'complete' }, { language: 'en', text: 'Hello', status: 'complete' }] }
  // Preserve the actual DOM row while applying new style and language order.
  await page.locator('[data-message-id="live"]').evaluate(el => { el.dataset.preserved = 'yes' })
  send(snapshot([old, translated], 'sync', { ...config.style, font_size: 36 }))
  await expect(page.locator('.translation')).toHaveText(['こんにちは', 'Hello'])
  await expect(page.locator('#message')).toHaveCSS('font-size', '36px')
  await expect(page.locator('[data-message-id="live"]')).toHaveAttribute('data-preserved', 'yes')
  send({ type: 'translation', id: old.id, translation: '不应显示' })
  sockets[0].close()
  await expect.poll(() => sockets.length).toBe(2)
  // Reconnection keeps the row already displayed, but skips the disconnected backlog.
  await expect(page.locator('yt-live-chat-text-message-renderer')).toHaveCount(1)
  await expect(page.locator('[data-message-id="live"]')).toHaveAttribute('data-preserved', 'yes')
  send(snapshot([old]))
  await expect(page.locator('yt-live-chat-text-message-renderer')).toHaveCount(0)
  send({ type: 'translation', id: live.id, translation: '已移除的消息' })
  send(snapshot([old], 'another-room'))
  send({ type: 'message', session: 'sync', message: live })
  send({ type: 'message', session: 'another-room', message: message('new-room') })
  await expect(page.locator('#message')).toHaveText('new-room')
  await expect(page.locator('.overlay-start')).toHaveCount(1)
})

test('chat HTML is displayed as text and does not execute', async ({ page }) => {
  let socket
  let dialogs = 0
  page.on('dialog', dialog => { dialogs++; dialog.dismiss() })
  await page.routeWebSocket('**/ws', ws => {
    socket = ws
    ws.send(JSON.stringify({ type: 'snapshot', session: 'test', messages: [], config, status: {} }))
  })
  await page.goto('/overlay')
  await expect.poll(() => Boolean(socket)).toBe(true)
  const text = '<img src=x onerror=alert(1)><script>alert(1)</script>'
  socket.send(JSON.stringify({ type: 'message', session: 'test', message: { id: 'safe', author: '<script>Alice</script>', original: text, avatar: '', time: new Date().toISOString(), role: 'normal', translation: '' } }))
  await expect(page.locator('#message')).toHaveText(text)
  expect(await page.locator('#message img, #message script').count()).toBe(0)
  expect(dialogs).toBe(0)
})

test('dashboard scrolls and stays usable on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await page.locator('#appearance').scrollIntoViewIfNeeded()
  await expect(page.getByRole('button', { name: '保存设置', exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  expect(await page.evaluate(() => scrollY > 0)).toBe(true)
})


test('Google setup saves without keys and diagnostic displays mocked service results', async ({ page, request }) => {
  let tested = false
  await page.route('**/api/translation/test', async route => {
    const saved = await (await request.get('/api/config')).json()
    expect(saved).not.toHaveProperty('translation_provider')
    expect(saved.translation_enabled).toBe(true)
    expect(saved).not.toHaveProperty('azure_key')
    tested = true
    return route.fulfill({ json: { original: 'Hello', translation: '你好', source_language: 'en' } })
  })
  await page.goto('/')
  await expect(page.locator('#provider')).toHaveCount(0)
  await expect(page.locator('#azure-key')).toHaveCount(0)
  await expect(page.locator('#translation')).toContainText('Google Translate')
  await page.getByRole('checkbox', { name: '开启翻译' }).check()
  await page.getByRole('button', { name: '保存并测试翻译' }).click()
  await expect(page.getByRole('status', { name: '翻译测试结果' })).toContainText('Hello → 你好')
  expect(tested).toBe(true)
  await expect(page.locator('.status-pill')).toHaveText('未连接')
  await page.route('**/api/translation/test', route => route.fulfill({ status: 503, json: { code: 'cooldown', detail: 'Google 正在限流等待中，请稍后测试。' } }))
  await page.getByRole('button', { name: '保存并测试翻译' }).click()
  await expect(page.getByRole('status', { name: '翻译测试结果' })).toContainText('限流等待')
})

test('successive Japanese translations appear in preview and OBS without duplicate rows', async ({ page, context }) => {
  const sockets = []
  await context.routeWebSocket('**/ws', ws => {
    sockets.push(ws)
    ws.send(JSON.stringify({ type: 'snapshot', session: 'continuous', messages: [], config, status: {} }))
  })
  await page.goto('/')
  const preview = page.frameLocator('iframe')
  const obs = await context.newPage()
  await obs.goto('/overlay')
  await expect.poll(() => sockets.length).toBe(3)
  const send = event => sockets.forEach(ws => ws.send(JSON.stringify({ session: 'continuous', ...event })))
  for (let i = 0; i < 6; i++) {
    send({ type: 'message', message: { id: `continuous-${i}`, author: 'Test', original: `English message ${i}`, avatar: '', role: 'normal', time: new Date().toISOString(), translation: '' } })
  }
  await expect(preview.locator('yt-live-chat-text-message-renderer')).toHaveCount(6)
  await expect(obs.locator('yt-live-chat-text-message-renderer')).toHaveCount(6)
  for (let i = 0; i < 6; i++) {
    send({ type: 'translation', id: `continuous-${i}`, translation: `日本語の翻訳 ${i}` })
    for (const surface of [preview, obs]) {
      await expect(surface.locator(`[data-message-id="continuous-${i}"] .translation`)).toHaveText(`日本語の翻訳 ${i}`)
      await expect(surface.locator(`[data-message-id="continuous-${i}"] #message`)).toHaveText(`English message ${i}`)
    }
  }
  for (const surface of [preview, obs]) await expect(surface.locator('yt-live-chat-text-message-renderer')).toHaveCount(6)
  send({ type: 'delete', ids: ['continuous-1'] })
  for (const surface of [preview, obs]) await expect(surface.locator('[data-message-id="continuous-1"]')).toHaveCount(0)
  send({ type: 'translation', id: 'continuous-1', translation: '遅い翻訳' })
  for (const surface of [preview, obs]) await expect(surface.locator('yt-live-chat-text-message-renderer')).toHaveCount(5)
  send({ type: 'status', status: { connection: 'connected', translation_message: '翻译运行中。', translation_counts: { pending: 2, complete: 3, failed: 1, skipped: 0 } } })
  await expect(page.getByLabel('翻译进度')).toContainText('等待 2 · 已完成 3 · 失败 1')
  await obs.close()
})

test('connect sends the click time before saving settings and explains history filtering', async ({ page }) => {
  let releaseSave, connectionBody
  const sockets = []
  await page.routeWebSocket('**/ws', ws => {
    sockets.push(ws)
    ws.send(JSON.stringify({ type: 'snapshot', session: 'fresh', messages: [], config, status: {} }))
  })
  await page.goto('/')
  await expect(page.getByRole('button', { name: '连接直播间' })).toBeEnabled()
  await page.route('**/api/config', async route => {
    if (route.request().method() !== 'PUT') return route.continue()
    await new Promise(resolve => { releaseSave = resolve })
    await route.continue()
  })
  await page.route('**/api/connect', async route => {
    connectionBody = route.request().postDataJSON()
    await route.fulfill({ json: { connection: 'connecting' } })
  })
  await page.getByRole('button', { name: '连接直播间' }).click()
  await expect.poll(() => Boolean(releaseSave)).toBe(true)
  const beforeSaveCompleted = Date.now()
  releaseSave()
  await expect.poll(() => Boolean(connectionBody)).toBe(true)
  expect(Date.parse(connectionBody.started_at)).toBeLessThanOrEqual(beforeSaveCompleted)
  sockets.forEach(ws => ws.send(JSON.stringify({ type: 'status', session: 'fresh', status: { connection: 'connected', chat_started_at: connectionBody.started_at, ignored_history: 500 } })))
  await expect(page.getByText('仅收录点击「连接直播间」后发布的新弹幕，不显示或翻译此前的历史弹幕。')).toBeVisible()
  await expect(page.getByText('已过滤 500 条历史弹幕；自动重连继续使用本次连接的起点。')).toBeVisible()
})


test('multiple target languages can be added, reordered, saved and restored in demo and OBS', async ({ page, context, request }) => {
  await page.goto('/')
  await expect(page.locator('#youtube-key')).toHaveCount(0)
  await expect(page.locator('.source-options')).toHaveCount(0)
  await expect(page.locator('#source-type')).toHaveCount(0)
  await expect(page.locator('#provider')).toHaveCount(0)
  await page.locator('#language').selectOption('en')
  await page.getByRole('button', { name: '添加', exact: true }).click()
  await expect(page.locator('.language-stack li')).toHaveCount(2)
  await page.getByRole('button', { name: '上移 English', exact: true }).click()
  await expect(page.locator('.language-stack li').first()).toHaveAttribute('data-language', 'en')
  // Native drag-and-drop also works, without making it the only keyboard interaction.
  await page.locator('.language-stack li[data-language="zh-Hans"]').dragTo(page.locator('.language-stack li[data-language="en"]'))
  await expect(page.locator('.language-stack li').first()).toHaveAttribute('data-language', 'zh-Hans')
  await page.getByRole('button', { name: '保存设置', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('设置已保存')
  expect((await (await request.get('/api/config')).json()).target_languages).toEqual(['zh-Hans', 'en'])
  await page.reload()
  await expect(page.locator('.language-stack li')).toHaveCount(2)
  const overlay = await context.newPage()
  await overlay.goto('/overlay')
  await expect(overlay.getByRole('status')).toHaveText('弹幕姬开始工作')
  await page.getByRole('button', { name: '体验演示' }).click()
  const preview = page.frameLocator('iframe')
  await expect(preview.locator('[data-message-id="demo-0"] .translation')).toHaveCount(2)
  await expect(preview.locator('[data-message-id="demo-0"] .translation').nth(1)).toContainText('Hello!')
  await expect(overlay.locator('[data-message-id="demo-0"] .translation')).toHaveCount(2)
  await page.getByRole('button', { name: '上移 English', exact: true }).click()
  await page.getByRole('button', { name: '保存设置', exact: true }).click()
  await expect(overlay.locator('[data-message-id="demo-0"] .translation-row').first()).toHaveAttribute('data-language', 'en')
  await expect(overlay.locator('[data-message-id="demo-0"] .translation').first()).toContainText('Hello!')
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: 'test-results/multilingual-dashboard.png', fullPage: true })
  await overlay.close()
})

test('all target languages can be removed, saved and readded without losing original messages', async ({ page, context, request }) => {
  await page.goto('/')
  await page.getByRole('checkbox', { name: '开启翻译' }).check()
  await page.getByRole('button', { name: '移除 简体中文', exact: true }).click()
  await expect(page.locator('.language-stack li')).toHaveCount(0)
  await expect(page.getByLabel('无目标语言')).toHaveText('未选择翻译语言，仅显示原文。')
  await expect(page.getByRole('button', { name: '保存并测试翻译' })).toBeDisabled()
  await expect(page.getByRole('button', { name: '恢复翻译' })).toBeDisabled()
  await page.getByRole('button', { name: '保存设置', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('设置已保存')
  expect((await (await request.get('/api/config')).json()).target_languages).toEqual([])
  await page.reload()
  await expect(page.getByLabel('无目标语言')).toBeVisible()
  const overlay = await context.newPage()
  await overlay.goto('/overlay')
  await expect(overlay.getByRole('status')).toHaveText('弹幕姬开始工作')
  await page.getByRole('button', { name: '体验演示' }).click()
  const preview = page.frameLocator('iframe')
  const row = overlay.locator('[data-message-id="demo-0"]')
  for (const surface of [preview, overlay]) {
    await expect(surface.locator('[data-message-id="demo-0"] #message')).toContainText('こんにちは')
    await expect(surface.locator('.translation-list, .translation, .translation-placeholder')).toHaveCount(0)
  }
  await row.evaluate(el => { el.dataset.preserved = 'yes' })
  await page.locator('#language').selectOption('ja')
  await page.getByRole('button', { name: '添加', exact: true }).click()
  await page.getByRole('button', { name: '保存设置', exact: true }).click()
  await expect(row.locator('.translation')).toContainText('こんにちは')
  await expect(row).toHaveAttribute('data-preserved', 'yes')
  await page.getByRole('button', { name: '移除 日本語', exact: true }).click()
  await page.getByRole('button', { name: '保存设置', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('设置已保存')
  for (const surface of [preview, overlay]) {
    await expect(surface.locator('.translation-list, .translation, .translation-placeholder')).toHaveCount(0)
  }
  await expect(row).toHaveAttribute('data-preserved', 'yes')
  await overlay.close()
})


test('original stays above ordered translations including an identical source-language result', async ({ page }) => {
  let socket
  await page.routeWebSocket('**/ws', ws => {
    socket = ws
    ws.send(JSON.stringify({ type: 'snapshot', session: 'multi', messages: [], config: { ...config, target_languages: ['zh-Hans', 'en'] }, status: {} }))
  })
  await page.goto('/overlay')
  await expect.poll(() => Boolean(socket)).toBe(true)
  const send = event => socket.send(JSON.stringify({ session: 'multi', ...event }))
  const rows = [
    { language: 'zh-Hans', text: '', status: 'pending' },
    { language: 'en', text: 'Hello', status: 'complete' },
  ]
  send({ type: 'message', message: { id: 'multi-one', author: 'XXX', original: '你好', avatar: '', time: new Date().toISOString(), role: 'normal', translations: rows } })
  await expect(page.locator('#message')).toHaveText('你好')
  await expect(page.locator('.translation-row')).toHaveCount(2)
  await expect(page.locator('.translation-row').first()).toContainText('翻译中')
  rows[0] = { language: 'zh-Hans', text: '你好', status: 'complete' }
  send({ type: 'translation', id: 'multi-one', translations: rows })
  await expect(page.locator('.translation')).toHaveText(['你好', 'Hello'])
  await expect(page.locator('.translation-row')).toHaveText(['你好', 'Hello'])
  await expect(page.locator('.translation-language')).toHaveCount(0)
  const positions = await page.locator('[data-message-id="multi-one"]').evaluate(el => ({
    original: el.querySelector('#message').getBoundingClientRect().top,
    rows: [...el.querySelectorAll('.translation')].map(row => row.getBoundingClientRect().top),
  }))
  expect(positions.rows[0]).toBeGreaterThan(positions.original)
  expect(positions.rows[1]).toBeGreaterThan(positions.rows[0])
  send({ type: 'delete', ids: ['multi-one'] })
  send({ type: 'translation', id: 'multi-one', translations: rows })
  await expect(page.locator('yt-live-chat-text-message-renderer')).toHaveCount(0)
})


test('offline demo renders every Google target language without skipped extra rows', async ({ page, request, context }) => {
  const targets = ['zh-Hant', 'ja', 'fr', 'de', 'ko', 'es', 'en', 'zh-Hans']
  await request.put('/api/config', { data: { target_languages: targets } })
  await page.unroute('**/api/languages*')
  // Demo must not send actual chat translation or diagnostic requests.
  const diagnostics = []
  page.on('request', req => { if (req.url().includes('/api/translation/test')) diagnostics.push(req.url()) })
  await page.goto('/')
  await expect(page.locator('.language-stack li')).toHaveCount(8)
  const overlay = await context.newPage()
  await overlay.goto('/overlay')
  await expect(overlay.getByRole('status')).toHaveText('弹幕姬开始工作')
  await page.getByRole('button', { name: '体验演示' }).click()
  await expect(page.getByRole('status')).toContainText('八种常用语言均有固定译文')
  const preview = page.frameLocator('iframe')
  const rows = preview.locator('[data-message-id="demo-0"] .translation-row')
  await expect(rows).toHaveCount(8)
  await expect(preview.locator('[data-message-id="demo-0"] .translation')).toHaveCount(8)
  expect(await rows.evaluateAll(nodes => nodes.map(node => node.dataset.language))).toEqual(targets)
  expect(await rows.evaluateAll(nodes => nodes.every(node => node.dataset.status === 'complete'))).toBe(true)
  await expect(preview.locator('[data-message-id="demo-0"] .translation-placeholder')).toHaveCount(0)
  await expect(overlay.locator('[data-message-id="demo-0"] .translation')).toHaveCount(8)
  expect(diagnostics).toEqual([])
  await overlay.close()
})


test('mixed channel emotes keep order and images after translation updates', async ({ page }) => {
  let socket
  await page.route('https://yt3.ggpht.com/test-emote', route => route.fulfill({ contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48"><circle cx="24" cy="24" r="22" fill="pink"/></svg>' }))
  await page.routeWebSocket('**/ws', ws => { socket = ws; ws.send(JSON.stringify({ type: 'snapshot', session: 'emotes', messages: [], config, status: {} })) })
  await page.goto('/overlay')
  await expect.poll(() => Boolean(socket)).toBe(true)
  const send = event => socket.send(JSON.stringify({ session: 'emotes', ...event }))
  send({ type: 'message', message: { id: 'emote-one', author: 'Alice', original: 'Hello :wave: world 🌸 :wave:', role: 'normal', time: new Date().toISOString(), content_parts: [
    { type: 'text', text: 'Hello ' }, { type: 'emoji', text: ':wave:', url: 'https://yt3.ggpht.com/test-emote', width: 48, height: 48 },
    { type: 'text', text: ' world 🌸 ' }, { type: 'emoji', text: ':wave:', url: 'https://yt3.ggpht.com/test-emote', width: 48, height: 48 },
  ] } })
  const row = page.locator('[data-message-id="emote-one"]')
  const images = row.locator('#message img.emoji')
  await expect(images).toHaveCount(2)
  await expect.poll(() => images.first().evaluate(img => img.complete && img.naturalWidth > 0)).toBe(true)
  expect(await row.locator('#message').evaluate(el => [...el.children].map(node => node.querySelector('img') ? ':wave:' : node.textContent).join(''))).toBe('Hello :wave: world 🌸 :wave:')
  send({ type: 'translation', id: 'emote-one', translations: [{ language: 'zh-Hans', text: '你好 世界', status: 'complete' }] })
  await expect(row.locator('.translation')).toHaveText('你好 世界')
  await expect(images).toHaveCount(2)
  await expect(page.locator('yt-live-chat-text-message-renderer')).toHaveCount(1)
  await expect(images.first()).toHaveAttribute('referrerpolicy', 'no-referrer')
})


test('failed and unsafe image URLs fall back to literal names', async ({ page }) => {
  let socket
  let dialogs = 0
  const invalidRequests = []
  page.on('dialog', async dialog => { dialogs++; await dialog.dismiss() })
  page.on('request', req => { if (req.url().includes('evil.example')) invalidRequests.push(req.url()) })
  await page.route('https://yt3.ggpht.com/broken-emote', route => route.abort())
  await page.routeWebSocket('**/ws', ws => { socket = ws; ws.send(JSON.stringify({ type: 'snapshot', session: 'fallback', messages: [], config, status: {} })) })
  await page.goto('/overlay')
  await expect.poll(() => Boolean(socket)).toBe(true)
  socket.send(JSON.stringify({ type: 'message', session: 'fallback', message: { id: 'fallback', author: 'Alice', original: ':wave:', role: 'normal', time: new Date().toISOString(), content_parts: [
    { type: 'emoji', text: ':wave:', url: 'https://yt3.ggpht.com/broken-emote', width: 24, height: 24 },
    { type: 'emoji', text: '<script>alert(1)</script>', url: 'javascript:alert(1)' },
    { type: 'emoji', text: ':bad:', url: 'https://yt3.ggpht.com.evil.example/x' },
  ] } }))
  const row = page.locator('[data-message-id="fallback"]')
  await expect(row.locator('.emote-fallback')).toHaveText(':wave:')
  await expect(row.locator('#message')).toContainText('<script>alert(1)</script>')
  await expect(row.locator('#message img')).toHaveCount(0)
  await expect(row.locator('#message script')).toHaveCount(0)
  expect(invalidRequests).toEqual([])
  expect(dialogs).toBe(0)
})


test('YouTube stickers are bounded and deletion survives late translations', async ({ page }) => {
  let socket
  await page.setViewportSize({ width: 480, height: 720 })
  await page.route('https://lh3.googleusercontent.com/test-sticker', route => route.fulfill({ contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100"><rect width="200" height="100" fill="pink"/></svg>' }))
  await page.routeWebSocket('**/ws', ws => { socket = ws; ws.send(JSON.stringify({ type: 'snapshot', session: 'stickers', messages: [], config, status: {} })) })
  await page.goto('/overlay')
  await expect.poll(() => Boolean(socket)).toBe(true)
  const send = event => socket.send(JSON.stringify({ session: 'stickers', ...event }))
  send({ type: 'message', message: { id: 'sticker', author: 'Alice', original: 'Happy sticker', role: 'normal', time: new Date().toISOString(), content_parts: [
    { type: 'sticker', text: 'Happy sticker', url: 'https://lh3.googleusercontent.com/test-sticker', width: 20000, height: 10000 },
  ] } })
  const image = page.locator('[data-message-id="sticker"] img.chat-sticker')
  await expect(image).toBeVisible()
  const bounds = await image.boundingBox()
  expect(bounds.width).toBeLessThanOrEqual(256)
  expect(bounds.height).toBeLessThanOrEqual(160)
  send({ type: 'delete', ids: ['sticker'] })
  send({ type: 'translation', id: 'sticker', translation: 'late' })
  await expect(page.locator('[data-message-id="sticker"]')).toHaveCount(0)
})


test('offline demo emotes load in preview and OBS and scale with text', async ({ page, context }) => {
  await page.goto('/')
  const overlay = await context.newPage()
  await overlay.goto('/overlay')
  await expect(overlay.getByRole('status')).toHaveText('弹幕姬开始工作')
  await page.getByRole('button', { name: '体验演示' }).click()
  const image = page.frameLocator('iframe').locator('[data-message-id="demo-0"] #message img.emoji')
  await expect(image).toHaveAttribute('src', '/emotes/sakura.svg')
  await expect.poll(() => image.evaluate(img => img.complete && img.naturalWidth > 0)).toBe(true)
  const before = await image.boundingBox()
  await page.locator('#font-size').fill('36')
  await expect.poll(async () => (await image.boundingBox()).height).toBeGreaterThan(before.height)
  await expect(overlay.locator('[data-message-id="demo-0"] #message img.emoji')).toHaveAttribute('src', '/emotes/sakura.svg')
  await overlay.close()
})
