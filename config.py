"""
Configurações do Arkham Horror LCG Translation Checker.
Edite este arquivo para adaptar a outros ciclos/expansões.
"""

import os
from pathlib import Path

# Raiz do projeto (pasta onde este arquivo está)
PROJECT_ROOT = Path(__file__).parent

# Pasta com as traduções em português do ciclo atual
TRANSLATIONS_PATH = PROJECT_ROOT / "translations" / "pt" / "pack" / "tde"

# Prefixo do ciclo atual (TDE = "06").
# Para outras expansões, altere este valor. Ex.: "07" para Forgotten Age.
PACK_PREFIX = "06"

# Índice da câmera padrão (0 = câmera principal)
CAMERA_INDEX = 0

# Indentação usada ao gravar os JSON (deve corresponder ao repositório)
JSON_INDENT = 4
