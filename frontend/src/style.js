export function makeCSS(style) {
  return `/* YouTube OBS 多语言弹幕 — 可粘贴到 OBS 自定义 CSS */
@layer yt, overlay;
@layer overlay {
body, yt-live-chat-renderer, yt-live-chat-ticker-renderer,
yt-live-chat-author-chip #author-name { background-color: transparent; }
body, yt-live-chat-item-list-renderer #item-scroller { overflow: hidden; }
yt-live-chat-renderer { --yt-live-chat-primary-text-color: ${style.color}; --yt-live-chat-secondary-text-color: ${style.color}; }
yt-live-chat-text-message-renderer { font-size: ${style.font_size}px; padding: 9px 16px; }
yt-live-chat-text-message-renderer #message { color: ${style.color}; font-size: ${style.font_size}px; line-height: 1.45; }
yt-live-chat-author-chip #author-name { font-size: ${Math.max(12, style.font_size - 3)}px; margin-right: 6px; }
yt-live-chat-text-message-renderer .translation { display: block; color: ${style.translation_color}; font-size: ${style.font_size}px; line-height: 1.45; margin-top: 3px; white-space: pre-wrap; overflow-wrap: anywhere; }
yt-live-chat-text-message-renderer { margin: 4px 8px; border-radius: 12px; background: #152a25bd; border: 1px solid #b1dcc21a; }
yt-live-chat-text-message-renderer .translation-list { padding: 4px 0 0 14px; margin: 6px 0 0; border-left: 2px solid #8de1cb55; list-style: none; }
yt-live-chat-text-message-renderer .translation-row { display: flex; gap: 8px; align-items: baseline; padding: 3px 0; }
yt-live-chat-text-message-renderer .translation-row::before { content: "·"; color: ${style.translation_color}; }
yt-live-chat-text-message-renderer .translation-language { color: ${style.translation_color}; font-size: 10px; opacity: .6; min-width: 38px; }
yt-live-chat-text-message-renderer .translation-placeholder { color: ${style.translation_color}; font-size: 12px; opacity: .5; }
yt-live-chat-text-message-renderer .translation-row .translation { margin: 0; flex: 1; min-width: 0; }
yt-live-chat-text-message-renderer #author-photo { display: ${style.show_avatar ? 'block' : 'none'}; }
yt-live-chat-text-message-renderer #message { white-space: pre-wrap; }
yt-live-chat-text-message-renderer .emote-part { display: inline; }
yt-live-chat-text-message-renderer .sticker-part { display: inline-block; max-width: 100%; }
yt-live-chat-text-message-renderer .emote-fallback { font-size: .8em; opacity: .75; }
yt-live-chat-text-message-renderer #message .emoji { margin: 0 2px; }
}
${style.custom_css || ''}`
}
