<template>
  <div class="overlay-root"><chat-renderer ref="renderer" :maxNumber="config.style.max_messages">
    <div v-if="ready" slot="start" class="overlay-start" role="status">{{ $t('弹幕姬开始工作') }}</div>
  </chat-renderer></div>
</template>

<script>
import ChatRenderer from './components/ChatRenderer/index.vue'
import { makeCSS } from './style'
import { contentParts } from './content'

const defaults = { font_size: 24, color: '#ffffff', translation_color: '#8de1cb', show_avatar: true, max_messages: 100, custom_css: '' }
export default {
  components: { ChatRenderer },
  data: () => ({ config: { style: { ...defaults } }, session: '', ready: false, visibleIds: new Set(), socket: null, timer: null, stopped: false, cssNode: null }),
  mounted() {
    this.cssNode = document.createElement('style')
    this.cssNode.id = 'overlay-custom-css'
    document.head.appendChild(this.cssNode)
    this.applyStyle(this.config.style)
    window.addEventListener('message', this.previewStyle)
    this.connect()
  },
  beforeDestroy() {
    this.stopped = true
    clearTimeout(this.timer)
    this.socket?.close()
    this.cssNode?.remove()
    window.removeEventListener('message', this.previewStyle)
  },
  methods: {
    applyStyle(style) { this.cssNode.textContent = makeCSS(style) },
    previewStyle(event) {
      if (event.origin === location.origin && event.source === window.parent && event.data?.type === 'preview-style') {
        this.config.style = event.data.style
        this.applyStyle(event.data.style)
      }
    },
    adapt(message) {
      return { id: message.id, type: 0, authorName: message.author, avatarUrl: message.avatar,
        time: new Date(message.time), authorType: { normal: 0, member: 1, moderator: 2, owner: 3 }[message.role] || 0,
        privilegeType: 0, repeated: 1, content: message.original, translation: message.translation, translations: message.translations || [],
        contentParts: contentParts(message) }
    },
    syncSnapshot(event) {
      const renderer = this.$refs.renderer
      this.config = event.config
      this.applyStyle(this.config.style)
      if (!this.ready || event.session !== this.session) {
        // Opening this surface starts a new display; cached chat is never replayed.
        renderer.clearMessages()
        this.visibleIds.clear()
      } else {
        // Settings changes and reconnects update only rows received by this surface.
        // Never feed a snapshot back into the smooth-scrolling message queue.
        const current = new Map(event.messages.map(message => [message.id, message]))
        const removed = [...this.visibleIds].filter(id => !current.has(id))
        for (const id of removed) this.visibleIds.delete(id)
        if (removed.length) renderer.delMessages(removed)
        for (const id of this.visibleIds) renderer.updateMessage(id, this.adapt(current.get(id)))
      }
      this.session = event.session
      this.ready = true
      this.$nextTick(() => renderer.onContentResize())
    },
    connect() {
      const socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`)
      this.socket = socket
      socket.onmessage = ({ data }) => {
        const event = JSON.parse(data)
        const renderer = this.$refs.renderer
        if (event.type === 'snapshot') {
          this.syncSnapshot(event)
          // Parent draft styles are restored after any snapshot.
          window.parent !== window && window.parent.postMessage({ type: 'preview-ready' }, location.origin)
        } else if (event.session === this.session) {
          if (event.type === 'message') {
            const message = this.adapt(event.message)
            if (this.visibleIds.has(message.id)) renderer.updateMessage(message.id, message)
            else {
              this.visibleIds.add(message.id)
              renderer.addMessage(message)
              while (this.visibleIds.size > this.config.style.max_messages) this.visibleIds.delete(this.visibleIds.values().next().value)
            }
          } else if (event.type === 'translation' && this.visibleIds.has(event.id)) {
            renderer.updateMessage(event.id, { translation: event.translation, translations: event.translations || [] })
          } else if (event.type === 'delete') {
            const ids = event.ids.filter(id => this.visibleIds.delete(id))
            if (ids.length) renderer.delMessages(ids)
          }
        }
      }
      socket.onclose = () => { if (!this.stopped) this.timer = setTimeout(this.connect, 1500) }
      socket.onerror = () => socket.close()
    }
  }
}
</script>

<style>
html, body, #app { margin: 0; padding: 0; }
.overlay-mode, .overlay-mode body, .overlay-mode #app, .overlay-root { width: 100%; height: 100%; background: transparent; }
.overlay-mode body { overflow: hidden; font-family: "Segoe UI", "Microsoft YaHei", sans-serif; }
.overlay-start { margin: 12px 16px; padding: 8px 12px; border-left: 2px solid #8de1cb; color: var(--yt-live-chat-secondary-text-color, #fff); font-size: 14px; line-height: 1.5; background: #152a25bd; border-radius: 0 8px 8px 0; }
</style>
