"""
Testes unitários para o módulo card_data e normalização de códigos de carta.
"""

import pytest
import card_data


class TestCardDataNormalization:
    def test_single_digit(self):
        assert card_data.normalize_code("6", pack_prefix="06") == "06006"

    def test_two_digits(self):
        assert card_data.normalize_code("26", pack_prefix="06") == "06026"

    def test_three_digits(self):
        assert card_data.normalize_code("202", pack_prefix="06") == "06202"

    def test_full_five_digits(self):
        assert card_data.normalize_code("06026", pack_prefix="06") == "06026"
        assert card_data.normalize_code("06202", pack_prefix="06") == "06202"

    def test_with_whitespace(self):
        assert card_data.normalize_code("  6  ", pack_prefix="06") == "06006"
        assert card_data.normalize_code(" 202 \n", pack_prefix="06") == "06202"

    def test_different_pack_prefix(self):
        assert card_data.normalize_code("6", pack_prefix="04") == "04006"
        assert card_data.normalize_code("150", pack_prefix="07") == "07150"

    def test_letter_suffix_short_code(self):
        assert card_data.normalize_code("15a", pack_prefix="06") == "06015a"
        assert card_data.normalize_code("15b", pack_prefix="06") == "06015b"
        assert card_data.normalize_code("6a", pack_prefix="06") == "06006a"
        assert card_data.normalize_code("202b", pack_prefix="06") == "06202b"

    def test_letter_suffix_case_insensitive(self):
        assert card_data.normalize_code("15A", pack_prefix="06") == "06015a"
        assert card_data.normalize_code("06015A", pack_prefix="06") == "06015a"
        assert card_data.normalize_code("06015B", pack_prefix="06") == "06015b"

    def test_full_five_digits_with_letter(self):
        assert card_data.normalize_code("06015a", pack_prefix="06") == "06015a"
        assert card_data.normalize_code("06015b", pack_prefix="06") == "06015b"
        assert card_data.normalize_code("01001b", pack_prefix="06") == "01001b"

    def test_with_hyphen_or_separator(self):
        assert card_data.normalize_code("06015-a", pack_prefix="06") == "06015a"
        assert card_data.normalize_code("15-a", pack_prefix="06") == "06015a"
        assert card_data.normalize_code("  15a  ", pack_prefix="06") == "06015a"

    def test_empty_or_none(self):
        assert card_data.normalize_code("") == ""
        assert card_data.normalize_code(None) == ""


class TestFindCard:
    def test_find_card_exact_and_normalized(self):
        fake_cards = {
            "06026": {"card": {"code": "06026", "name": "Alvo Fácil"}},
            "06015a": {"card": {"code": "06015a", "name": "Portal de Sonho (A)"}},
            "06015b": {"card": {"code": "06015b", "name": "Portal de Sonho (B)"}},
        }
        # Busca exata
        assert card_data.find_card("06026", fake_cards)["card"]["name"] == "Alvo Fácil"
        assert card_data.find_card("06015a", fake_cards)["card"]["name"] == "Portal de Sonho (A)"
        
        # Busca case insensitive
        assert card_data.find_card("06015A", fake_cards)["card"]["name"] == "Portal de Sonho (A)"
        assert card_data.find_card("06015B", fake_cards)["card"]["name"] == "Portal de Sonho (B)"

        # Busca normalizada com sufixo
        assert card_data.find_card("15a", fake_cards, pack_prefix="06")["card"]["name"] == "Portal de Sonho (A)"
        assert card_data.find_card("15A", fake_cards, pack_prefix="06")["card"]["name"] == "Portal de Sonho (A)"
        assert card_data.find_card("15b", fake_cards, pack_prefix="06")["card"]["name"] == "Portal de Sonho (B)"
        assert card_data.find_card("26", fake_cards, pack_prefix="06")["card"]["name"] == "Alvo Fácil"

        # Não encontrado
        assert card_data.find_card("999", fake_cards, pack_prefix="06") is None
        assert card_data.find_card("", fake_cards) is None
        assert card_data.find_card(None, fake_cards) is None
