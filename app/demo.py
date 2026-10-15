"""Offline sample translations for every language offered by Google mode."""

DEMO_SAMPLES = [
    ("Mika", "こんにちは！配信楽しみにしていました 🌸", "你好！一直很期待这次直播 🌸", "ja"),
    ("Alex", "Hello from London! Love this stream 💚", "来自伦敦的问候！好喜欢这场直播 💚", "en"),
    ("小雨", "晚上好，今天也要加油呀！", "晚上好，今天也要加油呀！", "zh-Hans"),
    ("Sofia", "¡Qué bonito! Gracias por compartir ✨", "太漂亮了！谢谢分享 ✨", "es"),
    ("Min", "오늘 방송 정말 재밌어요!", "今天的直播真的很有趣！", "ko"),
    ("测试观众", "<script>alert('文本安全测试')</script>", "<script>alert('文本安全测试')</script>", "zh-Hans"),
]

# Fixed examples, never machine-translated or requested from an external service.
DEMO_TRANSLATIONS = {
    "zh-Hant": (
        "你好！一直很期待這次直播 🌸",
        "來自倫敦的問候！好喜歡這場直播 💚",
        "晚上好，今天也要加油呀！",
        "太漂亮了！謝謝分享 ✨",
        "今天的直播真的很有趣！",
    ),
    "en": (
        "Hello! I've been looking forward to this stream 🌸",
        "Hello from London! Love this stream 💚",
        "Good evening, keep it up today!",
        "How beautiful! Thanks for sharing ✨",
        "Today's stream is really fun!",
    ),
    "ja": (
        "こんにちは！配信楽しみにしていました 🌸",
        "ロンドンからこんにちは！この配信が大好きです 💚",
        "こんばんは、今日も頑張ってね！",
        "とてもきれい！シェアしてくれてありがとう ✨",
        "今日の配信は本当に楽しいです！",
    ),
    "ko": (
        "안녕하세요! 이번 방송을 기다리고 있었어요 🌸",
        "런던에서 인사해요! 이 방송 정말 좋아요 💚",
        "좋은 저녁이에요, 오늘도 힘내세요!",
        "정말 예뻐요! 공유해 주셔서 감사해요 ✨",
        "오늘 방송 정말 재밌어요!",
    ),
    "es": (
        "¡Hola! Tenía muchas ganas de ver esta transmisión 🌸",
        "¡Saludos desde Londres! Me encanta esta transmisión 💚",
        "¡Buenas noches, mucho ánimo para hoy!",
        "¡Qué bonito! Gracias por compartir ✨",
        "¡La transmisión de hoy es muy divertida!",
    ),
    "fr": (
        "Bonjour ! J'attendais cette diffusion avec impatience 🌸",
        "Bonjour de Londres ! J'adore cette diffusion 💚",
        "Bonsoir, bon courage pour aujourd'hui !",
        "C'est magnifique ! Merci pour le partage ✨",
        "La diffusion d'aujourd'hui est vraiment amusante !",
    ),
    "de": (
        "Hallo! Ich habe mich auf diesen Stream gefreut 🌸",
        "Grüße aus London! Ich liebe diesen Stream 💚",
        "Guten Abend, viel Erfolg auch heute!",
        "Wie schön! Danke fürs Teilen ✨",
        "Der heutige Stream macht wirklich Spaß!",
    ),
}


def demo_translation(index: int, target: str) -> str | None:
    _, original, chinese, source = DEMO_SAMPLES[index]
    supported = {"zh-Hans", *DEMO_TRANSLATIONS}
    if target not in supported:
        return None
    # Keep the markup safety sample literal in every language.
    if index == len(DEMO_SAMPLES) - 1 or target == source:
        return original
    if target == "zh-Hans":
        return chinese
    return DEMO_TRANSLATIONS[target][index]
