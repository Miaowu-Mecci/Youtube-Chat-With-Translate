const imageDomains = ['ggpht.com', 'googleusercontent.com', 'gstatic.com', 'ytimg.com']
function imageURL(value) {
  if (value === '/emotes/sakura.svg') return value
  try {
    const url = new URL(value)
    if (url.protocol === 'https:' && !url.username && !url.password && (!url.port || url.port === '443') &&
      imageDomains.some(domain => url.hostname === domain || url.hostname.endsWith(`.${domain}`))) return url.href
  } catch {}
  return ''
}
const dimension = (value, fallback) => Number.isFinite(Number(value)) && Number(value) > 0 ? Math.min(512, Number(value)) : fallback

export function contentParts(message) {
  if (!Array.isArray(message.content_parts)) return [{ type: 0, text: message.original }]
  const parts = message.content_parts.slice(0, 512).flatMap(part => {
    if (!part || typeof part.text !== 'string') return []
    if (part.type === 'text') return [{ type: 0, text: part.text }]
    if (part.type !== 'emoji' && part.type !== 'sticker') return []
    const url = imageURL(part.url)
    if (!url) return [{ type: 0, text: part.text || '[表情]' }]
    const size = part.type === 'sticker' ? 128 : 24
    return [{ type: 1, kind: part.type, text: part.text || '[表情]', url,
      width: dimension(part.width, size), height: dimension(part.height, size) }]
  })
  return parts.length ? parts : [{ type: 0, text: message.original }]
}
