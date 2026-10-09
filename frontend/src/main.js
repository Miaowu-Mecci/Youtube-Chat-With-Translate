import Vue from 'vue'
import App from './App.vue'

Vue.config.ignoredElements = [/^yt-/]
document.documentElement.classList.toggle('overlay-mode', location.pathname === '/overlay')
new Vue({ render: h => h(App) }).$mount('#app')
