# YouTube OBS Multilingual Chat

[简体中文](README.md) | **English** | [日本語](README.ja.md)

Fetch public YouTube live chat for free and translate messages into multiple languages using Google Translate's keyless web endpoint. Display originals and translations in your preferred order in a transparent OBS browser source. Supports channel emotes, image emoji and stickers.

**v0.5.0** adds Chinese, Japanese and English interfaces while keeping free chat collection and keyless Google Translate. Download the Windows version from the [v0.5.0 Release](https://github.com/Miaowu-Mecci/Youtube-Chat-With-Translate/releases/tag/v0.5.0). It includes an EXE, a ZIP with documentation and licenses, and SHA-256 checksums. Running the EXE does not require Python, Node.js or Git.

## Interface language

Use the **Language** dropdown at the top right to select **简体中文 / 日本語 / English**. Buttons, settings, target-language names, status messages, diagnostics, notifications and accessibility labels follow your choice. The interface translations are bundled locally; they do not use Google Translate or require a network connection.

On first launch, the interface uses the first supported language in your browser preferences, falling back to Chinese. Your manual choice is saved in the current browser and survives refreshes and reopening. If browser storage is disabled, you can still switch languages for the current page. Interface language is independent of chat translation targets: switching it does not change stream settings, send translation requests, or alter original messages or completed translations.

Previews and open overlays on the same origin in the same browser update immediately, without reloading or replaying messages. OBS browser sources have separate storage and do not share language preferences with your external browser. Interface language switching is available from v0.5.0.

## Quick start

### Windows EXE — recommended

1. Download `YouTubeOBSChat.exe` or the ZIP with documentation and licenses from the [v0.5.0 Release](https://github.com/Miaowu-Mecci/Youtube-Chat-With-Translate/releases/tag/v0.5.0). Extract the ZIP before running. No Python, Node.js or Git installation is needed.
2. Close any older instance, then double-click the EXE. The settings page opens automatically. Keep the terminal window open. You can also visit `http://127.0.0.1:12450` manually.
3. Click **Try demo** to preview fixed translations in eight languages and image emotes offline. The demo does not contact YouTube or translation services.
4. Paste an ongoing YouTube live video URL or an 11-character video ID, then click **Connect to live chat**.
5. Enable translation, add and reorder target languages, and save settings. Use **Save & test translation** to check access to Google before connecting.
6. In OBS, add a **Browser** source with URL `http://127.0.0.1:12450/overlay`. The recommended size is 480 × 720.

No API key is needed, and there is no provider or connection-mode selector. Language selection, ordering, appearance, the translation toggle and diagnostic controls remain available.

### Run from source

Only source installations require Python 3.11+ and Node.js 22+. Reopen your terminal after installing them. On Windows, run `install.cmd` to install dependencies and build the frontend, then run `start.cmd` and open `http://127.0.0.1:12450`.

For other platforms or manual installation:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cd frontend
npm ci
npm run build
cd ..
.venv/bin/python main.py --no-browser
```

The application listens only on the local loopback interface. Use `--port 12460` to change the port. Set `YTCHAT_DATA_DIR` to choose a data directory; source installations default to `data/`, while the Windows EXE uses `%LOCALAPPDATA%\YouTubeOBSChat\`. The app does not automatically connect to a stream at startup.

Each overlay, including the settings preview, starts with **Chat overlay is ready** and displays only messages received after that page opens or refreshes. It does not replay cached chat. Refreshing one page does not clear other pages or interrupt the live connection. Settings changes and reconnects update existing rows without replaying history; messages accumulated while disconnected are not replayed. The startup marker means the display is ready. Check the settings page for the actual stream connection status.

## Free live chat collection

Accepts video links such as `watch?v=…`, `youtu.be/…`, `youtube.com/live/…`, and 11-character video IDs. Collection follows the webpage's continuation tokens and polling intervals. Multiple previews and OBS sources share one upstream connection. Message deduplication, reconnection with continuation, deletion and author-ban handling are supported.

Only messages posted after clicking **Connect to live chat** are kept, including new messages posted while the connection is being established. Earlier history is neither displayed nor queued for translation. Automatic reconnects retain the session's starting point; a manual reconnect sets a new one. Keep your system clock synchronized.

Only public, ongoing live video chats are supported. Private streams, chat replays, `liveChatId`, automatically finding a stream from a channel homepage, and sending messages are not supported. Collection uses an unofficial web protocol and may fail due to sign-in or age restrictions, verification challenges, consent pages, regional or network restrictions, rate limits, or webpage changes.

If the standalone chat page lacks bootstrap data, the app tries the watch page. Errors distinguish proxy failures, sign-in or verification requirements, offline streams and protocol parsing failures. Parsing diagnostics include HTTP status, response type, and whether initial markers and chat tokens were found. They do not include cookies or page bodies.

If your browser can show chat while signed out but the app cannot connect, check whether both use the same proxy route. YouTube collection uses httpx; Google translation uses curl_cffi/libcurl. Each follows the `HTTPS_PROXY` / `HTTP_PROXY` environment variables it supports. When reporting an issue, include the complete diagnostic message shown in the interface.

## Multilingual translation

Supports Simplified Chinese, Traditional Chinese, English, Japanese, Korean, Spanish, French and German, with up to eight targets at once. Drag language cards or use ↑ ↓ to reorder them. You can also remove all languages. Saving syncs settings to the preview and all OBS pages. With no targets selected, only originals are displayed: no translation requests, translation rows or placeholders are created. The demo follows this setting too. Add a language and save to restore translation.

Translation rows show content only, without language codes such as `zh-Hans`, `en` or `ja`. For example, selecting Chinese and English for a message containing “你好” displays:

```text
XXX: 你好
  · 你好
  · Hello
```

Original messages appear immediately. Each translation is added to its original row when ready, without reordering messages. A translation matching the source text still gets its own row. Reordering languages reuses completed results. Adding or removing languages, or toggling translation, cancels old jobs and updates retained messages without reconnecting the stream.

The Google web endpoint requires no account or API key, but it is unofficial and provides no fixed free quota or availability guarantee. Requests share one worker, a minimum interval of one second, a queue of up to 200 jobs, and a five-second request timeout. Identical text and target-language requests are coalesced and cached. More languages mean longer waits. HTTP 429 triggers a 60-second cooldown; three consecutive rate-limit responses pause translation. HTTP 403, verification challenges and response-format changes also pause it.

Failures preserve originals and any successful translations. **Resume translation** retries only unfinished languages for retained messages and cannot bypass a rate-limit cooldown. **Save & test translation** checks each selected target without needing a YouTube connection, even if chat translation is turned off. Test and resume controls are disabled when no target languages are selected.

The demo uses fixed local samples for all eight languages and makes no external requests. A successful demo does not prove that live Google or YouTube services are reachable. With live translation enabled, the text portion of messages is sent to Google.

## Emotes and stickers

YouTube image emoji and channel or member emotes retain their original order, including repeated emotes and mixed text. Emotes in paid messages and Super Sticker images are supported. Payment amounts and gift or membership cards are not reproduced. Unicode emoji display normally.

Emotes scale with the font size; sticker dimensions are bounded. Expired or failed images fall back to their name or description. Only natural text is translated: image URLs and emote names are not sent for translation. Image-only messages do not create translation jobs or a set of “Skipped” rows. Image loading triggers a chat layout update.

Only HTTPS YouTube/Google image CDN URLs supplied in messages are used. Arbitrary image links are not expanded. Uploads, OCR and image translation are not provided. Common domains include `*.ggpht.com`, `*.googleusercontent.com`, `*.gstatic.com` and `*.ytimg.com`. The demo's first message uses a local flower image that needs no network access.

## Appearance and configuration

Preview changes to font size, original and translation colors, avatars and message retention. Saving applies them to OBS. Use `.translation` for translated text and `#message` for originals. Example selectors:

```css
yt-live-chat-renderer { background: transparent; }
yt-live-chat-text-message-renderer { padding: 10px 16px; }
yt-live-chat-author-chip #author-name { font-weight: bold; }
.translation { color: #8de1cb; font-weight: 600; }
```

Regular CSS can override the default CSS layer. OBS custom CSS follows normal browser cascade rules. A recent OBS browser source with `@layer` and `:has()` support is required.

Settings are stored as `config.json` in the data directory. Loading older settings ignores removed connection modes, keys, providers and regions while preserving the stream URL, supported target languages, ordering and appearance. The next save removes obsolete fields. Unsupported legacy languages are filtered out; if a nonempty legacy list loses all its entries, Simplified Chinese is used. An intentionally saved empty list stays empty and displays originals only.

Chat history is held only in memory and is lost on restart. Up to 500 messages are retained. Deduplication IDs and deletion IDs are each limited to 10,000 entries. YouTube may not send deletion events immediately, so real-time deletion synchronization is not guaranteed.

## Development and building

```sh
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
cd frontend
npm run build
npx playwright install chromium
npm test
```

Browser tests use an isolated temporary data directory and local server. They do not read user settings or consume external translation requests. No gRPC/protobuf installation or code generation is required. See [VALIDATION.md](VALIDATION.md) for validation records in Chinese.

Run `build-exe.cmd` on Windows to build `dist/YouTubeOBSChat.exe` and run its startup smoke test. Windows executables must be built on Windows; Linux cannot directly produce this Windows EXE. Packages include the frontend, offline image sample, documentation and licenses, without user data.

Release tags and GitHub Releases are created only when the user explicitly requests a release. Routine source edits, commits and pushes do not publish one.

## Local API

| Endpoint | Purpose |
| --- | --- |
| `GET /api/config`, `PUT /api/config` | Read and save settings |
| `POST /api/connect`, `POST /api/disconnect` | Connect or stop live chat |
| `POST /api/demo` | Start the offline demo |
| `GET /api/status` | Connection status and translation progress |
| `GET /api/languages` | Eight Google target languages |
| `POST /api/translation/test` | Test all selected targets |
| `POST /api/translation/resume` | Resume unfinished translations |
| `WS /ws` | Snapshots, originals, translations, deletions and status events |

A message's `content_parts` contains ordered text, emote and sticker parts. `translations` contains ordered language results. Language codes remain in the data and HTML attributes but are not displayed before translated messages.

## License

New project code is licensed under MIT. The renderer reuses MIT-licensed code from blivechat. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and [licenses/](licenses/) for protocol research references and third-party notices.
