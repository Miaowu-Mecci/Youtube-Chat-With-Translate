<template>
  <overlay v-if="isOverlay" />
  <div v-else class="dashboard">
    <aside class="sidebar">
      <a class="brand" href="/"><span class="brand-mark">译</span><span>LiveChat<span class="brand-sub">YOUTUBE · OBS</span></span></a>
      <div class="side-label">工作空间</div>
      <a class="nav-item active" href="#connection"><span>◉</span> 直播弹幕</a>
      <a class="nav-item" href="#translation"><span>文</span> 双语翻译</a>
      <a class="nav-item" href="#appearance"><span>◐</span> 外观与样式</a>
      <div class="side-bottom"><span class="local-dot"></span> 本地运行<span class="side-note">你的直播，你的表达。</span></div>
    </aside>
    <main class="workspace">
      <header class="topbar"><span>工作空间 <span class="crumb">/</span> 直播弹幕</span><span class="version">LOCAL · v0.1</span></header>
      <div class="page-title"><div><div class="eyebrow">CONNECT WITHOUT LANGUAGE BARRIERS</div><h1>让每一句话，都被听懂<span>。</span></h1><p>将 YouTube 直播弹幕带入 OBS，让原文和译文一起出现。</p></div><button class="secondary" :disabled="busy" @click="action('demo')">▷ 体验演示</button></div>
      <div class="toast" role="status" v-if="notice">{{ notice }}</div>
      <div class="columns">
        <div class="settings">
          <section class="card" id="connection">
            <div class="card-heading"><h2><span class="step">01</span> 连接直播间</h2><span class="status-pill" :class="status.connection">{{ statusLabel }}</span></div>
            <label for="source">YouTube 直播链接 / ID</label>
            <input id="source" v-model="form.source" placeholder="https://www.youtube.com/watch?v=…" autocomplete="off">
            <div class="field-row"><div><label for="source-type">输入类型</label><select id="source-type" v-model="form.source_type"><option value="auto">自动识别</option><option value="video">视频链接 / 视频 ID</option><option value="chat">liveChatId</option></select></div><div><label for="youtube-key">YouTube API Key <span v-if="youtubeKeySet" class="saved">已保存</span></label><input id="youtube-key" v-model="youtubeKey" type="password" :placeholder="youtubeKeySet ? '留空保留已保存的 Key' : '输入 API Key'" autocomplete="new-password"></div></div>
            <div class="helper-row"><a href="https://console.cloud.google.com/apis/library/youtube.googleapis.com" target="_blank" rel="noreferrer">启用 YouTube Data API ↗</a><button v-if="youtubeKeySet" class="text-button" @click="clearSecret('youtube_key')">清除 Key</button></div>
            <div class="button-row"><button class="primary" :disabled="busy" @click="action('connect', true)">连接直播间 <span>→</span></button><button class="secondary" :disabled="busy" @click="action('disconnect')">断开</button></div>
            <p class="connection-message">{{ status.message }}</p>
          </section>

          <section class="card" id="translation">
            <div class="card-heading"><h2><span class="step">02</span> 双语翻译</h2><label class="switch"><input type="checkbox" v-model="form.translation_enabled" aria-label="开启翻译"><span></span></label></div>
            <p class="card-description">原文即时出现，译文随后补上。让不同语言的观众一起参与。</p>
            <label for="provider">翻译服务</label><select id="provider" v-model="form.translation_provider" @change="providerChanged"><option value="google_web">Google 翻译 · 免 Key（实验性）</option><option value="azure">Azure Translator · F0 免费档</option></select>
            <p v-if="form.translation_provider === 'google_web'" class="small">免账号、免 Key；接口可能限流，失败时保留原文。</p>
            <label for="language">主播的目标语言</label><select id="language" v-model="form.target_language"><option v-for="language in languages" :key="language.code" :value="language.code">{{ language.name }} · {{ language.code }}</option></select>
            <div class="translation-flow"><span>自动识别观众语言</span><span>→</span><strong>{{ targetName }}</strong><span class="flow-badge">译文 + 原文</span></div>
            <div v-if="form.translation_provider === 'azure'" class="field-row"><div><label for="azure-key">Azure Translator Key <span v-if="azureKeySet" class="saved">已保存</span></label><input id="azure-key" v-model="azureKey" type="password" :placeholder="azureKeySet ? '留空保留已保存的 Key' : '输入 F0 资源 Key'" autocomplete="new-password"></div><div><label for="region">资源区域</label><input id="region" v-model="form.azure_region" placeholder="例如 eastasia" autocomplete="off"></div></div>
            <div v-if="form.translation_provider === 'azure'" class="helper-row"><a href="https://portal.azure.com/" target="_blank" rel="noreferrer">创建 Translator F0 免费资源 ↗</a><button v-if="azureKeySet" class="text-button" @click="clearSecret('azure_key')">清除 Key</button></div>
            <div v-if="form.translation_provider === 'azure'" class="info-note"><span>ⓘ</span><span>使用 Azure F0 免费档，每月 200 万字符。额度不足或翻译失败时，弹幕继续显示原文。</span></div>
            <div class="button-row"><button class="secondary" :disabled="busy" @click="testTranslation">保存并测试翻译</button><button class="secondary" :disabled="busy" @click="resumeTranslation">恢复翻译</button></div>
            <p class="small">测试会向选定服务发送固定外语样例，不需要连接 YouTube。测试翻译不受弹幕翻译开关控制。</p>
            <p class="connection-message" role="status" aria-label="翻译测试结果" v-if="testResult">{{ testResult }}</p>
            <p class="connection-message">{{ status.translation_message }}</p>
            <p class="small" v-if="languageNotice">{{ languageNotice }}</p>
          </section>

          <section class="card" id="appearance">
            <div class="card-heading"><h2><span class="step">03</span> 外观与样式</h2><span class="small">实时预览</span></div>
            <div class="field-row"><div><label for="font-size">字号 <span class="saved">{{ form.style.font_size }} px</span></label><input id="font-size" type="range" min="10" max="72" v-model.number="form.style.font_size"></div><div><label for="max-messages">保留消息数量</label><input id="max-messages" type="number" min="10" max="500" v-model.number="form.style.max_messages"></div></div>
            <div class="color-row"><label>原文颜色 <input aria-label="原文颜色" type="color" v-model="form.style.color"></label><label>译文颜色 <input aria-label="译文颜色" type="color" v-model="form.style.translation_color"></label><label class="checkbox-label"><input type="checkbox" v-model="form.style.show_avatar"> 显示头像</label></div>
            <label for="custom-css">自定义 CSS <span class="label-note">兼容 blivechat 普通弹幕选择器</span></label>
            <textarea id="custom-css" v-model="form.style.custom_css" rows="5" spellcheck="false" placeholder=".translation { font-weight: 600; }"></textarea>
            <div class="button-row"><button class="primary" :disabled="busy" @click="save()">保存设置</button><button class="secondary" @click="copy(css, 'CSS 已复制')">复制 CSS</button></div>
          </section>
        </div>

        <div class="preview-column">
          <section class="card preview-card"><div class="card-heading"><h2>评论栏预览</h2><span class="preview-live"><span class="local-dot"></span> LIVE PREVIEW</span></div><div class="preview-screen"><div class="preview-caption">YOUR STREAM, CONNECTED.</div><iframe ref="preview" src="/overlay" title="OBS 评论栏实时预览" @load="draftPreview"></iframe><div v-if="!hasMessages" class="empty-state"><span>文 ↔ A</span><strong>跨越语言，开始对话</strong><p>连接直播间或点击「体验演示」<br>这里将展示你的双语评论栏</p></div></div><div class="preview-footer"><span>透明背景 · 译文在上，原文在下</span><a href="/overlay" target="_blank" rel="noreferrer">独立预览 ↗</a></div></section>
          <section class="card obs-card"><div class="card-heading"><h2>添加到 OBS</h2><span class="obs-badge">浏览器源</span></div><p class="card-description">在 OBS 中添加「浏览器」源，粘贴下方地址。</p><div class="url-box"><code>{{ overlayUrl }}</code><button aria-label="复制 OBS 地址" @click="copy(overlayUrl, 'OBS 地址已复制')">复制</button></div><div class="obs-tip"><span>建议尺寸</span><strong>480 × 720</strong></div><p class="small">OBS 自定义 CSS 保留透明背景设置即可。页面不包含控制按钮，多个浏览器源共享同一直播连接。</p></section>
          <div class="privacy-note"><span>⌁</span><p>密钥只保存在本地。开启翻译后，弹幕文本会发送至选定的 Google 或 Azure 服务。演示模式不消耗额度。</p></div>
        </div>
      </div>
      <footer class="page-footer"><span>Made for conversations, in every language.</span><a href="https://github.com/xfgryujk/blivechat" target="_blank" rel="noreferrer">渲染组件源自 blivechat · MIT ↗</a></footer>
    </main>
  </div>
</template>

<script>
import Overlay from './Overlay.vue'
import { makeCSS } from './style'
const initial = { source: '', source_type: 'auto', translation_enabled: false, translation_provider: 'google_web', azure_region: '', target_language: 'zh-Hans',
  style: { font_size: 24, color: '#ffffff', translation_color: '#8de1cb', show_avatar: true, max_messages: 100, custom_css: '' } }
export default {
  components: { Overlay },
  data: () => ({ isOverlay: location.pathname === '/overlay', form: JSON.parse(JSON.stringify(initial)),
    youtubeKey: '', azureKey: '', youtubeKeySet: false, azureKeySet: false,
    status: { connection: 'idle', message: '尚未连接。', translation_message: '翻译未开启。' },
    testResult: '', languages: [{ code: 'zh-Hans', name: '简体中文' }], languageNotice: '', notice: '', busy: false, hasMessages: false,
    socket: null, retryTimer: null, stopped: false, ready: false }),
  computed: {
    overlayUrl() { return `${location.origin}/overlay` },
    css() { return makeCSS(this.form.style) },
    targetName() { return this.languages.find(item => item.code === this.form.target_language)?.name || this.form.target_language },
    statusLabel() { return { idle: '未连接', connecting: '连接中', connected: '已连接', reconnecting: '重连中', demo: '演示中', error: '连接异常', ended: '已结束' }[this.status.connection] || '未连接' }
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
      const { youtube_key_set, azure_key_set, ...form } = config
      this.form = form
      this.youtubeKeySet = youtube_key_set
      this.azureKeySet = azure_key_set
      this.youtubeKey = ''; this.azureKey = ''
    },
    async loadLanguages() {
      const provider = this.form.translation_provider
      try {
        const data = await this.api(`/api/languages?provider=${provider}`)
        if (provider !== this.form.translation_provider) return
        this.languages = data.languages
        this.languageNotice = data.message || ''
        if (!this.languages.some(item => item.code === this.form.target_language)) {
          this.form.target_language = 'zh-Hans'
          this.languageNotice = '当前服务不支持原目标语言，已改为简体中文；请保存设置。'
        }
      } catch { this.languageNotice = '语言列表暂不可用，请刷新页面重试。' }
    },
    async providerChanged() {
      this.testResult = ''
      await this.loadLanguages()
    },
    async testTranslation() {
      this.busy = true
      this.testResult = ''
      try {
        await this.persist()
        const result = await this.api('/api/translation/test', 'POST')
        this.testResult = `测试成功：${result.original} → ${result.translation}`
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
      if (this.youtubeKey) payload.youtube_key = this.youtubeKey.trim()
      if (this.azureKey) payload.azure_key = this.azureKey.trim()
      this.loadConfig(await this.api('/api/config', 'PUT', payload))
    },
    async save() {
      this.busy = true
      try { await this.persist(); this.notice = '设置已保存，OBS 页面已同步。' } catch (error) { this.notice = error.message }
      finally { this.busy = false }
    },
    async action(name, saveFirst = false) {
      this.busy = true
      try { if (saveFirst) await this.persist(); await this.api(`/api/${name}`, 'POST'); this.notice = name === 'demo' ? '演示模式已启动，简体中文译文为固定样例。' : '' }
      catch (error) { this.notice = error.message }
      finally { this.busy = false }
    },
    async clearSecret(key) {
      try { this.loadConfig(await this.api('/api/config', 'PUT', { [key]: '' })); this.notice = 'Key 已清除。' } catch (error) { this.notice = error.message }
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
</style>
