<template>
  <overlay v-if="isOverlay" />
  <div v-else class="dashboard">
    <aside class="sidebar">
      <a class="brand" href="/"><span class="brand-mark">{{ $t('译') }}</span><span>LiveChat<span class="brand-sub">YOUTUBE · OBS</span></span></a>
      <div class="side-label">{{ $t('工作空间') }}</div>
      <a class="nav-item active" href="#connection"><span>◉</span> {{ $t('直播弹幕') }}</a>
      <a class="nav-item" href="#translation"><span>文</span> {{ $t('多语言翻译') }}</a>
      <a class="nav-item" href="#appearance"><span>◐</span> {{ $t('外观与样式') }}</a>
      <div class="side-bottom"><span class="local-dot"></span> {{ $t('本地运行') }}<span class="side-note">{{ $t('你的直播，你的表达。') }}</span></div>
    </aside>
    <main class="workspace">
      <header class="topbar"><span class="breadcrumb">{{ $t('工作空间') }} <span class="crumb">/</span> {{ $t('直播弹幕') }}</span><div class="topbar-tools"><span class="version">v0.5.0 · MULTILINGUAL</span><label class="ui-language" for="ui-language">Language<select id="ui-language" v-model="uiLocale" aria-label="Language"><option v-for="locale in uiLocales" :key="locale.code" :value="locale.code">{{ locale.name }}</option></select></label></div></header>
      <div class="page-title"><div><div class="eyebrow">{{ $t('CONNECT WITHOUT LANGUAGE BARRIERS') }}</div><h1>{{ $t('让每一句话，都被听懂') }}<span>{{ $t('。') }}</span></h1><p>{{ $t('将 YouTube 直播弹幕带入 OBS，让每一种语言都有位置。') }}</p></div><button class="secondary" :disabled="busy" @click="action('demo', true)">▷ {{ $t('体验演示') }}</button></div>
      <div class="toast" role="status" v-if="notice">{{ $uiMessage(notice) }}</div>
      <div class="columns">
        <div class="settings">
          <section class="card" id="connection">
            <div class="card-heading"><h2><span class="step">01</span> {{ $t('连接直播间') }}</h2><span class="status-pill" :class="status.connection">{{ statusLabel }}</span></div>
            <label for="source">{{ $t('YouTube 直播链接 / ID') }}</label>
            <input id="source" v-model="form.source" placeholder="https://www.youtube.com/watch?v=…" autocomplete="off">
            <p class="small">{{ $t('输入公开直播视频链接，即可免费接收弹幕。只支持正在直播的公开聊天。') }}</p>
            <div class="button-row"><button class="primary" :disabled="busy" @click="action('connect', true)">{{ $t('连接直播间') }} <span>→</span></button><button class="secondary" :disabled="busy" @click="action('disconnect')">{{ $t('断开') }}</button></div>
            <p class="connection-message">{{ $uiMessage(status.message) }}</p>
            <p class="small">{{ $t('仅收录点击「连接直播间」后发布的新弹幕，不显示或翻译此前的历史弹幕。') }}</p>
            <p v-if="status.chat_started_at" class="small">{{ $t('已过滤 {count} 条历史弹幕；自动重连继续使用本次连接的起点。', { count: status.ignored_history || 0 }) }}</p>
          </section>

          <section class="card" id="translation">
            <div class="card-heading"><h2><span class="step">02</span> {{ $t('多语言翻译') }}</h2><label class="switch"><input type="checkbox" v-model="form.translation_enabled" :aria-label="$t('开启翻译')"><span></span></label></div>
            <p class="card-description">{{ $t('原文即时出现，译文随后补上。让不同语言的观众一起参与。') }}</p>
            <p class="small">{{ $t('Google Translate 自动识别原文语言，按下方顺序翻译。接口可能限流，失败时保留原文。') }}</p>
            <div class="language-heading"><label>{{ $t('目标语言与显示顺序') }}</label><span>{{ form.target_languages.length }} / 8</span></div>
            <ol class="language-stack" :aria-label="$t('已选目标语言')">
              <li v-for="(code, index) in form.target_languages" :key="code" draggable="true" @dragstart="dragIndex = index" @dragover.prevent @drop.prevent="dropLanguage(index)" @dragend="dragIndex = null" :data-language="code">
                <span class="language-number">{{ String(index + 1).padStart(2, '0') }}</span>
                <div class="language-name"><strong>{{ languageName(code) }}</strong><small>{{ code }}</small></div>
                <div class="language-actions">
                  <button :aria-label="$t('上移 {name}', { name: languageName(code) })" :disabled="index === 0" @click="moveLanguage(index, index - 1)">↑</button>
                  <button :aria-label="$t('下移 {name}', { name: languageName(code) })" :disabled="index === form.target_languages.length - 1" @click="moveLanguage(index, index + 1)">↓</button>
                  <button :aria-label="$t('移除 {name}', { name: languageName(code) })" @click="removeLanguage(index)">×</button>
                </div>
              </li>
            </ol>
            <p v-if="!form.target_languages.length" class="small" :aria-label="$t('无目标语言')">{{ $t('未选择翻译语言，仅显示原文。') }}</p>
            <div class="add-language"><select id="language" v-model="languageToAdd" :aria-label="$t('添加目标语言')"><option value="" disabled>＋ {{ $t('添加一种语言') }}</option><option v-for="language in availableLanguages" :key="language.code" :value="language.code">{{ languageName(language.code) }} · {{ language.code }}</option></select><button class="secondary" :disabled="!languageToAdd || form.target_languages.length >= 8" @click="addLanguage">{{ $t('添加') }}</button></div>
            <p class="small">{{ $t('拖动语言卡片或使用 ↑ ↓ 调整顺序，保存后同步到 OBS。最多选择 8 种；每种语言单独请求，语言越多，翻译等待越长。') }}</p>
            <div class="translation-flow"><template v-if="form.target_languages.length"><span>{{ $t('原文') }}</span><span>→</span></template><strong>{{ targetName }}</strong><span v-if="form.target_languages.length" class="flow-badge">{{ $t('按序逐行显示') }}</span></div>
            <div class="button-row"><button class="secondary" :disabled="busy || !form.target_languages.length" @click="testTranslation">{{ $t('保存并测试翻译') }}</button><button class="secondary" :disabled="busy || !form.target_languages.length" @click="resumeTranslation">{{ $t('恢复翻译') }}</button></div>
            <p class="small">{{ $t('测试会向 Google 发送固定外语样例，不需要连接 YouTube。测试翻译不受弹幕翻译开关控制。') }}</p>
            <p class="connection-message" role="status" :aria-label="$t('翻译测试结果')" v-if="testResult">{{ $uiMessage(testResult) }}</p>
            <p class="connection-message">{{ $uiMessage(status.translation_message) }}</p>
            <p v-if="status.translation_counts" class="small" :aria-label="$t('翻译进度')">{{ $t('当前保留弹幕：等待 {pending} · 已完成 {complete} · 失败 {failed} · 跳过 {skipped}。Google 每秒最多请求约一种语言；恢复翻译会重新处理未完成消息。', status.translation_counts) }}</p>
            <p class="small" v-if="languageNotice">{{ $uiMessage(languageNotice) }}</p>
          </section>

          <section class="card" id="appearance">
            <div class="card-heading"><h2><span class="step">03</span> {{ $t('外观与样式') }}</h2><span class="small">{{ $t('实时预览') }}</span></div>
            <div class="field-row"><div><label for="font-size">{{ $t('字号') }} <span class="saved">{{ form.style.font_size }} px</span></label><input id="font-size" type="range" min="10" max="72" v-model.number="form.style.font_size"></div><div><label for="max-messages">{{ $t('保留消息数量') }}</label><input id="max-messages" type="number" min="10" max="500" v-model.number="form.style.max_messages"></div></div>
            <div class="color-row"><label>{{ $t('原文颜色') }} <input :aria-label="$t('原文颜色')" type="color" v-model="form.style.color"></label><label>{{ $t('译文颜色') }} <input :aria-label="$t('译文颜色')" type="color" v-model="form.style.translation_color"></label><label class="checkbox-label"><input type="checkbox" v-model="form.style.show_avatar"> {{ $t('显示头像') }}</label></div>
            <label for="custom-css">{{ $t('自定义 CSS') }} <span class="label-note">{{ $t('兼容 blivechat 普通弹幕选择器') }}</span></label>
            <textarea id="custom-css" v-model="form.style.custom_css" rows="5" spellcheck="false" placeholder=".translation { font-weight: 600; }"></textarea>
            <div class="button-row"><button class="primary" :disabled="busy" @click="save()">{{ $t('保存设置') }}</button><button class="secondary" @click="copy(css, 'CSS 已复制')">{{ $t('复制 CSS') }}</button></div>
          </section>
        </div>

        <div class="preview-column">
          <section class="card preview-card"><div class="card-heading"><h2>{{ $t('评论栏预览') }}</h2><span class="preview-live"><span class="local-dot"></span> {{ $t('LIVE PREVIEW') }}</span></div><div class="preview-screen"><div class="preview-caption">{{ $t('YOUR STREAM, CONNECTED.') }}</div><iframe ref="preview" src="/overlay" :title="$t('OBS 评论栏实时预览')" @load="draftPreview"></iframe><div v-if="!hasMessages" class="empty-state"><span>文 ↔ A</span><strong>{{ $t('跨越语言，开始对话') }}</strong><p>{{ $t('连接直播间或点击「体验演示」') }}<br>{{ $t('这里将展示你的多语言评论栏') }}</p></div></div><div class="preview-footer"><span>{{ $t('透明背景 · 原文在上，多语言依序排列') }}</span><a href="/overlay" target="_blank" rel="noreferrer">{{ $t('独立预览') }} ↗</a></div></section>
          <section class="card obs-card"><div class="card-heading"><h2>{{ $t('添加到 OBS') }}</h2><span class="obs-badge">{{ $t('浏览器源') }}</span></div><p class="card-description">{{ $t('在 OBS 中添加「浏览器」源，粘贴下方地址。') }}</p><div class="url-box"><code>{{ overlayUrl }}</code><button :aria-label="$t('复制 OBS 地址')" @click="copy(overlayUrl, 'OBS 地址已复制')">{{ $t('复制') }}</button></div><div class="obs-tip"><span>{{ $t('建议尺寸') }}</span><strong>480 × 720</strong></div><p class="small">{{ $t('OBS 自定义 CSS 保留透明背景设置即可。页面不包含控制按钮，多个浏览器源共享同一直播连接。') }}</p></section>
          <div class="privacy-note"><span>⌁</span><p>{{ $t('开启翻译后，消息的文字部分会发送至 Google。演示使用本地固定译文，不访问翻译服务。') }}</p></div>
        </div>
      </div>
      <footer class="page-footer"><span>{{ $t('Made for conversations, in every language.') }}</span><a href="https://github.com/xfgryujk/blivechat" target="_blank" rel="noreferrer">{{ $t('渲染组件源自 blivechat · MIT') }} ↗</a></footer>
    </main>
  </div>
</template>

<script>
import Overlay from './Overlay.vue'
import { makeCSS } from './style'
import { languageState, locales, setLocale } from './i18n'
const initial = { source: '', target_languages: ['zh-Hans'], translation_enabled: false, target_language: 'zh-Hans',
  style: { font_size: 24, color: '#ffffff', translation_color: '#8de1cb', show_avatar: true, max_messages: 100, custom_css: '' } }
export default {
  components: { Overlay },
  data: () => ({ isOverlay: location.pathname === '/overlay', form: JSON.parse(JSON.stringify(initial)),
    status: { connection: 'idle', message: '尚未连接。', translation_message: '翻译未开启。' },
    languageToAdd: '', dragIndex: null, testResult: '', languages: [{ code: 'zh-Hans', name: '简体中文' }], languageNotice: '', notice: '', busy: false, hasMessages: false,
    socket: null, retryTimer: null, stopped: false, ready: false }),
  computed: {
    uiLocale: { get() { return languageState.locale }, set: setLocale },
    uiLocales() { return locales },
    overlayUrl() { return `${location.origin}/overlay` },
    css() { return makeCSS(this.form.style) },
    targetName() { return this.form.target_languages.map(this.languageName).join(' → ') || this.$t('仅显示原文') },
    availableLanguages() { return this.languages.filter(item => !this.form.target_languages.includes(item.code)) },
    statusLabel() { return this.$t({ idle: '未连接', connecting: '连接中', connected: '已连接', reconnecting: '重连中', demo: '演示中', error: '连接异常', ended: '已结束' }[this.status.connection] || '未连接') }
  },
  watch: { 'form.style': { deep: true, handler() { this.draftPreview() } } },
  async mounted() {
    if (this.isOverlay) return
    window.addEventListener('message', this.previewReady)
    try { this.loadConfig(await this.api('/api/config')); this.ready = true } catch (error) { this.notice = error.message }
    this.listen()
    await this.loadLanguages()
  },
  beforeDestroy() {
    this.stopped = true
    clearTimeout(this.retryTimer)
    this.socket?.close()
    window.removeEventListener('message', this.previewReady)
  },
  methods: {
    async api(path, method = 'GET', body) {
      const response = await fetch(path, { method, headers: { 'Content-Type': 'application/json' }, ...(body !== undefined ? { body: JSON.stringify(body) } : {}) })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || '请求失败，请检查本地服务。')
      return data
    },
    loadConfig(config) {
      this.form = { ...config, target_languages: config.target_languages || [config.target_language || 'zh-Hans'] }
    },
    async loadLanguages() {
      try {
        const data = await this.api('/api/languages')
        this.languages = data.languages
        this.languageNotice = ''
      } catch { this.languageNotice = '语言列表暂不可用，请刷新页面重试。' }
    },
    languageName(code) { return this.$t(this.languages.find(item => item.code === code)?.name || code) },
    addLanguage() {
      if (this.languageToAdd && this.form.target_languages.length < 8 && !this.form.target_languages.includes(this.languageToAdd)) this.form.target_languages.push(this.languageToAdd)
      this.languageToAdd = ''
    },
    removeLanguage(index) { this.form.target_languages.splice(index, 1) },
    moveLanguage(from, to) {
      if (to < 0 || to >= this.form.target_languages.length || from === to) return
      const [code] = this.form.target_languages.splice(from, 1)
      this.form.target_languages.splice(to, 0, code)
    },
    dropLanguage(index) { if (this.dragIndex !== null) this.moveLanguage(this.dragIndex, index); this.dragIndex = null },
    async testTranslation() {
      this.busy = true
      this.testResult = ''
      try {
        await this.persist()
        const result = await this.api('/api/translation/test', 'POST')
        this.testResult = { key: '测试成功：{original} → {translations}', values: { original: result.original, translations: (result.translations || [{ text: result.translation }]).map(row => row.text).join(' / ') } }
      } catch (error) { this.testResult = error.message }
      finally { this.busy = false }
    },
    async resumeTranslation() {
      this.busy = true
      try {
        await this.persist()
        await this.api('/api/translation/resume', 'POST')
        this.testResult = '已请求恢复翻译；若正在限流等待，仍需等待结束。'
      } catch (error) { this.testResult = error.message }
      finally { this.busy = false }
    },
    async persist() {
      if (!this.ready) throw new Error('配置尚未加载，请刷新页面后重试。')
      const payload = JSON.parse(JSON.stringify(this.form))
      if (payload.target_languages.length) payload.target_language = payload.target_languages[0]
      this.loadConfig(await this.api('/api/config', 'PUT', payload))
    },
    async save() {
      this.busy = true
      try { await this.persist(); this.notice = '设置已保存，OBS 页面已同步。' } catch (error) { this.notice = error.message }
      finally { this.busy = false }
    },
    async action(name, saveFirst = false) {
      const clickedAt = new Date().toISOString()
      this.busy = true
      try { if (saveFirst) await this.persist(); await this.api(`/api/${name}`, 'POST', name === 'connect' ? { started_at: clickedAt } : undefined); this.notice = name === 'demo' ? '演示模式已启动，八种常用语言均有固定译文；不调用真实翻译。' : '' }
      catch (error) { this.notice = error.message }
      finally { this.busy = false }
    },
    async copy(text, notice) {
      try { await navigator.clipboard.writeText(text); this.notice = notice }
      catch { this.notice = '浏览器未允许复制，请手动选择文本复制。' }
    },
    previewReady(event) { if (event.origin === location.origin && event.source === this.$refs.preview?.contentWindow && event.data?.type === 'preview-ready') this.draftPreview() },
    draftPreview() { this.$refs.preview?.contentWindow?.postMessage({ type: 'preview-style', style: JSON.parse(JSON.stringify(this.form.style)) }, location.origin) },
    listen() {
      const socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`)
      this.socket = socket
      socket.onmessage = ({ data }) => {
        const event = JSON.parse(data)
        if (event.type === 'snapshot') { this.status = event.status; this.hasMessages = event.messages.length > 0 }
        else if (event.type === 'status') this.status = event.status
        else if (event.type === 'message') this.hasMessages = true
      }
      socket.onclose = () => {
        this.status = { ...this.status, connection: 'reconnecting', message: '本地服务连接断开，正在重试。' }
        if (!this.stopped) this.retryTimer = setTimeout(this.listen, 1500)
      }
      socket.onerror = () => socket.close()
    }
  }
}
</script>

<style>
.dashboard { --accent: #146b55; --line: #e5e9e6; font-family: "Segoe UI", "Microsoft YaHei", sans-serif; color: #223a32; background: #f7f9f7; min-height: 100vh; font-size: 14px; }
.dashboard * { box-sizing: border-box; }
.dashboard a { color: inherit; text-decoration: none; }
.sidebar { position: fixed; inset: 0 auto 0 0; width: 224px; background: #fff; border-right: 1px solid var(--line); padding: 32px 22px; display: flex; flex-direction: column; z-index: 2; }
.brand { display: flex; align-items: center; gap: 12px; font-size: 23px; font-weight: 700; letter-spacing: -.8px; }
.brand-mark { width: 42px; height: 42px; display: grid; place-items: center; border-radius: 12px; background: var(--accent); color: white; font-size: 23px; }
.brand-sub { display: block; font-size: 9px; letter-spacing: 2px; margin-top: 4px; color: #8c9992; }
.side-label { color: #9aa59e; font-size: 11px; margin: 56px 14px 16px; }
.nav-item { padding: 14px; border-radius: 8px; margin-bottom: 6px; color: #7a8780 !important; display: flex; gap: 13px; align-items: center; }
.nav-item span { width: 18px; text-align: center; }
.nav-item.active { background: #edf5ef; color: var(--accent) !important; font-weight: 600; }
.side-bottom { margin-top: auto; font-size: 12px; color: #697d70; padding-left: 12px; }
.local-dot { display: inline-block; width: 6px; height: 6px; background: #58a87b; border-radius: 50%; margin-right: 7px; vertical-align: middle; }
.side-note { display: block; margin-top: 12px; color: #a0aba4; font-size: 11px; }
.workspace { margin-left: 224px; padding: 0 42px 24px; max-width: 1700px; }
.topbar { height: 75px; border-bottom: 1px solid var(--line); display: flex; align-items: center; justify-content: space-between; font-size: 12px; color: #89978e; }
.crumb { margin: 0 13px; color: #b2bdb6; }.version { font-size: 10px; letter-spacing: 1.4px; }
.page-title { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 35px 0 30px; }.eyebrow { font-size: 9px; letter-spacing: 2px; color: #859d90; margin-bottom: 12px; }
.dashboard h1 { font-size: clamp(24px, 2.3vw, 34px); letter-spacing: -1.3px; margin: 0 0 12px; font-weight: 650; }.dashboard h1 span { color: var(--accent); }.page-title p { color: #84928a; font-size: 13px; margin: 0; }
.columns { display: grid; grid-template-columns: minmax(370px, 1.16fr) minmax(340px, 1fr); gap: 24px; align-items: start; }.settings { display: grid; gap: 20px; }.card { background: #fff; border: 1px solid var(--line); border-radius: 12px; padding: 24px; box-shadow: 0 2px 3px #263c2c03; scroll-margin-top: 20px; }
.card-heading { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 23px; }.dashboard h2 { font-size: 15px; margin: 0; font-weight: 650; }.step { font-size: 11px; color: #9daf9f; margin-right: 10px; font-weight: 400; font-family: monospace; }.status-pill { padding: 5px 10px; border-radius: 20px; font-size: 10px; background: #f2f4f2; color: #7e8c82; }.status-pill.connected, .status-pill.demo { background: #e9f6ed; color: #208056; }.status-pill.error { color: #aa493d; background: #fff0ea; }
.dashboard label { display: block; font-size: 12px; font-weight: 500; margin-bottom: 9px; color: #53675b; }.dashboard input:not([type=checkbox]):not([type=range]):not([type=color]), .dashboard select, .dashboard textarea { width: 100%; border: 1px solid #dfe6e0; border-radius: 6px; padding: 11px 12px; background: #fbfcfb; color: #334e3f; font: inherit; font-size: 12px; outline: none; }.dashboard input:focus, .dashboard select:focus, .dashboard textarea:focus { border-color: #5d9980 !important; box-shadow: 0 0 0 2px #176b5510; }.dashboard input::placeholder, .dashboard textarea::placeholder { color: #a4b0a6; }.field-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 18px; }.helper-row { display: flex; justify-content: space-between; margin-top: 10px; gap: 10px; }.helper-row a { font-size: 10px; color: #7e9989; }.saved { float: right; font-weight: 400; color: #80a18e; font-size: 10px; }.dashboard button { cursor: pointer; font: inherit; font-size: 12px; border-radius: 6px; transition: background .15s; }.dashboard button:disabled { opacity: .5; cursor: wait; }.primary { background: var(--accent); color: white; border: 1px solid var(--accent); padding: 11px 18px; }.primary:hover { background: #105441; }.primary span { margin-left: 20px; }.secondary { background: white; border: 1px solid #dfe6e0; color: #4c6657; padding: 11px 16px; }.secondary:hover { background: #f4f8f4; }.text-button { background: none; border: 0; color: #a18077; font-size: 10px !important; padding: 0; }.button-row { display: flex; gap: 10px; margin-top: 20px; }.connection-message { font-size: 11px; color: #8e9c91; margin: 12px 0 0; line-height: 1.7; }.card-description { font-size: 12px; color: #8a998e; margin: -7px 0 20px; line-height: 1.8; }.switch { margin: 0 !important; position: relative; cursor: pointer; }.switch input { position: absolute; opacity: 0; width: 38px; height: 22px; margin: 0; }.switch span { width: 38px; height: 22px; background: #dfe6e0; border-radius: 15px; display: block; }.switch span:before { content: ''; position: absolute; top: 3px; left: 3px; width: 16px; height: 16px; background: #fff; border-radius: 50%; transition: transform .2s; }.switch input:checked + span { background: var(--accent); }.switch input:checked + span:before { transform: translateX(16px); }.switch input:focus-visible + span { outline: 2px solid #69af95; outline-offset: 2px; }.translation-flow { margin-top: 12px; padding: 11px 13px; background: #f4f8f4; border: 1px dashed #dce7de; border-radius: 6px; display: flex; align-items: center; gap: 12px; font-size: 10px; color: #84988a; }.translation-flow strong { color: #3e7960; font-weight: 500; }.flow-badge { margin-left: auto; font-size: 9px; background: #e9f0e9; padding: 4px 6px; border-radius: 4px; }.info-note { display: flex; gap: 9px; background: #f6f8f5; border-radius: 6px; padding: 12px; font-size: 10px; color: #879685; line-height: 1.8; margin-top: 18px; }.small { font-size: 10px; color: #98a499; line-height: 1.8; }.color-row { display: flex; gap: 20px; align-items: center; margin: 20px 0; flex-wrap: wrap; }.color-row label { display: flex; align-items: center; gap: 10px; margin: 0; font-size: 11px; }.color-row input[type=color] { width: 30px; height: 25px; background: #fff; border: 1px solid #dfe6e0; border-radius: 5px; cursor: pointer; padding: 2px; }.checkbox-label { margin-left: auto !important; }.dashboard input[type=checkbox], .dashboard input[type=range] { accent-color: var(--accent); }.dashboard input[type=range] { width: 100%; }.label-note { color: #a3afa5; font-size: 9px; float: right; }.dashboard textarea { resize: vertical; font-family: Consolas, monospace; font-size: 11px; line-height: 1.8; }.preview-column { display: grid; gap: 20px; position: sticky; top: 20px; }.preview-card { padding: 0; overflow: hidden; }.preview-card .card-heading { padding: 23px 23px 0; margin-bottom: 20px; }.preview-live { font-size: 8px; letter-spacing: 1px; color: #9dab9e; }.preview-screen { position: relative; height: 440px; margin: 0 16px; background: radial-gradient(ellipse at 20% 15%, #354b40, transparent 75%), linear-gradient(140deg, #20332e, #16221f); border-radius: 8px; overflow: hidden; }.preview-caption { position: absolute; top: 20px; left: 20px; font-size: 9px; letter-spacing: 2px; color: #7a9486; }.preview-screen iframe { position: absolute; bottom: 12px; left: 0; width: 100%; height: calc(100% - 50px); border: 0; }.empty-state { position: absolute; inset: 70px 0 0; display: flex; align-items: center; justify-content: center; flex-direction: column; color: #8ea497; pointer-events: none; }.empty-state > span { font-size: 30px; color: #668c78; margin-bottom: 23px; }.empty-state strong { font-size: 15px; color: #a6bbad; font-weight: 400; }.empty-state p { font-size: 11px; line-height: 2; text-align: center; color: #708e7c; }.preview-footer { display: flex; justify-content: space-between; padding: 18px 23px; font-size: 10px; color: #9ba99f; }.preview-footer a { color: #638976; }.obs-badge { font-size: 9px; border: 1px solid #e2e8e2; padding: 4px 7px; border-radius: 4px; color: #8b9d8f; }.url-box { display: flex; border: 1px solid #dce5dd; border-radius: 6px; background: #f6f9f6; align-items: center; padding: 10px; gap: 8px; }.url-box code { font-size: 11px; color: #6c8d77; overflow-wrap: anywhere; flex: 1; }.url-box button { border: 0; background: #e6efe7; color: #598166; padding: 7px 10px; font-size: 10px; }.obs-tip { display: flex; justify-content: space-between; margin: 18px 0 12px; font-size: 11px; color: #94a397; }.obs-tip strong { font-size: 11px; color: #607b68; font-weight: 500; }.privacy-note { display: flex; gap: 10px; padding: 0 10px; align-items: start; color: #9ca99d; }.privacy-note span { font-size: 22px; }.privacy-note p { margin: 0; font-size: 10px; line-height: 1.9; }.page-footer { border-top: 1px solid var(--line); padding-top: 20px; margin-top: 35px; display: flex; justify-content: space-between; font-size: 9px; color: #a1ada3; }.toast { border: 1px solid #d9e8dc; background: #edf6ef; color: #447256; padding: 12px 16px; border-radius: 8px; font-size: 12px; margin-bottom: 20px; }
@media (max-width: 1150px) { .sidebar { width: 180px; padding: 28px 14px; }.workspace { margin-left: 180px; padding: 0 25px 24px; }.columns { gap: 18px; grid-template-columns: minmax(320px, 1.1fr) minmax(300px, 1fr); }.card { padding: 20px; }.preview-card { padding: 0; }.field-row { gap: 12px; }.translation-flow { gap: 7px; } }
@media (max-width: 930px) { .sidebar { width: 70px; padding: 24px 14px; }.brand > span:not(.brand-mark), .side-label, .nav-item, .side-bottom { display: none; }.workspace { margin-left: 70px; }.columns { grid-template-columns: 1fr; }.preview-column { position: static; grid-row: 1; grid-template-columns: 1fr 1fr; }.preview-screen { height: 330px; }.privacy-note { grid-column: 1/-1; }.page-title h1 { font-size: 25px; } }
@media (max-width: 630px) { .sidebar { display: none; }.workspace { margin: 0; padding: 0 16px 20px; }.topbar { height: 56px; }.page-title { align-items: start; padding-top: 24px; }.page-title h1 { font-size: 23px; }.eyebrow { font-size: 7px; letter-spacing: 1px; }.page-title p { font-size: 11px; line-height: 1.7; }.page-title > button { padding: 9px; white-space: nowrap; font-size: 10px; }.preview-column { grid-template-columns: 1fr; }.preview-screen { height: 360px; }.field-row { grid-template-columns: 1fr; }.page-footer { display: block; line-height: 2; }.page-footer a { display: block; }.label-note { float: none; display: block; margin-top: 5px; } }
.translation-flow { flex-wrap: wrap; }.translation-flow strong { overflow-wrap: anywhere; }
.language-heading { display: flex; justify-content: space-between; margin-top: 22px; }.language-heading > span { color: #769786; font-size: 11px; }
.language-stack { list-style: none; padding: 0; margin: 0 0 12px; display: grid; gap: 8px; }
.language-stack li { display: flex; align-items: center; gap: 12px; padding: 12px; border: 1px solid #dce9e1; border-radius: 10px; background: linear-gradient(110deg, #f2f8f4, #fff); cursor: grab; }
.language-number { color: #6b9781; font-size: 12px; font-variant-numeric: tabular-nums; }.language-name { flex: 1; }.language-name strong { display: block; font-size: 13px; }.language-name small { display: block; color: #8b9d92; font-size: 10px; margin-top: 3px; }
.language-actions { display: flex; gap: 4px; }.language-actions button { min-width: 30px; height: 30px; border: 1px solid #e1e9e4; color: #527d66; background: #fff; }.language-actions button:disabled { cursor: default; opacity: .3; }
.add-language { display: flex; gap: 8px; }.add-language select { flex: 1; min-width: 0; }.add-language button { white-space: nowrap; }
.dashboard { background: radial-gradient(ellipse at 80% 0, #e7f0e9, transparent 45%), #f6f8f6; }
.page-title { border-radius: 16px; }.card { border-radius: 16px; box-shadow: 0 8px 30px #203c2f05; }
.preview-screen { background: radial-gradient(ellipse at 0 0, #375f50, transparent 70%), linear-gradient(145deg, #1c302a, #101c19); }
.dashboard button:focus-visible { outline: 2px solid #3e9673; outline-offset: 3px; }
.topbar { height: auto; min-height: 75px; gap: 16px; padding: 12px 0; flex-wrap: wrap; }
.topbar-tools { margin-left: auto; display: flex; align-items: center; gap: 20px; }
.dashboard .ui-language { display: flex; align-items: center; gap: 8px; margin: 0; white-space: nowrap; }
.dashboard .ui-language select { width: auto; min-width: 112px; padding: 8px 10px; background: #fff; cursor: pointer; }
.settings, .preview-column, .card, .page-title > div { min-width: 0; }
.page-title > button { flex-shrink: 0; }
.button-row { flex-wrap: wrap; }
.card-heading { gap: 12px; }.card-heading h2 { min-width: 0; }
.language-name { min-width: 0; overflow-wrap: anywhere; }
.preview-footer { gap: 12px; }.preview-footer a { flex-shrink: 0; }
.empty-state { padding: 0 16px; text-align: center; }
.nav-item span { flex-shrink: 0; }
@media (max-width: 1150px) { .topbar-tools .version { display: none; } }
@media (max-width: 630px) {
  .topbar { min-height: 60px; }.topbar .breadcrumb { display: none; }
  .topbar-tools { width: 100%; justify-content: flex-end; }
  .page-title { flex-direction: column; align-items: flex-start; }
}
</style>
