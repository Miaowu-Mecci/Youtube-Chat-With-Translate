import { test, expect } from '@playwright/test'

const config = { source: '', target_language: 'zh-Hans', target_languages: ['zh-Hans', 'en'], translation_enabled: false,
  style: { font_size: 24, color: '#ffffff', translation_color: '#8de1cb', show_avatar: true, max_messages: 100, custom_css: '' } }

test.beforeEach(async ({ request }) => {
  await request.post('/api/disconnect')
  await request.put('/api/config', { data: config })
})

for (const [browserLanguage, locale, heading, title] of [
  ['en-US', 'en', 'Make every message understood.', 'YouTube OBS Multilingual Chat'],
  ['ja-JP', 'ja', 'すべての言葉を、届けよう。', 'YouTube OBS 多言語チャット'],
  ['zh-TW', 'zh-CN', '让每一句话，都被听懂。', 'YouTube OBS 多语言弹幕'],
  ['fr-FR', 'zh-CN', '让每一句话，都被听懂。', 'YouTube OBS 多语言弹幕'],
]) {
  test.describe(`browser language ${browserLanguage}`, () => {
    test.use({ locale: browserLanguage })
    test('selects a supported UI language and remembers an explicit choice', async ({ page }) => {
      await page.goto('/')
      const chooser = page.getByRole('combobox', { name: 'Language', exact: true })
      await expect(chooser).toHaveValue(locale)
      await expect(page.getByRole('heading', { level: 1 })).toHaveText(heading)
      await expect(page).toHaveTitle(title)
      await expect(page.locator('html')).toHaveAttribute('lang', locale)
      await expect(chooser.locator('option')).toHaveText(['简体中文', '日本語', 'English'])
      const bounds = await chooser.boundingBox()
      expect(bounds.x).toBeGreaterThan(1000)
      if (locale === 'en' || locale === 'ja') await page.screenshot({ path: `test-results/dashboard-${locale}.png`, fullPage: true })
      const chosen = locale === 'en' ? 'ja' : 'en'
      await chooser.selectOption(chosen)
      await page.reload()
      await expect(chooser).toHaveValue(chosen)
      expect(await page.evaluate(() => localStorage.getItem('ytchat.uiLanguage'))).toBe(chosen)
    })
  })
}

test('changing UI language preserves drafts, target languages, chat rows and live sockets', async ({ page, context, request }) => {
  const sockets = []
  let writes = 0
  await context.routeWebSocket('**/ws', ws => {
    sockets.push(ws)
    ws.send(JSON.stringify({ type: 'snapshot', session: 'locale', messages: [], config, status: { connection: 'connected', message: '已连接 YouTube 直播聊天。', translation_message: '翻译运行中。' } }))
  })
  page.on('request', req => { if (req.method() === 'PUT' || req.url().includes('/api/translation/')) writes++ })
  await page.goto('/')
  await expect(page.locator('.language-stack li')).toHaveCount(2)
  await page.locator('#source').fill('https://www.youtube.com/watch?v=Sv2vZ8uZKVI')
  await page.locator('#font-size').fill('36')
  const overlay = await context.newPage()
  await overlay.goto('/overlay')
  await expect(overlay.getByRole('status')).toHaveText('弹幕姬开始工作')
  await expect.poll(() => sockets.length).toBe(3)
  const send = event => sockets.forEach(ws => ws.send(JSON.stringify({ session: 'locale', ...event })))
  send({ type: 'message', message: { id: 'original', author: 'Alice', role: 'moderator', original: '尚未连接。', time: new Date().toISOString(), translations: [{ language: 'zh-Hans', text: '翻译未开启。', status: 'complete' }, { language: 'en', text: '', status: 'pending' }] } })
  const preview = page.frameLocator('iframe')
  const row = overlay.locator('[data-message-id="original"]')
  await expect(row.locator('#message')).toHaveText('尚未连接。')
  await row.evaluate(el => { el.dataset.preserved = 'yes' })
  await page.getByRole('combobox', { name: 'Language', exact: true }).selectOption('en')
  for (const surface of [preview, overlay]) {
    await expect(surface.locator('.overlay-start')).toHaveText('Chat overlay is ready')
    await expect(surface.locator('.translation-placeholder')).toHaveText('Translating…')
    await expect(surface.locator('#message')).toHaveText('尚未连接。')
    await expect(surface.locator('.translation')).toHaveText('翻译未开启。')
    await expect(surface.locator('yt-live-chat-author-badge-renderer > span')).toHaveAttribute('title', 'Moderator')
  }
  await expect(page.locator('.status-pill')).toHaveText('Connected')
  await expect(page.locator('.language-stack strong')).toHaveText(['Simplified Chinese', 'English'])
  await page.getByRole('combobox', { name: 'Language', exact: true }).selectOption('ja')
  await expect(overlay.locator('.overlay-start')).toHaveText('コメント表示を開始しました')
  await expect(row.locator('.translation-placeholder')).toHaveText('翻訳中…')
  await expect(row).toHaveAttribute('data-preserved', 'yes')
  await expect(page.locator('#source')).toHaveValue('https://www.youtube.com/watch?v=Sv2vZ8uZKVI')
  await expect(page.locator('#font-size')).toHaveValue('36')
  expect(await page.locator('.language-stack li').evaluateAll(nodes => nodes.map(node => node.dataset.language))).toEqual(['zh-Hans', 'en'])
  expect(sockets).toHaveLength(3)
  expect(writes).toBe(0)
  expect((await (await request.get('/api/config')).json()).target_languages).toEqual(['zh-Hans', 'en'])
  await overlay.close()
})

test('system diagnostics, rate limits and action results follow the selected UI language', async ({ page }) => {
  await page.routeWebSocket('**/ws', ws => ws.send(JSON.stringify({ type: 'snapshot', session: 'errors', messages: [], config, status: {
    connection: 'error', code: 'web_protocol', chat_started_at: new Date().toISOString(), ignored_history: 42,
    message: '未取得实时聊天令牌；可能是聊天未开放或页面结构已变化。聊天页 HTTP 200/HTML，初始标记有，解析成功，聊天令牌无；观看页 HTTP 403/纯文本，初始标记无，解析失败，聊天令牌无',
    translation_message: 'Google 网页翻译限流，暂停新请求 60 秒；失败消息保留原文。',
    translation_counts: { pending: 2, complete: 3, failed: 1, skipped: 0 },
  } })))
  await page.route('**/api/translation/test', route => route.fulfill({ status: 503, json: { code: 'cooldown', detail: 'Google 正在限流等待中，请稍后测试。' } }))
  await page.goto('/')
  await page.getByRole('combobox', { name: 'Language', exact: true }).selectOption('en')
  await expect(page.locator('#connection')).toContainText('Chat page HTTP 200/HTML, initial marker: present, parsing: success, chat token: absent')
  await expect(page.locator('#connection')).toContainText('Watch page HTTP 403/Plain text')
  await expect(page.locator('#connection')).toContainText('Filtered 42 earlier messages')
  await expect(page.getByLabel('Translation progress')).toContainText('pending 2 · complete 3 · failed 1 · skipped 0')
  await expect(page.locator('#translation')).toContainText('New requests pause for 60 seconds')
  await page.getByRole('button', { name: 'Save & test translation', exact: true }).click()
  await expect(page.getByRole('status', { name: 'Translation test result' })).toHaveText('Google is in a rate-limit cooldown. Test again later.')
  await page.getByRole('combobox', { name: 'Language', exact: true }).selectOption('ja')
  await expect(page.getByRole('status', { name: '翻訳テスト結果' })).toHaveText('Google のリクエスト制限による待機中です。しばらくしてからテストしてください。')
  await page.route('**/api/translation/test', route => route.fulfill({ json: { original: '尚未连接。', translations: [{ text: '翻译未开启。' }] } }))
  await page.getByRole('button', { name: '保存して翻訳をテスト', exact: true }).click()
  await expect(page.getByRole('status', { name: '翻訳テスト結果' })).toHaveText('テスト成功：尚未连接。 → 翻译未开启。')
  await page.getByRole('combobox', { name: 'Language', exact: true }).selectOption('en')
  await expect(page.getByRole('status', { name: 'Translation test result' })).toHaveText('Test successful: 尚未连接。 → 翻译未开启。')
  await page.getByRole('button', { name: 'Save settings', exact: true }).click()
  await expect(page.locator('.toast')).toHaveText('Settings saved and synced with OBS.')
  await page.route('**/api/config', route => route.request().method() === 'PUT'
    ? route.fulfill({ status: 422, json: { detail: '配置无效，请检查语言、颜色、数值和字段。' } }) : route.continue())
  await page.getByRole('button', { name: 'Save settings', exact: true }).click()
  await expect(page.locator('.toast')).toHaveText('Invalid settings. Check languages, colors, values and fields.')
})

test('all UI languages fit mobile screens and the language control stays reachable', async ({ page }) => {
  await page.goto('/')
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 844 })
    for (const locale of ['en', 'ja', 'zh-CN']) {
      await page.getByRole('combobox', { name: 'Language', exact: true }).selectOption(locale)
      await page.evaluate(() => window.scrollTo(0, 0))
      await expect(page.getByRole('combobox', { name: 'Language', exact: true })).toBeInViewport()
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
      await page.locator('#appearance').scrollIntoViewIfNeeded()
      await expect(page.locator('#appearance .primary')).toBeVisible()
      if (width === 390) await page.screenshot({ path: `test-results/dashboard-${locale}-mobile.png`, fullPage: true })
    }
  }
})

test('invalid stored language falls back safely and UI works without browser storage', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('ytchat.uiLanguage', '<script>invalid</script>'))
  await page.goto('/')
  await expect(page.getByRole('combobox', { name: 'Language', exact: true })).toHaveValue('zh-CN')
  await page.addInitScript(() => {
    Object.defineProperty(window, 'localStorage', { get() { throw new DOMException('Disabled', 'SecurityError') } })
  })
  await page.reload()
  await page.getByRole('combobox', { name: 'Language', exact: true }).selectOption('ja')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('すべての言葉を、届けよう。')
})
