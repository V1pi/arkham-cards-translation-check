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
