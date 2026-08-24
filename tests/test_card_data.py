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

    def test_empty_or_none(self):
        assert card_data.normalize_code("") == ""
        assert card_data.normalize_code(None) == ""
