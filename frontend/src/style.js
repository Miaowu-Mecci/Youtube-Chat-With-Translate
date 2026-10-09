export function makeCSS(style) {
  return `/* YouTube OBS 双语弹幕 — 可粘贴到 OBS 自定义 CSS */
@layer yt, overlay;
@layer overlay {
body, yt-live-chat-renderer, yt-live-chat-ticker-renderer,
yt-live-chat-author-chip #author-name { background-color: transparent; }
body, yt-live-chat-item-list-renderer #item-scroller { overflow: hidden; }
yt-live-chat-renderer { --yt-live-chat-primary-text-color: ${style.color}; --yt-live-chat-secondary-text-color: ${style.color}; }
yt-live-chat-text-message-renderer { font-size: ${style.font_size}px; padding: 9px 16px; }
yt-live-chat-text-message-renderer #message { color: ${style.color}; font-size: ${style.font_size}px; line-height: 1.45; }
yt-live-chat-author-chip #author-name { font-size: ${Math.max(12, style.font_size - 3)}px; }
yt-live-chat-text-message-renderer .translation { display: block; color: ${style.translation_color}; font-size: ${style.font_size}px; line-height: 1.45; margin-top: 3px; white-space: pre-wrap; overflow-wrap: anywhere; }
yt-live-chat-text-message-renderer:has(.translation) #message { display: block; opacity: .72; font-size: ${Math.max(10, style.font_size - 3)}px; }
yt-live-chat-text-message-renderer #author-photo { display: ${style.show_avatar ? 'block' : 'none'}; }
yt-live-chat-text-message-renderer #message { white-space: pre-wrap; }
}
${style.custom_css || ''}`
}
