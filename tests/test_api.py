import json

from fastapi.testclient import TestClient

from app.server import create_app


def test_config_persistence_secret_redaction_and_validation(tmp_path):
    path = tmp_path / 'config.json'
    with TestClient(create_app(path)) as client:
        response = client.put('/api/config', json={'youtube_key': 'YT_SECRET', 'azure_key': 'AZURE_SECRET', 'source': 'CHAT'})
        assert response.status_code == 200
        assert response.json()['youtube_key_set']
        assert 'SECRET' not in response.text
        client.put('/api/config', json={'target_language': 'ja'})
        assert json.loads(path.read_text())['youtube_key'] == 'YT_SECRET'
        response = client.put('/api/config', json={'youtube_key': 'SECRET' * 100})
        assert response.status_code == 422 and 'SECRET' not in response.text
        response = client.put('/api/config', json={'style': {'font_size': 999}})
        assert response.status_code == 422
        client.put('/api/config', json={'youtube_key': ''})
        assert not client.get('/api/config').json()['youtube_key_set']
    with TestClient(create_app(path)) as client:
        assert client.get('/api/config').json()['target_language'] == 'ja'
        assert client.get('/api/config').json()['azure_key_set']


def test_foreign_origins_and_hosts_rejected(tmp_path):
    with TestClient(create_app(tmp_path / 'config.json')) as client:
        assert client.post('/api/demo', headers={'Origin': 'https://evil.example'}).status_code == 403
        assert client.get('/api/config', headers={'Host': 'evil.example'}).status_code == 400
        assert client.post('/api/demo', headers={'Origin': 'http://testserver'}).status_code == 200
        assert client.get('/api/status').headers['cache-control'] == 'no-store'


def test_websocket_snapshot_and_local_demo(tmp_path):
    with TestClient(create_app(tmp_path / 'config.json')) as client:
        with client.websocket_connect('/ws') as ws:
            initial = ws.receive_json()
            assert initial['type'] == 'snapshot' and initial['messages'] == []
            assert 'youtube_key' not in initial['config']
            client.post('/api/demo')
            while True:
                event = ws.receive_json()
                if event['type'] == 'message':
                    assert event['message']['original'] and event['session'] != initial['session']
                    break
