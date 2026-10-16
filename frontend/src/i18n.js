import Vue from 'vue'
import { messages } from './locales/messages'
import { systemMessages } from './locales/system'

export const LOCALE_KEY = 'ytchat.uiLanguage'
export const locales = [{ code: 'zh-CN', name: '简体中文' }, { code: 'ja', name: '日本語' }, { code: 'en', name: 'English' }]
const catalog = { ...messages, ...systemMessages }
const aliases = { 'chat.moderator': '管理员', 'chat.guardLevel1': '会员', 'chat.guardLevel2': '会员', 'chat.guardLevel3': '会员' }
const supported = value => locales.some(locale => locale.code === value)

function browserLocale() {
  const languages = typeof navigator === 'undefined' ? [] : navigator.languages || [navigator.language]
  for (const language of languages) {
    const code = language?.toLowerCase().split('-')[0]
    if (code === 'zh') return 'zh-CN'
    if (code === 'ja' || code === 'en') return code
  }
  return 'zh-CN'
}

function initialLocale() {
  try {
    const saved = localStorage.getItem(LOCALE_KEY)
    if (supported(saved)) return saved
  } catch { /* Storage may be disabled in an embedded browser. */ }
  return browserLocale()
}

export const languageState = Vue.observable({ locale: initialLocale() })
export function t(key, values = {}) {
  key = aliases[key] || key
  const locale = languageState.locale
  const text = locale === 'zh-CN' ? key : catalog[key]?.[locale === 'en' ? 0 : 1] ?? key
  return text.replace(/\{(\w+)\}/g, (match, name) => String(values[name] ?? match))
}

function updateDocument() {
  if (typeof document === 'undefined') return
  document.documentElement.lang = languageState.locale
  document.title = t('YouTube OBS 多语言弹幕')
}

export function setLocale(locale) {
  if (!supported(locale)) return
  languageState.locale = locale
  try { localStorage.setItem(LOCALE_KEY, locale) } catch { /* Keep the choice for this page. */ }
  updateDocument()
}

function diagnostics(text) {
  return text.replace(/(聊天页|观看页) HTTP (\d+)\/(HTML|JSON|纯文本|未知类型)，初始标记(有|无)，解析(成功|失败)，聊天令牌(有|无)/g,
    (_, stage, status, kind, marker, parsed, token) => t('{stage} HTTP {status}/{kind}，初始标记{marker}，解析{parsed}，聊天令牌{token}',
      { stage: t(stage), status, kind: t(kind), marker: t(marker), parsed: t(parsed), token: t(token) }))
}

const diagnosticPrefixes = Object.keys(systemMessages).filter(key => key.length > 20).sort((a, b) => b.length - a.length)
// Localize only interface messages, never original chat or translated content.
export function uiMessage(value) {
  if (!value) return ''
  if (typeof value === 'object') return t(value.key, value.values)
  if (catalog[value]) return t(value)
  const prefix = diagnosticPrefixes.find(key => value.startsWith(key))
  if (prefix) return t(prefix) + diagnostics(value.slice(prefix.length))
  return value
}

export const i18n = { t }
export function installI18n() {
  Vue.prototype.$t = t
  Vue.prototype.$uiMessage = uiMessage
}

if (typeof window !== 'undefined') {
  window.addEventListener('storage', event => {
    if (event.key !== LOCALE_KEY && event.key !== null) return
    languageState.locale = supported(event.newValue) ? event.newValue : browserLocale()
    updateDocument()
  })
}
updateDocument()
