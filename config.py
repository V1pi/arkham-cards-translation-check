"""
Configurações do Arkham Horror LCG Translation Checker.
Suporta persistência via settings.json e integração com OCR e LLMs (Gemini, Ollama).
"""

import json
import os
from pathlib import Path

# Raiz do projeto (pasta onde este arquivo está)
PROJECT_ROOT = Path(__file__).parent
SETTINGS_FILE = PROJECT_ROOT / "settings.json"

# Pasta com as traduções em português do ciclo atual
TRANSLATIONS_PATH = PROJECT_ROOT / "translations" / "pt" / "pack" / "tde"

# Indentação usada ao gravar os JSON (deve corresponder ao repositório)
JSON_INDENT = 4

# Valores padrão de configuração
DEFAULT_SETTINGS = {
    "pack_prefix": "06",
    "camera_index": 0,
    "json_indent": 4,
    "recognition_mode": "ocr",  # "ocr" ou "llm"
    "llm_provider": "gemini",   # "gemini" ou "ollama"
    "gemini_api_key": os.environ.get("GEMINI_API_KEY", ""),
    "gemini_model": "gemini-3.7-flash",
    "ollama_url": "http://localhost:11434",
    "ollama_model": "llama3.2-vision",
}


def load_settings() -> dict:
    """Carrega as configurações do arquivo settings.json mesclando com os padrões."""
    settings = dict(DEFAULT_SETTINGS)
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                settings.update(data)
        except Exception as e:
            print(f"[aviso] Erro ao ler {SETTINGS_FILE.name}: {e}")

    # Fallback para variável de ambiente se api_key não estiver definida
    if not settings.get("gemini_api_key"):
        settings["gemini_api_key"] = os.environ.get("GEMINI_API_KEY", "")

    return settings


def save_settings(settings: dict) -> None:
    """Grava as configurações em settings.json."""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
            f.write("\n")
    except Exception as e:
        print(f"[erro] Não foi possível salvar configurações: {e}")


# Instância global ativa
_current_settings = load_settings()


def get_setting(key: str, default=None):
    """Obtém uma configuração ativa."""
    return _current_settings.get(key, default)


def set_setting(key: str, value) -> None:
    """Atualiza e salva uma configuração."""
    _current_settings[key] = value
    save_settings(_current_settings)


def update_settings(new_dict: dict) -> None:
    """Atualiza múltiplos valores e salva."""
    _current_settings.update(new_dict)
    save_settings(_current_settings)


# Variáveis compatíveis para importação direta
PACK_PREFIX = _current_settings.get("pack_prefix", "06")
CAMERA_INDEX = _current_settings.get("camera_index", 0)
