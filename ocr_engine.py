"""
Motor OCR: pré-processamento de imagem com OpenCV e reconhecimento com PaddleOCR.

PaddleOCR v3 usa a API .predict() em vez de .ocr() (que é da v2).
"""

import os
import re
import cv2
import numpy as np

# Contorna problema de compatibilidade com Python 3.13 + modelscope
os.environ.setdefault('HUB_DATASET_ENDPOINT', 'https://modelscope.cn/api/v1/datasets')
# Evita verificação de conectividade a cada execução (modelos já em cache)
os.environ.setdefault('PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK', 'True')

from config import PACK_PREFIX

# Instância global do PaddleOCR (inicializada preguiçosamente)
_ocr_instance = None


def init_ocr():
    """
    Inicializa o PaddleOCR para português (carregado uma única vez).
    Modelos são baixados automaticamente na primeira execução.
    """
    global _ocr_instance
    if _ocr_instance is None:
        from paddleocr import PaddleOCR
        _ocr_instance = PaddleOCR(
            lang="pt",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
    return _ocr_instance


def preprocess_image(frame: np.ndarray) -> np.ndarray:
    """
    Pré-processamento básico para melhorar a qualidade do OCR:
    - Redimensiona para largura padrão (melhora OCR em imagens pequenas)
    - Converte para escala de cinza
    - Aplica leve desfoque Gaussiano para reduzir ruído
    - Aumenta contraste com equalização adaptativa (CLAHE)
    - Converte de volta para BGR (PaddleOCR aceita BGR)
    """
    # Redimensiona mantendo proporção (largura máx 1200px)
    h, w = frame.shape[:2]
    if w < 800:
        scale = 800 / w
        frame = cv2.resize(frame, (int(w * scale), int(h * scale)),
                           interpolation=cv2.INTER_LANCZOS4)

    # Converte para cinza
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Reduz ruído leve
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    # Aumenta contraste adaptativo
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    # Volta para BGR (3 canais) pois o PaddleOCR espera imagem colorida
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def _run_ocr_on_frame(frame: np.ndarray) -> list[tuple[list, str, float]]:
    """
    Executa o OCR em um frame e retorna lista de (bbox, texto, confiança)
    ordenada por posição vertical (topo → base).

    O PaddleOCR v3 retorna OCRResult (dict-like) com as chaves:
      - rec_texts: list[str]
      - rec_scores: list[float]
      - rec_boxes: ndarray (N, 4) → [x1, y1, x2, y2]
      - rec_polys: list[ndarray (4,2)]
    """
    ocr = init_ocr()
    results = ocr.predict(frame)

    lines = []
    for page in results:
        # PaddleOCR v3: OCRResult é um dict-like com as chaves abaixo
        texts = page.get("rec_texts", [])
        scores = page.get("rec_scores", [])
        boxes = page.get("rec_boxes")  # ndarray (N, 4) ou None
        polys = page.get("rec_polys", [])

        for i, text in enumerate(texts):
            score = scores[i] if i < len(scores) else 0.0
            # Usa rec_boxes (retângulo) se disponível; senão usa rec_polys
            if boxes is not None and i < len(boxes):
                x1, y1, x2, y2 = boxes[i]
                bbox = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
            elif i < len(polys) and polys[i] is not None:
                bbox = polys[i].tolist()
            else:
                bbox = [[0, 0], [0, 0], [0, 0], [0, 0]]
            lines.append((bbox, text, float(score)))

    # Ordena por coordenada Y do topo da bbox
    def top_y(item):
        bbox = item[0]
        return min(pt[1] for pt in bbox) if bbox else 0

    lines.sort(key=top_y)
    return lines


def extract_text_from_image(frame: np.ndarray) -> str:
    """
    Extrai todo o texto da imagem como string única (linhas separadas por \n).
    """
    processed = preprocess_image(frame)
    lines = _run_ocr_on_frame(processed)
    return '\n'.join(text for _, text, _ in lines)


def extract_card_number(frame: np.ndarray) -> str | None:
    """
    Tenta extrair o número da carta do canto inferior direito.

    O número (2-3 dígitos) fica impresso no canto inf. direito.
    Exemplo: "26" → código "06026", "202" → "06202".

    Estratégia:
    1. Faz crop da região inferior direita (~25% x 20% da imagem)
    2. Roda OCR nessa região
    3. Busca com regex o padrão de 2-3 dígitos
    4. Fallback: roda OCR no frame inteiro e busca número no quarto inferior
    5. Retorna o código completo com PACK_PREFIX + zero-padding de 3 dígitos
    """
    h, w = frame.shape[:2]

    # Crop: 25% direito × 20% inferior
    x_start = int(w * 0.75)
    y_start = int(h * 0.80)
    crop = frame[y_start:h, x_start:w]

    if crop.size > 0:
        # Escala o crop para facilitar OCR em regiões pequenas
        scale = 4
        crop_big = cv2.resize(crop, (crop.shape[1] * scale, crop.shape[0] * scale),
                              interpolation=cv2.INTER_LANCZOS4)
        lines = _run_ocr_on_frame(crop_big)
        all_text = ' '.join(text for _, text, _ in lines)
        match = re.search(r'\b(\d{2,3})\b', all_text)
        if match:
            number = match.group(1)
            return PACK_PREFIX + number.zfill(3)

    # Fallback: OCR no frame completo, busca números no quarto inferior
    lines_full = _run_ocr_on_frame(frame)
    # Filtra apenas linhas no quarto inferior da imagem
    bottom_lines = [
        (bbox, text, score) for bbox, text, score in lines_full
        if min(pt[1] for pt in bbox) >= h * 0.75
    ]

    all_bottom_text = ' '.join(text for _, text, _ in bottom_lines)
    # Busca número de 2-4 dígitos isolado (evita anos como 2024)
    match = re.search(r'(?<!\d)(\d{2,3})(?!\d)', all_bottom_text)
    if match:
        number = match.group(1)
        return PACK_PREFIX + number.zfill(3)

    return None


def list_cameras(max_to_check: int = 5) -> list[int]:
    """
    Retorna os índices das câmeras disponíveis no sistema (testa 0..max-1).
    """
    available = []
    for i in range(max_to_check):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            available.append(i)
            cap.release()
    return available
