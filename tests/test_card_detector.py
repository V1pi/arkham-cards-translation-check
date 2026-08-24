"""
Testes unitários para o módulo card_detector (detecção de contornos, corte e sobreposição visual).
"""

import pytest
import numpy as np
import cv2
from pathlib import Path

import card_detector


class TestCardDetector:
    def test_order_points(self):
        # 4 pontos desordenados representando um retângulo (10, 10) a (110, 210)
        unordered = np.array([
            [110, 210], # BR
            [10, 10],   # TL
            [10, 210],  # BL
            [110, 10],  # TR
        ], dtype=np.float32)

        ordered = card_detector.order_points(unordered)

        np.testing.assert_array_almost_equal(ordered[0], [10, 10])   # TL
        np.testing.assert_array_almost_equal(ordered[1], [110, 10])  # TR
        np.testing.assert_array_almost_equal(ordered[2], [110, 210]) # BR
        np.testing.assert_array_almost_equal(ordered[3], [10, 210])  # BL

    def test_crop_and_warp_card_fallback_on_none(self):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        # Sem carta na imagem preta -> retorna a própria imagem com segurança
        result = card_detector.crop_and_warp_card(img, corners=None)
        assert result.shape == img.shape

    def test_crop_and_warp_card_with_corners(self):
        img = np.zeros((400, 400, 3), dtype=np.uint8)
        # Desenha um retângulo branco centralizado (100, 50) a (300, 350) - tamanho 200x300
        cv2.rectangle(img, (100, 50), (300, 350), (255, 255, 255), -1)

        corners = np.array([[100, 50], [300, 50], [300, 350], [100, 350]], dtype=np.float32)
        warped = card_detector.crop_and_warp_card(img, corners)

        assert warped is not None
        # O tamanho deve ser aproximadamente 200 de largura por 300 de altura
        assert abs(warped.shape[1] - 200) <= 2
        assert abs(warped.shape[0] - 300) <= 2

    def test_draw_card_overlay(self):
        img = np.zeros((300, 300, 3), dtype=np.uint8)
        corners = np.array([[50, 50], [250, 50], [250, 250], [50, 250]], dtype=np.float32)

        overlay = card_detector.draw_card_overlay(img, corners)
        assert overlay.shape == img.shape
        # O overlay deve ter pixels não-pretos desenhados
        assert np.any(overlay > 0)

    def test_detect_card_quad_on_sample_card(self):
        # Se os arquivos de exemplo existirem, testa a detecção
        sample_path = Path("card_example/06026.jpg")
        if sample_path.exists():
            data = np.fromfile(str(sample_path), dtype=np.uint8)
            img = cv2.imdecode(data, cv2.IMREAD_COLOR)
            corners = card_detector.detect_card_quad(img)
            assert corners is not None
            assert len(corners) == 4
