"""call_llm 公有云成功后必须立刻返回，不能再请求 Ollama。"""
from unittest.mock import MagicMock, patch

from app.common.ollama import OllamaClient


def test_call_llm_openai_does_not_fall_through_to_ollama():
    client = OllamaClient()
    client.provider = "openai"
    client.base_url = "https://example.com/v1"
    client.api_key = "test-key"
    urls = []

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "SELECT 1 FROM dual"}}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 2},
    }

    mock_http = MagicMock()
    mock_http.__enter__.return_value = mock_http
    mock_http.__exit__.return_value = False

    def fake_post(url, **kwargs):
        urls.append(url)
        return mock_resp

    mock_http.post.side_effect = fake_post

    with patch("httpx.Client", return_value=mock_http):
        out = client.call_llm([{"role": "user", "content": "hi"}])

    assert out == "SELECT 1 FROM dual"
    assert urls == ["https://example.com/v1/chat/completions"]
    prompt, completion, total = client.usage_snapshot()
    assert prompt == 3
    assert completion == 2
    assert total == 5
