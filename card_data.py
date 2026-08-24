"""
Leitura e escrita dos arquivos JSON de tradução.

Estrutura esperada: cada arquivo é um array de objetos com pelo menos:
  { "code": "06026", "name": "...", "text": "...", "traits": "..." }

Campos opcionais: flavor, subname, back_text, back_flavor, slot.
"""

import json
from pathlib import Path

from config import JSON_INDENT

# Campos que contêm texto traduzível a comparar com o OCR
TEXT_FIELDS = ["name", "subname", "text", "traits", "flavor", "back_text", "back_flavor"]


def load_all_cards(translations_path: Path) -> dict:
    """
    Carrega todos os .json do diretório de traduções.

    Retorna: { code: {"card": card_dict, "file": filepath} }
    Cartas sem campo "code" são ignoradas.
    """
    all_cards = {}
    translations_path = Path(translations_path)

    for json_file in sorted(translations_path.glob("*.json")):
        try:
            with open(json_file, encoding="utf-8") as f:
                cards = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[aviso] Não foi possível ler {json_file.name}: {e}")
            continue

        for card in cards:
            code = card.get("code")
            if not code:
                continue  # entrada inválida (ex.: campo com typo)
            all_cards[code] = {"card": card, "file": json_file}

    return all_cards


def find_card(code: str, all_cards: dict) -> dict | None:
    """
    Busca uma carta pelo código. Retorna {"card": ..., "file": ...} ou None.
    """
    return all_cards.get(code)


def save_card(card: dict, filepath: Path, updated_fields: dict) -> None:
    """
    Atualiza os campos indicados em updated_fields dentro do arquivo JSON,
    preservando todos os outros campos e a ordem das cartas.

    updated_fields: { "text": "novo texto", "traits": "novo trait", ... }
    """
    filepath = Path(filepath)

    with open(filepath, encoding="utf-8") as f:
        cards = json.load(f)

    code = card["code"]
    for i, c in enumerate(cards):
        if c.get("code") == code:
            for field, value in updated_fields.items():
                if value is not None:
                    cards[i][field] = value
            break

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(cards, f, ensure_ascii=True, indent=JSON_INDENT)
        f.write("\n")  # linha final, padrão do repositório


def get_card_text_fields(card: dict) -> dict:
    """
    Retorna apenas os campos de texto de uma carta, excluindo vazios.
    """
    return {k: card[k] for k in TEXT_FIELDS if k in card and card[k]}


