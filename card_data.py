"""
Leitura e escrita dos arquivos JSON de tradução.

Estrutura esperada: cada arquivo é um array de objetos com pelo menos:
  { "code": "06026", "name": "...", "text": "...", "traits": "..." }

Campos opcionais: flavor, subname, back_text, back_flavor, slot.
"""

import json
import re
from pathlib import Path

from config import JSON_INDENT

# Campos que contêm texto traduzível a comparar com o OCR
TEXT_FIELDS = ["name", "subname", "text", "traits", "flavor", "back_text", "back_flavor"]


def normalize_code(code: str, pack_prefix: str | None = None) -> str:
    """
    Normaliza um código/número informado pelo usuário ou OCR.
    Se o usuário digitar '6', '26' ou '202', formata automaticamente:
      - '6' -> '06006' (usando o pack_prefix atual, ex.: '06')
      - '26' -> '06026'
      - '202' -> '06202'
      - '06026' -> '06026'
    """
    if not code:
        return ""
    code_str = str(code).strip()
    if not code_str:
        return ""

    if pack_prefix is None:
        import config
        pack_prefix = config.get_setting("pack_prefix", "06")

    digits = re.findall(r"\d+", code_str)
    if digits:
        num = digits[0]
        if len(num) <= 3:
            return pack_prefix + num.zfill(3)
        elif len(num) == 5:
            return num
    return code_str


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


def find_card(code: str, all_cards: dict, pack_prefix: str | None = None) -> dict | None:
    """
    Busca uma carta pelo código. Tenta busca exata e busca normalizada com prefixo.
    """
    if not code:
        return None

    # 1. Busca exata direta
    if code in all_cards:
        return all_cards[code]

    # 2. Busca com código normalizado (ex.: '6' -> '06006', '26' -> '06026')
    norm = normalize_code(code, pack_prefix)
    if norm in all_cards:
        return all_cards[norm]

    return None


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


