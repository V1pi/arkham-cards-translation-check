"""
Módulo de detecção automática de cartas, recorte inteligente e correção de perspectiva.
Detecta os contornos retangulares da carta na imagem/câmera e desenha o feedback visual.
"""

import cv2
import numpy as np


def order_points(pts: np.ndarray) -> np.ndarray:
    """
    Ordena 4 pontos nas posições:
    [0]: Top-Left, [1]: Top-Right, [2]: Bottom-Right, [3]: Bottom-Left.
    """
    pts = np.asarray(pts, dtype=np.float32).reshape(4, 2)
    rect = np.zeros((4, 2), dtype=np.float32)

    # Top-Left terá a menor soma (x + y), Bottom-Right terá a maior
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]

    # Top-Right terá a menor diferença (y - x), Bottom-Left terá a maior
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]

    return rect


def detect_card_quad(image: np.ndarray, min_area_ratio: float = 0.08) -> np.ndarray | None:
    """
    Detecta o quadrilátero (4 cantos) de uma carta na imagem.

    Retorna uma matriz numpy (4, 2) com as coordenadas originais dos cantos,
    ou None se nenhum contorno de carta claro for identificado.
    """
    if image is None or image.size == 0:
        return None

    h, w = image.shape[:2]
    if h < 50 or w < 50:
        return None

    # Redimensiona para velocidade e redução de ruído
    scale = 600.0 / max(h, w)
    small_w = max(1, int(w * scale))
    small_h = max(1, int(h * scale))
    small = cv2.resize(image, (small_w, small_h), interpolation=cv2.INTER_AREA)

    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Detecção de bordas adaptativa + Canny
    thresh_val, _ = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    low_thresh = max(20, int(thresh_val * 0.4))
    high_thresh = min(200, int(thresh_val * 1.0))
    edges = cv2.Canny(blurred, low_thresh, high_thresh)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    dilated = cv2.dilate(edges, kernel, iterations=2)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    total_area = small_w * small_h

    for c in contours[:6]:
        area = cv2.contourArea(c)
        if area / total_area < min_area_ratio:
            continue

        hull = cv2.convexHull(c)
        peri = cv2.arcLength(hull, True)

        # Tenta aproximação de polígono com diferentes tolerâncias
        for eps in [0.02, 0.03, 0.04, 0.05, 0.06]:
            approx = cv2.approxPolyDP(hull, eps * peri, True)
            if len(approx) == 4 and cv2.isContourConvex(approx):
                corners = approx.reshape(4, 2) / scale
                # Valida proporção mínima de aspecto
                rect = order_points(corners)
                cw = np.linalg.norm(rect[0] - rect[1])
                ch = np.linalg.norm(rect[0] - rect[3])
                if cw > 30 and ch > 30:
                    aspect = max(cw, ch) / min(cw, ch)
                    if 1.0 <= aspect <= 2.2:  # Proporção típica de cartas (~1.4)
                        return corners

        # Fallback: retângulo delimitador mínimo orientado
        rect = cv2.minAreaRect(hull)
        box = cv2.boxPoints(rect)
        if cv2.contourArea(box) / total_area >= min_area_ratio:
            corners = box / scale
            return corners

    return None


def enhance_card_image(image: np.ndarray) -> np.ndarray:
    """
    Aplica realce de contraste adaptativo (CLAHE no canal L) e nitidez (unsharp mask)
    para tornar as letras e textos pequenos muito mais nítidos e fáceis de ler.
    """
    if image is None or image.size == 0:
        return image

    # 1. CLAHE no canal de Luminância (LAB) para realçar contraste de texto
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=1.6, tileGridSize=(8, 8))
    l_enh = clahe.apply(l)
    enh_lab = cv2.cvtColor(cv2.merge((l_enh, a, b)), cv2.COLOR_LAB2BGR)

    # 2. Máscara de Nitidez (Unsharp Masking) suave
    blurred = cv2.GaussianBlur(enh_lab, (0, 0), 1.5)
    sharpened = cv2.addWeighted(enh_lab, 1.2, blurred, -0.2, 0)

    return sharpened


def crop_and_warp_card(image: np.ndarray, corners: np.ndarray | None = None) -> np.ndarray:
    """
    Recorta, corrige a perspectiva e aprimora a nitidez da carta para gerar uma imagem retangular e legível.
    Se nenhum canto for fornecido, tenta detectar automaticamente.
    Se a detecção falhar, retorna a imagem original com segurança.
    """
    if image is None or image.size == 0:
        return image

    if corners is None:
        corners = detect_card_quad(image)

    if corners is None or len(corners) != 4:
        return enhance_card_image(image)

    rect = order_points(corners)
    (tl, tr, br, bl) = rect

    # Calcula a largura do novo retângulo
    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    max_w = max(int(width_a), int(width_b))

    # Calcula a altura do novo retângulo
    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_h = max(int(height_a), int(height_b))

    if max_w < 50 or max_h < 50:
        return enhance_card_image(image)

    # Destino do mapeamento de perspectiva
    dst = np.array([
        [0, 0],
        [max_w - 1, 0],
        [max_w - 1, max_h - 1],
        [0, max_h - 1]
    ], dtype=np.float32)

    m = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, m, (max_w, max_h), flags=cv2.INTER_CUBIC)

    return enhance_card_image(warped)


def draw_card_overlay(frame: np.ndarray, corners: np.ndarray | None) -> np.ndarray:
    """
    Desenha uma borda destacada e marcadores visuais sobre o frame para indicar a carta detectada.
    """
    if frame is None or corners is None or len(corners) != 4:
        return frame

    overlay = frame.copy()
    pts = corners.astype(np.int32).reshape((-1, 1, 2))

    # Linhas do contorno
    cv2.polylines(overlay, [pts], isClosed=True, color=(0, 230, 115), thickness=2, lineType=cv2.LINE_AA)

    # Círculos destacados nos 4 vértices
    for pt in pts:
        x, y = pt[0]
        cv2.circle(overlay, (x, y), 5, (0, 255, 128), -1, lineType=cv2.LINE_AA)
        cv2.circle(overlay, (x, y), 7, (255, 255, 255), 1, lineType=cv2.LINE_AA)

    # Adiciona badge textual "🎯 Carta Detectada"
    rect = order_points(corners)
    tl = rect[0].astype(int)
    tx = max(10, tl[0])
    ty = max(20, tl[1] - 8)

    # Fundo do texto para contraste
    (tw, th), _ = cv2.getTextSize("Carta Detectada", cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
    cv2.rectangle(overlay, (tx - 2, ty - th - 4), (tx + tw + 4, ty + 2), (0, 0, 0), -1)
    cv2.putText(overlay, "Carta Detectada", (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 128), 1, lineType=cv2.LINE_AA)

    return overlay
