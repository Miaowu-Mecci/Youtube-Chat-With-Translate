import pytest

from app.youtube import SourceError, parse_source, map_item


@pytest.mark.parametrize('source', [
    'abcdefgh_-1', 'https://www.youtube.com/watch?v=abcdefgh_-1&t=3',
    'https://youtu.be/abcdefgh_-1?si=test', 'youtube.com/live/abcdefgh_-1',
    'https://m.youtube.com/watch?v=abcdefgh_-1', 'https://www.youtube.com/embed/abcdefgh_-1',
])
def test_parse_video(source):
    assert parse_source(source) == ('video', 'abcdefgh_-1')


@pytest.mark.parametrize('source', ['', 'https://evil.com/watch?v=abcdefgh_-1',
    'https://youtube.com.evil.com/watch?v=abcdefgh_-1', 'https://youtube.com/@channel/live',
    'https://youtube.com/watch?v=short', 'long_chat_id_123'])
def test_invalid_source(source):
    with pytest.raises(SourceError):
        parse_source(source)


def test_normalized_web_message_and_moderation_events():
    event = map_item({'id': 'one', 'snippet': {'type': 'textMessageEvent',
        'publishedAt': '2026-10-15T00:00:00Z', 'textMessageDetails': {'messageText': 'Hello 🌸'}},
        'authorDetails': {'displayName': 'Alice', 'isChatModerator': True}})
    assert event['message']['original'] == 'Hello 🌸'
    assert event['message']['role'] == 'moderator'
    assert map_item({'id': 'one', 'snippet': {'type': 'tombstone'}}) == {'type': 'delete', 'ids': ['one']}
    assert map_item({'snippet': {'type': 'chatEndedEvent'}}) == {'type': 'ended'}
