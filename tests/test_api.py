import json

from fastapi.testclient import TestClient

from app.server import create_app


def test_config_persistence_and_removed_credentials_rejected(tmp_path):
    path = tmp_path / 'config.json'
    with TestClient(create_app(path)) as client:
        response = client.put('/api/config', json={'source': 'Sv2vZ8uZKVI', 'target_languages': ['ja', 'en']})
        assert response.status_code == 200
        assert 'youtube_key' not in response.json() and 'azure_key' not in response.json()
        response = client.put('/api/config', json={'youtube_key': 'PRIVATE_SECRET'})
        assert response.status_code == 422 and 'PRIVATE_SECRET' not in response.text
        assert 'youtube_key' not in json.loads(path.read_text())
        assert client.put('/api/config', json={'style': {'font_size': 999}}).status_code == 422
    with TestClient(create_app(path)) as client:
        assert client.get('/api/config').json()['target_languages'] == ['ja', 'en']


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


def test_connect_accepts_click_timestamp_and_rejects_unzoned_timestamp(tmp_path):
    from datetime import datetime, timezone
    from app.server import create_app
    app = create_app(tmp_path / 'config.json')
    with TestClient(app) as client:
        timestamp = datetime.now(timezone.utc).isoformat()
        result = client.post('/api/connect', json={'started_at': timestamp})
        assert result.status_code == 200
        assert result.json()['chat_started_at'] == timestamp
        client.post('/api/disconnect')
        assert client.post('/api/connect', json={'started_at': '2026-10-09T00:00:00'}).status_code == 422
        assert client.post('/api/connect', json={'started_at': 'invalid'}).status_code == 422
        assert client.post('/api/connect').status_code == 200


def test_legacy_local_config_keeps_source_style_and_order_without_old_credentials(tmp_path):
    path = tmp_path / 'config.json'
    path.write_text(json.dumps({'source': 'Sv2vZ8uZKVI', 'source_type': 'video', 'youtube_provider': 'api',
        'youtube_key': 'OLD_PRIVATE', 'translation_provider': 'azure', 'azure_key': 'OLD_PRIVATE',
        'azure_region': 'eastasia', 'target_languages': ['ja', 'en'], 'style': {'font_size': 38}}))
    with TestClient(create_app(path)) as client:
        config = client.get('/api/config').json()
        assert config['source'] == 'Sv2vZ8uZKVI'
        assert config['style']['font_size'] == 38 and config['target_languages'] == ['ja', 'en']
        assert 'OLD_PRIVATE' not in json.dumps(config)
        assert client.put('/api/config', json=config).status_code == 200
    saved = json.loads(path.read_text())
    assert not any(field in saved for field in ['youtube_key', 'azure_key', 'source_type', 'translation_provider'])
