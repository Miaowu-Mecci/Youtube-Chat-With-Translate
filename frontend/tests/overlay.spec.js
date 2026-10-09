import { test, expect } from '@playwright/test'

const config = { source: '', source_type: 'auto', youtube_key: '', azure_key: '', azure_region: '',
  target_language: 'zh-Hans', translation_enabled: false, translation_provider: 'google_web',
  style: { font_size: 24, color: '#ffffff', translation_color: '#8de1cb', show_avatar: true, max_messages: 100, custom_css: '' } }

test.beforeEach(async ({ request, page }) => {
  await request.post('/api/disconnect')
  await request.put('/api/config', { data: config })
  await page.route('**/api/languages*', route => {
    const languages = [{ code: 'zh-Hans', name: '简体中文' }, { code: 'ja', name: '日本語' }]
    if (new URL(route.request().url()).searchParams.get('provider') === 'azure') languages.push({ code: 'it', name: 'Italiano' })
    return route.fulfill({ json: { languages } })
  })
})

test('settings preview and standalone overlay share the demo', async ({ page, context }) => {
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '让每一句话，都被听懂。' })).toBeVisible()
  await page.getByRole('button', { name: '体验演示' }).click()
  const preview = page.frameLocator('iframe')
  const first = preview.locator('[data-message-id="demo-0"]')
  await expect(first.locator('#message')).toContainText('こんにちは')
  await expect(first.locator('.translation')).toContainText('你好！')
  await expect(first).toHaveCount(1)
  await expect(page.locator('.status-pill')).toHaveText('演示中')
  const overlay = await context.newPage()
  await overlay.goto('/overlay')
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
  expect(positions.translation).toBeLessThan(positions.original)
  send({ type: 'delete', ids: ['one'] })
  await expect(page.locator('yt-live-chat-text-message-renderer')).toHaveCount(0)
  send({ type: 'translation', id: 'one', translation: '迟到的译文' })
  await expect(page.locator('yt-live-chat-text-message-renderer')).toHaveCount(0)
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
    expect(saved.translation_provider).toBe('google_web')
    expect(saved.translation_enabled).toBe(true)
    expect(saved.azure_key_set).toBe(false)
    tested = true
    return route.fulfill({ json: { original: 'Hello', translation: '你好', source_language: 'en' } })
  })
  await page.goto('/')
  await expect(page.locator('#provider')).toHaveValue('google_web')
  await expect(page.locator('#azure-key')).toHaveCount(0)
  await expect(page.locator('#translation')).toContainText('免账号、免 Key')
  await page.getByRole('checkbox', { name: '开启翻译' }).check()
  await page.getByRole('button', { name: '保存并测试翻译' }).click()
  await expect(page.getByRole('status', { name: '翻译测试结果' })).toContainText('Hello → 你好')
  expect(tested).toBe(true)
  await expect(page.locator('.status-pill')).toHaveText('未连接')
  await page.route('**/api/translation/test', route => route.fulfill({ status: 503, json: { code: 'cooldown', detail: 'Google 正在限流等待中，请稍后测试。' } }))
  await page.getByRole('button', { name: '保存并测试翻译' }).click()
  await expect(page.getByRole('status', { name: '翻译测试结果' })).toContainText('限流等待')
})

test('switching services preserves Azure credentials and resets unsupported language', async ({ page, request }) => {
  await page.goto('/')
  await page.locator('#provider').selectOption('azure')
  await expect(page.locator('#azure-key')).toBeVisible()
  await page.locator('#azure-key').fill('MOCK_AZURE_KEY')
  await page.locator('#region').fill('eastasia')
  await page.locator('#language').selectOption('it')
  await page.getByRole('button', { name: '保存设置', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('设置已保存')
  await page.locator('#provider').selectOption('google_web')
  await expect(page.locator('#azure-key')).toHaveCount(0)
  await expect(page.locator('#language')).toHaveValue('zh-Hans')
  await expect(page.locator('#translation')).toContainText('不支持原目标语言')
  await page.getByRole('button', { name: '保存设置', exact: true }).click()
  await expect.poll(async () => (await (await request.get('/api/config')).json()).translation_provider).toBe('google_web')
  const saved = await (await request.get('/api/config')).json()
  expect(saved.azure_key_set).toBe(true)
  expect(saved.azure_region).toBe('eastasia')
  await page.locator('#provider').selectOption('azure')
  await expect(page.locator('#azure-key')).toHaveAttribute('placeholder', '留空保留已保存的 Key')
})


test('Azure language lookup failure preserves an existing target on upgrade', async ({ page, request }) => {
  await request.put('/api/config', { data: { translation_provider: 'azure', target_language: 'it' } })
  await page.route('**/api/languages*', route => route.fulfill({ json: {
    languages: [{ code: 'zh-Hans', name: '简体中文' }], fallback: true, message: '语言列表暂不可用。'
  } }))
  await page.goto('/')
  await expect(page.locator('#language')).toHaveValue('it')
  await page.getByRole('button', { name: '保存设置', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('设置已保存')
  expect((await (await request.get('/api/config')).json()).target_language).toBe('it')
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
