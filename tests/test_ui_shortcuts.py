"""
Testes unitários para os métodos de atalho de teclado, navegação de campos e formatação na UI (main.py).
"""

import pytest
import tkinter as tk
from unittest.mock import MagicMock, patch
import main


@pytest.fixture
def app():
    # Cria uma instância da App sem abrir câmera real
    with patch("main.cv2.VideoCapture") as mock_cap, \
         patch("main.card_data.load_all_cards", return_value={}):
        mock_instance = MagicMock()
        mock_instance.isOpened.return_value = False
        mock_cap.return_value = mock_instance
        
        test_app = main.App()
        test_app.withdraw()  # Não exibe janela física no teste
        yield test_app
        try:
            test_app.destroy()
        except Exception:
            pass


def test_field_navigation(app):
    """Testa navegação circular entre campos com _next_field, _prev_field e _select_field_by_index."""
    app._field_keys = ["name", "traits", "text", "flavor"]
    app.field_combo["values"] = ["Nome", "Traits", "Texto", "Flavor"]
    app.json_fields = {"name": "Old Name", "traits": "Old Traits", "text": "Old Text", "flavor": "Old Flavor"}
    app.ocr_text_by_field = {"name": "New Name", "traits": "New Traits", "text": "New Text", "flavor": "New Flavor"}
    
    # Inicia no campo 0 (name)
    app._select_field_by_index(0)
    assert app._current_field_key == "name"
    assert app.txt_ocr.get("1.0", "end-1c") == "New Name"

    # Altera texto no widget e avança para o próximo campo (traits)
    app.txt_ocr.delete("1.0", tk.END)
    app.txt_ocr.insert("1.0", "Edited Name")
    
    app._next_field()
    # Verifica se o texto editado de 'name' foi salvo no buffer
    assert app.ocr_text_by_field["name"] == "Edited Name"
    assert app._current_field_key == "traits"
    assert app.txt_ocr.get("1.0", "end-1c") == "New Traits"

    # Avança para 'text'
    app._next_field()
    assert app._current_field_key == "text"

    # Volta para 'traits' com _prev_field
    app._prev_field()
    assert app._current_field_key == "traits"

    # Pula diretamente para o campo 3 (flavor) com _select_field_by_index
    app._select_field_by_index(3)
    assert app._current_field_key == "flavor"
    assert app.txt_ocr.get("1.0", "end-1c") == "New Flavor"

    # Avança circularmente de flavor para name (índice 0)
    app._next_field()
    assert app._current_field_key == "name"
    assert app.txt_ocr.get("1.0", "end-1c") == "Edited Name"


def test_format_wrap_selection(app):
    """Testa inclusão de tags <b> e <i> com ou sem seleção."""
    app._field_keys = ["text"]
    app.json_fields = {"text": "Original"}
    app.ocr_text_by_field = {"text": "Original"}
    app._select_field_by_index(0)

    # Caso 1: Sem seleção - insere as tags
    app.txt_ocr.delete("1.0", tk.END)
    app._format_wrap_selection("<b>", "</b>")
    assert app.txt_ocr.get("1.0", "end-1c") == "<b></b>"

    # Caso 2: Com seleção de texto
    app.txt_ocr.delete("1.0", tk.END)
    app.txt_ocr.insert("1.0", "investigador")
    app.txt_ocr.tag_add("sel", "1.0", "1.end")
    app._format_wrap_selection("<i>", "</i>")
    assert app.txt_ocr.get("1.0", "end-1c") == "<i>investigador</i>"


def test_accept_all_and_next(app, tmp_path):
    """Testa salvar tudo com _action_accept_all e avançar com _action_next."""
    dummy_json_file = tmp_path / "card.json"
    dummy_json_file.write_text("[]", encoding="utf-8")

    app.current_card = {"code": "06026", "name": "Antigo Nome", "text": "Antigo Texto"}
    app.current_card_file = dummy_json_file
    app.json_fields = {"name": "Antigo Nome", "text": "Antigo Texto"}
    app.ocr_text_by_field = {"name": "Novo Nome", "text": "Novo Texto"}
    app._field_keys = ["name", "text"]
    app._select_field_by_index(0)

    with patch("main.card_data.save_card") as mock_save:
        res = app._action_accept_all()
        assert res is True
        mock_save.assert_called_once_with(
            app.current_card,
            dummy_json_file,
            {"name": "Novo Nome", "text": "Novo Texto"}
        )

    # Teste do _action_next
    app._action_next()
    assert app.current_card is None
    assert app.current_card_file is None
    assert app._current_field_key is None
    assert app.is_static_preview is False


def test_shortcut_handlers(app):
    """Testa se os métodos manipuladores de atalho chamam as ações correspondentes e retornam 'break'."""
    with patch.object(app, "_capture_and_process") as mock_cap:
        app.btn_capture.config(state="normal")
        ret = app._on_shortcut_capture()
        assert ret == "break"
        mock_cap.assert_called_once()

    with patch.object(app, "_action_accept_all") as mock_accept_all:
        ret = app._on_shortcut_accept_all()
        assert ret == "break"
        mock_accept_all.assert_called_once()

    with patch.object(app, "_action_accept") as mock_accept:
        ret = app._on_shortcut_accept_single()
        assert ret == "break"
        mock_accept.assert_called_once()

    with patch.object(app, "_action_next") as mock_next:
        ret = app._on_shortcut_next()
        assert ret == "break"
        mock_next.assert_called_once()

    with patch.object(app, "_action_accept_all_and_next") as mock_combo:
        ret = app._on_shortcut_accept_all_and_next()
        assert ret == "break"
        mock_combo.assert_called_once()

    with patch.object(app, "after") as mock_after:
        ret_tab = app._on_tab_key()
        assert ret_tab == "break"
        mock_after.assert_called_once_with(20, app._next_field)

    with patch.object(app, "after") as mock_after:
        ret_stab = app._on_shift_tab_key()
        assert ret_stab == "break"
        mock_after.assert_called_once_with(20, app._prev_field)

