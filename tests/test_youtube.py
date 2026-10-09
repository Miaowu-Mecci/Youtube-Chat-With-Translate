import grpc
import httpx
import pytest
from google.protobuf.json_format import MessageToDict

from app.proto import stream_list_pb2 as pb
from app.proto import stream_list_pb2_grpc as rpc
from app.youtube import YouTubeSource, SourceError, parse_source, map_item, grpc_error


@pytest.mark.parametrize('source', [
    'abcdefgh_-1', 'https://www.youtube.com/watch?v=abcdefgh_-1&t=3',
    'https://youtu.be/abcdefgh_-1?si=test', 'youtube.com/live/abcdefgh_-1',
    'https://m.youtube.com/watch?v=abcdefgh_-1', 'https://www.youtube.com/embed/abcdefgh_-1',
])
def test_parse_video(source):
    assert parse_source(source) == ('video', 'abcdefgh_-1')


def test_explicit_chat_id_avoids_11_character_ambiguity():
    assert parse_source('abcdefgh_-1', 'chat') == ('chat', 'abcdefgh_-1')
    assert parse_source('long_chat_id_123') == ('chat', 'long_chat_id_123')


@pytest.mark.parametrize('source', ['', 'https://evil.com/watch?v=abcdefgh_-1',
                                    'https://youtube.com.evil.com/watch?v=abcdefgh_-1',
                                    'https://youtube.com/@channel/live', 'https://youtube.com/watch?v=short'])
def test_invalid_source(source):
    with pytest.raises(SourceError):
        parse_source(source)


async def test_resolve_and_sanitized_quota_errors():
    def response(request):
        assert request.url.params['part'] == 'liveStreamingDetails'
        return httpx.Response(200, json={'items': [{'liveStreamingDetails': {'activeLiveChatId': 'CHAT'}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
        assert await YouTubeSource(client).resolve('abcdefgh_-1', 'auto', 'SECRET') == 'CHAT'
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(
        403, json={'error': {'errors': [{'reason': 'quotaExceeded'}], 'message': 'SECRET'}}))) as client:
        with pytest.raises(SourceError) as error:
            await YouTubeSource(client).resolve('abcdefgh_-1', 'auto', 'SECRET')
        assert error.value.code == 'quota_exhausted'
        assert 'SECRET' not in str(error.value)


def test_official_protobuf_mapping():
    item = pb.LiveChatMessage(id='m1')
    item.snippet.type = pb.LiveChatMessageSnippet.TypeWrapper.TEXT_MESSAGE_EVENT
    item.snippet.published_at = '2026-10-09T00:00:00Z'
    item.snippet.text_message_details.message_text = '<b>Hello 🌸</b>'
    item.author_details.channel_id = 'author-id'
    item.author_details.display_name = 'Alice'
    item.author_details.profile_image_url = 'https://example.com/avatar'
    item.author_details.is_chat_moderator = True
    event = map_item(MessageToDict(item))
    assert event['message']['original'] == '<b>Hello 🌸</b>'
    assert event['message']['role'] == 'moderator'
    item.snippet.type = pb.LiveChatMessageSnippet.TypeWrapper.USER_BANNED_EVENT
    item.snippet.user_banned_details.banned_user_details.channel_id = 'author-id'
    assert map_item(MessageToDict(item)) == {'type': 'ban', 'author_id': 'author-id'}
    item.snippet.type = pb.LiveChatMessageSnippet.TypeWrapper.TOMBSTONE
    assert map_item(MessageToDict(item)) == {'type': 'delete', 'ids': ['m1']}


@pytest.mark.parametrize('code,details,retry', [
    (grpc.StatusCode.UNAVAILABLE, 'SECRET', True),
    (grpc.StatusCode.PERMISSION_DENIED, 'SECRET', False),
    (grpc.StatusCode.RESOURCE_EXHAUSTED, 'quota exceeded SECRET', False),
    (grpc.StatusCode.RESOURCE_EXHAUSTED, 'rate too fast SECRET', False),
    (grpc.StatusCode.FAILED_PRECONDITION, 'SECRET', False),
])
def test_grpc_error_redaction(code, details, retry):
    class Error:
        def code(self): return code
        def details(self): return details
    error = grpc_error(Error())
    assert error.retry == retry
    assert 'SECRET' not in error.message


async def test_grpc_stream_wire_contract(monkeypatch):
    requests = []
    class Service(rpc.V3DataLiveChatMessageServiceServicer):
        async def StreamList(self, request, context):
            requests.append((request, dict(context.invocation_metadata())))
            response = pb.LiveChatMessageListResponse(next_page_token='resume-token')
            response.items.add(id='one', snippet=pb.LiveChatMessageSnippet(
                type=pb.LiveChatMessageSnippet.TypeWrapper.TEXT_MESSAGE_EVENT,
                text_message_details=pb.LiveChatTextMessageDetails(message_text='hello')))
            yield response
    server = grpc.aio.server()
    rpc.add_V3DataLiveChatMessageServiceServicer_to_server(Service(), server)
    port = server.add_insecure_port('127.0.0.1:0')
    await server.start()
    insecure_channel = grpc.aio.insecure_channel
    monkeypatch.setattr(grpc.aio, 'secure_channel', lambda *args: insecure_channel(f'127.0.0.1:{port}'))
    try:
        source = YouTubeSource(None)
        batches = [batch async for batch in source.stream('CHAT', 'SECRET', 'previous-token')]
        assert batches[0].token == 'resume-token'
        assert map_item(batches[0].items[0])['message']['original'] == 'hello'
        request, metadata = requests[0]
        assert request.live_chat_id == 'CHAT'
        assert request.page_token == 'previous-token'
        assert list(request.part) == ['id', 'snippet', 'authorDetails']
        assert metadata['x-goog-api-key'] == 'SECRET'
    finally:
        await server.stop(0)
