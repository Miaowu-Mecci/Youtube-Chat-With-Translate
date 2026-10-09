<template>
  <div class="overlay-root"><chat-renderer ref="renderer" :maxNumber="config.style.max_messages" /></div>
</template>

<script>
import ChatRenderer from './components/ChatRenderer/index.vue'
import { makeCSS } from './style'

const defaults = { font_size: 24, color: '#ffffff', translation_color: '#8de1cb', show_avatar: true, max_messages: 100, custom_css: '' }
export default {
  components: { ChatRenderer },
  data: () => ({ config: { style: { ...defaults } }, session: '', socket: null, timer: null, stopped: false, cssNode: null }),
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
        privilegeType: 0, repeated: 1, content: message.original, translation: message.translation,
        contentParts: [{ type: 0, text: message.original }] }
    },
    connect() {
      const socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`)
      this.socket = socket
      socket.onmessage = ({ data }) => {
        const event = JSON.parse(data)
        const renderer = this.$refs.renderer
        if (event.type === 'snapshot') {
          this.session = event.session
          this.config = event.config
          this.applyStyle(this.config.style)
          renderer.clearMessages()
          renderer.addMessages(event.messages.map(this.adapt))
          // Parent draft styles are restored after any snapshot.
          window.parent !== window && window.parent.postMessage({ type: 'preview-ready' }, location.origin)
        } else if (event.session === this.session) {
          if (event.type === 'message') renderer.addMessage(this.adapt(event.message))
          else if (event.type === 'translation') renderer.updateMessage(event.id, { translation: event.translation })
          else if (event.type === 'delete') renderer.delMessages(event.ids)
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
</style>
