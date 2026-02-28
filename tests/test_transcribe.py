import httpx


class MockResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_transcribe_valid_audio_file(client, monkeypatch):
    captured = {}

    def mock_post(url, files, timeout):
        captured["url"] = url
        captured["files"] = files
        captured["timeout"] = timeout
        return MockResponse({"text": "hello world", "language": "en"})

    monkeypatch.setattr("app.routers.transcribe.httpx.post", mock_post)

    response = client.post(
        "/api/v1/transcribe",
        files={"file": ("note.wav", b"fake-bytes", "audio/wav")},
    )

    assert response.status_code == 200
    assert response.json() == {"text": "hello world", "language": "en"}
    assert captured["url"] == "http://127.0.0.1:8200/transcribe"
    assert captured["timeout"] == 60.0
    assert captured["files"]["file"][0] == "note.wav"


def test_transcribe_unsupported_file_type_returns_400(client):
    response = client.post(
        "/api/v1/transcribe",
        files={"file": ("note.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Unsupported file type: .txt"}


def test_transcribe_whisper_unavailable_returns_503(client, monkeypatch):
    def mock_post(url, files, timeout):
        request = httpx.Request("POST", url)
        raise httpx.ConnectError("connection failed", request=request)

    monkeypatch.setattr("app.routers.transcribe.httpx.post", mock_post)

    response = client.post(
        "/api/v1/transcribe",
        files={"file": ("note.webm", b"fake", "audio/webm")},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Whisper service unavailable"}


def test_transcribe_honors_whisper_url_env_override(client, monkeypatch):
    captured = {}

    def mock_post(url, files, timeout):
        captured["url"] = url
        return MockResponse({"text": "override ok", "language": "en"})

    monkeypatch.setenv("WHISPER_URL", "http://127.0.0.1:9999")
    monkeypatch.setattr("app.routers.transcribe.httpx.post", mock_post)

    response = client.post(
        "/api/v1/transcribe",
        files={"file": ("voice.m4a", b"fake", "audio/m4a")},
    )

    assert response.status_code == 200
    assert response.json() == {"text": "override ok", "language": "en"}
    assert captured["url"] == "http://127.0.0.1:9999/transcribe"
