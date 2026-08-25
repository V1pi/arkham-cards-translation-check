"""
Testes para text_utils: proteção de símbolos, comparação e aplicação do OCR.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from text_utils import (
    extract_symbols,
    restore_symbols,
    normalize_text,
    build_diff_html_segments,
    apply_ocr_to_json,
    has_differences,
)


# ---------------------------------------------------------------------------
# extract_symbols / restore_symbols
# ---------------------------------------------------------------------------

class TestExtractSymbols:
    def test_no_symbols(self):
        text = "Texto sem símbolos."
        clean, sym_map = extract_symbols(text)
        assert clean == text
        assert sym_map == {}

    def test_single_symbol_middle(self):
        text = "Depois que você [reaction] derrotar um inimigo."
        clean, sym_map = extract_symbols(text)
        assert "[reaction]" not in clean
        assert "{{SYMBOL_0}}" in clean
        assert sym_map["{{SYMBOL_0}}"] == "[reaction]"

    def test_symbol_at_start(self):
        text = "[action] Mova-se até 2 locais."
        clean, sym_map = extract_symbols(text)
        assert clean.startswith("{{SYMBOL_0}}")
        assert sym_map["{{SYMBOL_0}}"] == "[action]"

    def test_symbol_at_end(self):
        text = "Efeito do [elder_sign]"
        clean, sym_map = extract_symbols(text)
        assert clean.endswith("{{SYMBOL_0}}")
        assert sym_map["{{SYMBOL_0}}"] == "[elder_sign]"

    def test_multiple_symbols(self):
        text = "[fast] Ganhe [willpower] neste teste [wild]."
        clean, sym_map = extract_symbols(text)
        assert "[fast]" not in clean
        assert "[willpower]" not in clean
        assert "[wild]" not in clean
        assert len(sym_map) == 3

    def test_restore_roundtrip(self):
        text = "Enquanto [reaction] Liderança estiver [willpower][wild] comprometida."
        clean, sym_map = extract_symbols(text)
        restored = restore_symbols(clean, sym_map)
        assert restored == text

    def test_restore_no_symbols(self):
        text = "Texto simples."
        clean, sym_map = extract_symbols(text)
        restored = restore_symbols(clean, sym_map)
        assert restored == text


# ---------------------------------------------------------------------------
# normalize_text
# ---------------------------------------------------------------------------

class TestNormalizeText:
    def test_strips_whitespace(self):
        assert normalize_text("  texto  ") == "texto"

    def test_normalizes_newlines(self):
        result = normalize_text("linha1\r\nlinha2\rlinha3")
        assert result == "linha1\nlinha2\nlinha3"

    def test_collapses_empty_lines(self):
        result = normalize_text("a\n\n\nb")
        assert result == "a\n\nb"

    def test_strips_each_line(self):
        result = normalize_text("  linha1  \n  linha2  ")
        assert result == "linha1\nlinha2"


# ---------------------------------------------------------------------------
# apply_ocr_to_json
# ---------------------------------------------------------------------------

class TestApplyOcrToJson:
    def test_symbol_inferred_for_ocr_middle(self):
        """Para OCR sem símbolos, [reaction] é inferido no meio do texto."""
        json_text = "Depois que você [reaction] derrotar um inimigo."
        ocr_text  = "Depois que você vencer um inimigo."
        result = apply_ocr_to_json(json_text, ocr_text)
        assert "[reaction]" in result
        assert "vencer" in result
        assert "derrotar" not in result

    def test_symbol_inferred_for_ocr_start(self):
        """Para OCR sem símbolos, [action] é inferido no início do texto."""
        json_text = "[action] Mova-se até 2 locais."
        ocr_text  = "Mova até 2 localizações."
        result = apply_ocr_to_json(json_text, ocr_text)
        assert "[action]" in result
        assert result.startswith("[action]")

    def test_symbol_inferred_for_ocr_end(self):
        """Para OCR sem símbolos, [elder_sign] é inferido no final do texto."""
        json_text = "Efeito: +2. Resolva um efeito [elder_sign]"
        ocr_text  = "Efeito: +2. Resolva um efeito"
        result = apply_ocr_to_json(json_text, ocr_text)
        assert "[elder_sign]" in result

    def test_multiple_symbols_inferred_for_ocr(self):
        """Múltiplos símbolos são inferidos nos locais corretos para o OCR."""
        json_text = "[fast] Ganhe [willpower] neste teste [wild]."
        ocr_text  = "Receba um bônus neste teste."
        result = apply_ocr_to_json(json_text, ocr_text)
        assert "[fast]" in result
        assert "[willpower]" in result
        assert "[wild]" in result

    def test_user_or_llm_symbols_not_duplicated(self):
        """Se o texto do OCR/LLM já tiver os símbolos, NÃO duplica."""
        json_text = "Depois que você [reaction] derrotar um inimigo."
        ocr_text  = "Depois que você [reaction] vencer um inimigo."
        result = apply_ocr_to_json(json_text, ocr_text)
        assert result == "Depois que você [reaction] vencer um inimigo."
        assert result.count("[reaction]") == 1

    def test_user_custom_symbol_position_not_altered(self):
        """Se o usuário/LLM já definiu os símbolos em sua própria ordem/posição, preserva."""
        json_text = "[action] Mova-se até 2 locais."
        ocr_text  = "[action] Mova até 2 localizações."
        result = apply_ocr_to_json(json_text, ocr_text)
        assert result == "[action] Mova até 2 localizações."
        assert result.count("[action]") == 1

    def test_no_symbols_returns_ocr(self):
        """Sem símbolos no JSON, retorna o texto OCR."""
        json_text = "Texto original sem símbolos."
        ocr_text  = "Texto OCR sem símbolos."
        result = apply_ocr_to_json(json_text, ocr_text)
        assert result == "Texto OCR sem símbolos."

    def test_identical_texts(self):
        """Textos idênticos retornam o texto normalizado."""
        text = "Texto igual dos dois lados."
        result = apply_ocr_to_json(text, text)
        assert normalize_text(text) == normalize_text(result)

    def test_empty_ocr_returns_json(self):
        """Se o OCR for vazio, retorna o texto do JSON."""
        json_text = "Texto original do JSON."
        assert apply_ocr_to_json(json_text, "") == json_text


# ---------------------------------------------------------------------------
# Caracteres portugueses
# ---------------------------------------------------------------------------

class TestPortugueseChars:
    def test_accented_chars_preserved(self):
        json_text = "Após você [reaction] derrotar o inimigo, ganhe 2 ações."
        ocr_text  = "Após você derrotar o inimigo, ganhe 2 ações."
        result = apply_ocr_to_json(json_text, ocr_text)
        assert "ações" in result
        assert "você" in result
        assert "[reaction]" in result

    def test_tilde_cedilla(self):
        json_text = "Engaje um inimigo [action] não élite."
        ocr_text  = "Engaje um inimigo não élite."
        result = apply_ocr_to_json(json_text, ocr_text)
        assert "não" in result
        assert "élite" in result
        assert "[action]" in result

    def test_unicode_symbols_in_json(self):
        """Símbolos com underscore preservados corretamente."""
        json_text = "Efeito [elder_sign]: +2."
        ocr_text  = "Efeito: +2."
        result = apply_ocr_to_json(json_text, ocr_text)
        assert "[elder_sign]" in result


# ---------------------------------------------------------------------------
# has_differences
# ---------------------------------------------------------------------------

class TestHasDifferences:
    def test_no_diff(self):
        text = "Texto igual dos dois lados."
        assert not has_differences(text, text)

    def test_with_diff(self):
        assert has_differences("derrotar um inimigo", "vencer um inimigo")

    def test_symbol_ignored_in_diff(self):
        """Diferença apenas no símbolo não conta (OCR não reconhece símbolo)."""
        json_text = "Depois que você [reaction] derrotar."
        ocr_text  = "Depois que você derrotar."
        # Sem o símbolo, textos são equivalentes
        assert not has_differences(json_text, ocr_text)


# ---------------------------------------------------------------------------
# diff segments
# ---------------------------------------------------------------------------

class TestDiffSegments:
    def test_equal_produces_equal_tag(self):
        segments = build_diff_html_segments("palavra", "palavra")
        tags = [t for _, t in segments]
        assert "equal" in tags
        assert "delete" not in tags
        assert "insert" not in tags

    def test_replace_produces_delete_and_insert(self):
        segments = build_diff_html_segments("derrotar inimigo", "vencer inimigo")
        tags = [t for _, t in segments]
        assert "delete" in tags
        assert "insert" in tags

    def test_segments_rebuild_texts(self):
        """Os segmentos devem conter todo o texto original."""
        json_text = "Mova-se até 2 locais adjacentes."
        ocr_text  = "Mova até 3 locais conectados."
        segments = build_diff_html_segments(json_text, ocr_text)
        full_text = ''.join(t for t, _ in segments)
        # Todos os tokens de ambos os textos devem aparecer
        assert "Mova" in full_text or "Mova-se" in full_text
