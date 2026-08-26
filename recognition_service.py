"""
Serviço unificado de reconhecimento de cartas.
Abstrai a escolha entre o PaddleOCR tradicional e modelos multimodais de LLM (Gemini e Ollama).
"""

import numpy as np
import config
import ocr_engine
import llm_engine
import text_utils
import card_detector


def recognize_card(
    frame: np.ndarray,
    known_json_fields: dict | None = None,
    auto_crop: bool = False,
) -> tuple[str | None, dict[str, str], str]:
    """
    Processa a imagem da carta usando o motor selecionado (OCR ou LLM).
    Se auto_crop for True, recorta e alinha a carta automaticamente antes da análise.
    """
    # Apenas recorta e alinha caso auto_crop seja explicitamente solicitado
    processed_frame = card_detector.crop_and_warp_card(frame) if auto_crop else frame

    mode = config.get_setting("recognition_mode", "ocr")

    if mode == "llm":
        provider = config.get_setting("llm_provider", "gemini")
        if provider == "gemini":
            model = config.get_setting("gemini_model", "gemini-3.7-flash")
            result = llm_engine.analyze_with_gemini(processed_frame)
            return result.get("code"), result.get("fields", {}), f"Google Gemini ({model})"
        elif provider == "openai":
            model = config.get_setting("openai_model", "gpt-4o")
            result = llm_engine.analyze_with_openai(processed_frame)
            return result.get("code"), result.get("fields", {}), f"OpenAI Compatible ({model})"
        elif provider == "ollama":
            model = config.get_setting("ollama_model", "llama3.2-vision")
            result = llm_engine.analyze_with_ollama(processed_frame)
            return result.get("code"), result.get("fields", {}), f"Ollama ({model})"
        else:
            raise ValueError(f"Provedor LLM desconhecido: '{provider}'")

    # Modo padrão: PaddleOCR
    code = ocr_engine.extract_card_number(processed_frame)
    full_text = ocr_engine.extract_text_from_image(processed_frame)

    # Classifica o texto usando heurísticas se conhecermos os campos do JSON
    if known_json_fields:
        classified = classify_ocr_text(full_text, known_json_fields)
        # Aplica inferência de símbolos para o PaddleOCR
        final_fields = {}
        for f, raw in classified.items():
            j_val = known_json_fields.get(f, "")
            if raw and j_val:
                final_fields[f] = text_utils.apply_ocr_to_json(j_val, raw)
            else:
                final_fields[f] = raw
    else:
        # Se os campos do JSON ainda não forem conhecidos (antes de achar o código da carta),
        # guarda o texto bruto para classificar assim que achar a carta
        final_fields = {"_raw_ocr": full_text}

    return code, final_fields, "PaddleOCR (Local)"


def classify_ocr_text(full_text: str, json_fields: dict) -> dict:
    """
    Classifica o texto corrido do OCR nos campos do JSON usando heurísticas.
    """
    if not full_text.strip():
        return {field: "" for field in json_fields}

    lines = [l.strip() for l in full_text.split('\n') if l.strip()]
    result = {}

    # --- Nome ---
    if "name" in json_fields:
        name_candidate = ""
        for line in lines[:5]:
            if line.upper() in {"EVENTO", "ATIVO", "PERÍCIA", "PERICIA", "FRAQUEZA", "TREACHERY"}:
                continue
            if len(line) < 50 and not line.endswith('.') and not line.isdigit():
                name_candidate = line
                break
        result["name"] = name_candidate

    # --- Traits ---
    if "traits" in json_fields:
        traits_candidate = ""
        for line in lines:
            if line.endswith('.') and len(line) < 60:
                words = line.rstrip('.').split('.')
                if all(w.strip() and w.strip()[0].isupper() for w in words if w.strip()):
                    traits_candidate = line
                    break
        result["traits"] = traits_candidate

    # --- Texto principal ---
    if "text" in json_fields:
        exclude = {
            result.get("name", ""),
            result.get("traits", ""),
            "EVENTO", "ATIVO", "PERÍCIA", "PERICIA", "FRAQUEZA"
        } - {""}
        text_lines = [l for l in lines if l not in exclude and not l.isdigit()]

        flavor_start = len(text_lines)
        if "flavor" in json_fields:
            for i, line in enumerate(text_lines):
                if line.startswith('"') or line.startswith('“') or line.startswith('*'):
                    flavor_start = i
                    break

            expected_flavor = json_fields.get("flavor", "")
            if flavor_start == len(text_lines) and expected_flavor:
                flavor_chars = len(expected_flavor)
                acc = 0
                for i in range(len(text_lines) - 1, -1, -1):
                    acc += len(text_lines[i])
                    if acc >= flavor_chars * 0.6:
                        flavor_start = i
                        break

        result["text"] = '\n'.join(text_lines[:flavor_start])

        if "flavor" in json_fields:
            result["flavor"] = '\n'.join(text_lines[flavor_start:])

    # --- Subtítulo ---
    if "subname" in json_fields:
        result["subname"] = ""

    # --- Verso ---
    for back_field in ["back_text", "back_flavor"]:
        if back_field in json_fields:
            result[back_field] = ""

    for field in json_fields:
        result.setdefault(field, "")

    return result
