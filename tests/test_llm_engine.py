"""
Testes unitários para o módulo llm_engine e reconhecimento estruturado.
"""

import pytest
import llm_engine


class TestLlmEngine:
    def test_clean_json_response_with_markdown_blocks(self):
        raw = """```json
{
  "code": "06026",
  "name": "Alvo Fácil",
  "traits": "Truque.",
  "text": "Ganhe 2 recursos."
}
```"""
        parsed = llm_engine._clean_json_response(raw)
        assert parsed["code"] == "06026"
        assert parsed["name"] == "Alvo Fácil"
        assert parsed["traits"] == "Truque."

    def test_clean_json_response_with_surrounding_text(self):
        raw = """Aqui está o resultado da análise:
{
  "code": "06202",
  "name": "Palavra de Comando",
  "traits": "Magia.",
  "text": "Nomeie uma carta de Magia."
}
Espero ter ajudado!"""
        parsed = llm_engine._clean_json_response(raw)
        assert parsed["code"] == "06202"
        assert parsed["name"] == "Palavra de Comando"

    def test_normalize_llm_result_short_code(self):
        raw = {
            "code": "26",
            "name": "Alvo Fácil",
            "traits": "Truque.",
            "text": "Ganhe 2 recursos.",
            "flavor": None,
        }
        res = llm_engine._normalize_llm_result(raw, pack_prefix="06")
        assert res["code"] == "06026"
        assert res["fields"]["name"] == "Alvo Fácil"
        assert res["fields"]["traits"] == "Truque."
        assert res["fields"]["flavor"] == ""

    def test_normalize_llm_result_3digit_code(self):
        raw = {
            "code": "202",
            "name": "Palavra de Comando",
            "traits": "Magia.",
            "text": "Nomeie uma carta.",
        }
        res = llm_engine._normalize_llm_result(raw, pack_prefix="06")
        assert res["code"] == "06202"
        assert res["fields"]["name"] == "Palavra de Comando"

    def test_fetch_gemini_models_empty_key(self):
        ok, models, msg = llm_engine.fetch_gemini_models("")
        assert not ok
        assert models == []
        assert "não informada" in msg

    def test_fetch_ollama_models_invalid_url(self):
        ok, models, msg = llm_engine.fetch_ollama_models("http://127.0.0.1:59999")
        assert not ok
        assert models == []
        assert "Não foi possível conectar" in msg

    def test_fetch_openai_models_empty_url(self):
        ok, models, msg = llm_engine.fetch_openai_models("")
        assert not ok
        assert models == []
        assert "não informada" in msg

    def test_fetch_openai_models_invalid_url(self):
        ok, models, msg = llm_engine.fetch_openai_models("http://127.0.0.1:59999", "dummy_key")
        assert not ok
        assert models == []
        assert "Erro ao conectar" in msg

    def test_test_openai_connection_empty_url(self):
        ok, msg = llm_engine.test_openai_connection("", "dummy_key", "gpt-4o")
        assert not ok
        assert "não informada" in msg

    def test_fetch_gemini_models_alphabetical_order(self, monkeypatch):
        import io
        import json

        fake_response_data = {
            "models": [
                {"name": "models/gemini-2.0-flash", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-1.5-pro", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-3.7-flash", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-1.5-flash", "supportedGenerationMethods": ["generateContent"]},
            ]
        }

        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self):
                return json.dumps(fake_response_data).encode("utf-8")

        monkeypatch.setattr(llm_engine.urllib.request, "urlopen", lambda req, timeout=10: FakeResponse())

        ok, models, msg = llm_engine.fetch_gemini_models("fake_key")
        assert ok
        assert models == [
            "gemini-1.5-flash",
            "gemini-1.5-pro",
            "gemini-2.0-flash",
            "gemini-3.7-flash",
        ]

    def test_fetch_openai_models_alphabetical_order(self, monkeypatch):
        import json

        fake_response_data = {
            "data": [
                {"id": "gpt-4o"},
                {"id": "claude-3-5-sonnet"},
                {"id": "gpt-4-turbo"},
                {"id": "deepseek-chat"},
            ]
        }

        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self):
                return json.dumps(fake_response_data).encode("utf-8")

        monkeypatch.setattr(llm_engine.urllib.request, "urlopen", lambda req, timeout=10: FakeResponse())

        ok, models, msg = llm_engine.fetch_openai_models("https://api.openai.com/v1", "fake_key")
        assert ok
        assert models == [
            "claude-3-5-sonnet",
            "deepseek-chat",
            "gpt-4-turbo",
            "gpt-4o",
        ]

    def test_fetch_ollama_models_alphabetical_order(self, monkeypatch):
        import json

        fake_response_data = {
            "models": [
                {"name": "qwen2.5-vl:latest"},
                {"name": "llama3.2-vision:latest"},
                {"name": "llava:latest"},
            ]
        }

        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self):
                return json.dumps(fake_response_data).encode("utf-8")

        monkeypatch.setattr(llm_engine.urllib.request, "urlopen", lambda req, timeout=5: FakeResponse())

        ok, models, msg = llm_engine.fetch_ollama_models("http://localhost:11434")
        assert ok
        assert models == [
            "llama3.2-vision:latest",
            "llava:latest",
            "qwen2.5-vl:latest",
        ]
