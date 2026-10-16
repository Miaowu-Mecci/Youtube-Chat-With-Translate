import Vue from 'vue'
import App from './App.vue'
import { installI18n } from './i18n'

installI18n()
Vue.config.ignoredElements = [/^yt-/]
document.documentElement.classList.toggle('overlay-mode', location.pathname === '/overlay')
new Vue({ render: h => h(App) }).$mount('#app')
