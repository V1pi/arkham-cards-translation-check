"""
Utilitários de texto: proteção de símbolos Arkham, normalização e comparação.

Símbolos protegidos: qualquer token no formato [nome_do_simbolo].
Exemplos: [reaction], [action], [fast], [elder_sign], [willpower], [wild], etc.
"""

import re
import difflib


# Regex que captura qualquer [token] — padrão usado em todo o projeto
SYMBOL_PATTERN = re.compile(r'\[[^\[\]]+\]')


def extract_symbols(text: str) -> tuple[str, dict]:
    """
    Substitui todos os tokens [símbolo] por placeholders {{SYMBOL_N}}.

    Retorna:
        clean_text: texto sem símbolos
        symbol_map: { "{{SYMBOL_0}}": "[reaction]", ... }
    """
    symbol_map = {}
    counter = [0]

    def replacer(match):
        placeholder = f"{{{{SYMBOL_{counter[0]}}}}}"
        symbol_map[placeholder] = match.group(0)
        counter[0] += 1
        return placeholder

    clean_text = SYMBOL_PATTERN.sub(replacer, text)
    return clean_text, symbol_map


def restore_symbols(text: str, symbol_map: dict) -> str:
    """
    Recoloca os símbolos originais no texto a partir do symbol_map.
    """
    for placeholder, symbol in symbol_map.items():
        text = text.replace(placeholder, symbol)
    return text


def normalize_text(text: str) -> str:
    """
    Normalização leve para comparação justa:
    - colapsa múltiplos espaços em um
    - normaliza quebras de linha
    - remove espaços antes/depois de quebras de linha
    - strip nas bordas
    """
    # normaliza quebras de linha
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # remove espaços em branco antes e depois de cada linha
    lines = [line.strip() for line in text.split('\n')]
    # remove linhas vazias duplicadas
    result = []
    prev_empty = False
    for line in lines:
        if line == '':
            if not prev_empty:
                result.append(line)
            prev_empty = True
        else:
            # colapsa múltiplos espaços dentro de cada linha
            line = re.sub(r' {2,}', ' ', line)
            result.append(line)
            prev_empty = False
    return '\n'.join(result).strip()


def compare_texts(json_text: str, ocr_text: str) -> list[tuple]:
    """
    Compara dois textos usando difflib e retorna lista de operações de diff.

    Retorna lista de tuplas (tag, i1, i2, j1, j2) do SequenceMatcher,
    onde tag pode ser: 'equal', 'replace', 'delete', 'insert'.

    Os textos são comparados por palavras para melhor legibilidade.
    """
    # Normaliza antes de comparar
    a_words = normalize_text(json_text).split()
    b_words = normalize_text(ocr_text).split()

    matcher = difflib.SequenceMatcher(None, a_words, b_words, autojunk=False)
    return matcher.get_opcodes()


def build_diff_html_segments(json_text: str, ocr_text: str) -> list[tuple[str, str]]:
    """
    Gera segmentos de texto com tag de cor para exibição no Tkinter.

    Retorna: lista de (texto, tag) onde tag é:
        'equal'   → texto igual
        'delete'  → estava no JSON, não está no OCR (vermelho)
        'insert'  → está no OCR, não estava no JSON (verde)
        'replace' → substituição (amarelo)
    """
    a_words = normalize_text(json_text).split()
    b_words = normalize_text(ocr_text).split()

    matcher = difflib.SequenceMatcher(None, a_words, b_words, autojunk=False)
    segments = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            segments.append((' '.join(a_words[i1:i2]) + ' ', 'equal'))
        elif tag == 'delete':
            segments.append((' '.join(a_words[i1:i2]) + ' ', 'delete'))
        elif tag == 'insert':
            segments.append((' '.join(b_words[j1:j2]) + ' ', 'insert'))
        elif tag == 'replace':
            segments.append((' '.join(a_words[i1:i2]) + ' ', 'delete'))
            segments.append((' '.join(b_words[j1:j2]) + ' ', 'insert'))

    return segments


def apply_ocr_to_json(json_text: str, ocr_text: str) -> str:
    """
    Inferência inteligente de símbolos e aplicação do OCR ao JSON.
    Preserva a formatação/quebras de linha e posiciona os [símbolos] do JSON
    no local contextual correspondente do texto OCR.
    """
    if not json_text or not ocr_text:
        return ocr_text

    clean_json, symbol_map = extract_symbols(json_text)
    if not symbol_map:
        return ocr_text.strip()

    # Se o ocr_text já possui todos os símbolos do JSON, não precisa reinserir
    existing_symbols = re.findall(r'\[[^\[\]]+\]', ocr_text)
    expected_symbols = list(symbol_map.values())
    if existing_symbols == expected_symbols:
        return ocr_text.strip()

    def tokenize(text):
        tokens = []
        for line in text.split('\n'):
            words = line.split()
            tokens.extend(words)
            tokens.append('\n')
        if tokens and tokens[-1] == '\n':
            tokens.pop()
        return tokens

    json_tokens = tokenize(clean_json)
    ocr_tokens = tokenize(ocr_text)

    # Identifica a posição relativa de cada símbolo em relação às palavras REAIS (sem símbolos)
    json_words = []
    syms_before = {}

    for tok in json_tokens:
        if tok == '\n':
            continue
        found_syms = re.findall(r'\{\{SYMBOL_\d+\}\}', tok)
        clean_tok = re.sub(r'\{\{SYMBOL_\d+\}\}', '', tok).strip()

        if found_syms and not clean_tok:
            # Token composto apenas de símbolos
            curr_pos = len(json_words)
            for s in found_syms:
                syms_before.setdefault(curr_pos, []).append(symbol_map[s])
        elif found_syms and clean_tok:
            # Símbolo anexado a uma palavra (ex.: [wild].)
            curr_pos = len(json_words)
            if tok.startswith('{{SYMBOL_'):
                for s in found_syms:
                    syms_before.setdefault(curr_pos, []).append(symbol_map[s])
                json_words.append(clean_tok)
            else:
                json_words.append(clean_tok)
                for s in found_syms:
                    syms_before.setdefault(len(json_words), []).append(symbol_map[s])
        else:
            json_words.append(tok)

    ocr_words = [t for t in ocr_tokens if t != '\n']

    matcher = difflib.SequenceMatcher(
        None,
        [w.lower().rstrip('.,;:!?') for w in json_words],
        [w.lower().rstrip('.,;:!?') for w in ocr_words],
        autojunk=False
    )

    def map_pos(j_pos, o_len):
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal' and i1 <= j_pos <= i2:
                return min(o_len, j1 + (j_pos - i1))
            if i2 > j_pos:
                return max(0, min(j1, o_len))
        return o_len

    ocr_insertions = {}
    for j_pos, sym_list in syms_before.items():
        o_pos = map_pos(j_pos, len(ocr_words))
        for sym in sym_list:
            ocr_insertions.setdefault(o_pos, []).append(sym)

    result = []
    curr_ocr_word = 0
    for tok in ocr_tokens:
        if tok == '\n':
            result.append('\n')
        else:
            if curr_ocr_word in ocr_insertions:
                for sym in ocr_insertions[curr_ocr_word]:
                    result.append(sym)
                    result.append(' ')
            result.append(tok)
            result.append(' ')
            curr_ocr_word += 1

    if len(ocr_words) in ocr_insertions:
        for sym in ocr_insertions[len(ocr_words)]:
            result.append(sym)
            result.append(' ')

    text_out = ''.join(result)
    text_out = re.sub(r'[ \t]+\n', '\n', text_out)
    text_out = re.sub(r'\n[ \t]+', '\n', text_out)
    text_out = re.sub(r' +', ' ', text_out)
    return text_out.strip()


def has_differences(json_text: str, ocr_text: str) -> bool:
    """
    Retorna True se os textos têm diferenças relevantes.
    """
    # Remove símbolos antes de comparar (OCR não os reconhece)
    clean_json, _ = extract_symbols(json_text)
    # Remove também os placeholders que possam ter sobrado (ex.: {{SYMBOL_0}})
    clean_json = re.sub(r'\{\{SYMBOL_\d+\}\}', '', clean_json)
    return normalize_text(clean_json) != normalize_text(ocr_text)
