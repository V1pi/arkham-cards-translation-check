"""
Arkham Horror LCG Translation Checker — Interface principal.

Uso:
    uv run python main.py
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog, filedialog
import threading
import cv2
import numpy as np
from PIL import Image, ImageTk
from pathlib import Path

import config
import card_data
import text_utils
import ocr_engine


# ---------------------------------------------------------------------------
# Constantes de layout
# ---------------------------------------------------------------------------
CAM_WIDTH = 480
CAM_HEIGHT = 360
REFRESH_MS = 30  # intervalo de atualização do stream (~33 fps)

FIELD_LABELS = {
    "name": "Nome",
    "subname": "Subtítulo",
    "traits": "Traits",
    "text": "Texto",
    "flavor": "Flavor",
    "back_text": "Texto (verso)",
    "back_flavor": "Flavor (verso)",
}

ROTATION_OPTIONS = [
    ("0° (Paisagem/Padrão)", 0),
    ("90° (Retrato)", 90),
    ("180° (Invertido)", 180),
    ("270° (Retrato Invertido)", 270),
]


# ---------------------------------------------------------------------------
# Aplicação principal
# ---------------------------------------------------------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Arkham Horror LCG — Translation Checker")
        self.resizable(True, True)

        # Estado
        self.cap = None
        self.current_camera_index = config.CAMERA_INDEX
        self.camera_rotation = 0  # 0, 90, 180, 270 graus
        self.is_static_preview = False  # se True, exibe imagem fixa carregada de arquivo
        self.all_cards: dict = {}
        self.current_card: dict | None = None
        self.current_card_file: Path | None = None
        self._current_field_key: str | None = None
        self._is_updating_ui: bool = False
        self.captured_frame: np.ndarray | None = None
        self.ocr_text_by_field: dict = {}   # campo → texto OCR classificado
        self.json_fields: dict = {}          # campo → texto do JSON

        self._load_cards()
        self._build_ui()
        self._setup_shortcuts()
        self._open_camera(self.current_camera_index)
        self._update_camera_frame()

    # ------------------------------------------------------------------
    # Atalhos de Teclado
    # ------------------------------------------------------------------
    def _setup_shortcuts(self):
        """Configura atalhos globais de teclado."""
        self.bind_all("<Shift-Return>", self._on_shortcut_capture)

    def _on_shortcut_capture(self, event=None):
        """Manipulador do atalho para capturar a imagem da câmera."""
        if str(self.btn_capture["state"]) != "disabled":
            self._capture_and_ocr()
        return "break"

    # ------------------------------------------------------------------
    # Dados
    # ------------------------------------------------------------------
    def _load_cards(self):
        path = config.TRANSLATIONS_PATH
        self.all_cards = card_data.load_all_cards(path)
        print(f"[info] {len(self.all_cards)} cartas carregadas de {path}")

    # ------------------------------------------------------------------
    # Construção da UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(0, weight=1)

        self._build_left_panel()
        self._build_right_panel()
        self._build_bottom_panel()

    def _build_left_panel(self):
        left = ttk.Frame(self, padding=6)
        left.grid(row=0, column=0, sticky="nsew")
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)

        # Seletor e controles de câmera
        cam_frame = ttk.LabelFrame(left, text="Câmera e Orientação", padding=6)
        cam_frame.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        cam_frame.columnconfigure(1, weight=1)

        # Linha 0: Seleção de câmera
        ttk.Label(cam_frame, text="Câmera:").grid(row=0, column=0, sticky="w", padx=(0, 4), pady=2)
        self.cam_var = tk.StringVar()
        self.cam_combo = ttk.Combobox(cam_frame, textvariable=self.cam_var,
                                       state="readonly", width=16)
        self.cam_combo.grid(row=0, column=1, sticky="ew", padx=(0, 4), pady=2)
        self.cam_combo.bind("<<ComboboxSelected>>", self._on_camera_changed)

        ttk.Button(cam_frame, text="↻ Atualizar", width=10,
                   command=self._on_refresh_camera_clicked).grid(row=0, column=2, pady=2)

        # Linha 1: Orientação / Rotação
        ttk.Label(cam_frame, text="Orientação:").grid(row=1, column=0, sticky="w", padx=(0, 4), pady=2)
        self.rot_var = tk.StringVar()
        self.rot_combo = ttk.Combobox(cam_frame, textvariable=self.rot_var,
                                       state="readonly", width=16)
        self.rot_combo["values"] = [label for label, _ in ROTATION_OPTIONS]
        self.rot_combo.current(0)
        self.rot_combo.grid(row=1, column=1, sticky="ew", padx=(0, 4), pady=2)
        self.rot_combo.bind("<<ComboboxSelected>>", self._on_rotation_changed)

        ttk.Button(cam_frame, text="🔄 Girar 90°", width=10,
                   command=self._rotate_camera_90).grid(row=1, column=2, pady=2)

        self._refresh_camera_list()

        # Canvas do vídeo / prévia
        self.cam_canvas = tk.Canvas(left, width=CAM_WIDTH, height=CAM_HEIGHT,
                                     bg="#1a1a2e", highlightthickness=1,
                                     highlightbackground="#444")
        self.cam_canvas.grid(row=1, column=0, sticky="nsew", pady=4)

        # Botões de captura e carregamento
        btn_frame = ttk.Frame(left)
        btn_frame.grid(row=2, column=0, sticky="ew")
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        self.btn_capture = ttk.Button(btn_frame, text="📷 CAPTURAR (Cmd+Espaço)",
                                       command=self._capture_and_ocr)
        self.btn_capture.grid(row=0, column=0, sticky="ew", padx=(0, 2), pady=2)

        self.btn_load_file = ttk.Button(btn_frame, text="📁 BUSCAR CARTA NO PC",
                                         command=self._load_image_from_file)
        self.btn_load_file.grid(row=0, column=1, sticky="ew", padx=(2, 0), pady=2)

        self.btn_choose = ttk.Button(btn_frame, text="🔍 Escolher por Código (Manual)",
                                      command=self._choose_card_manually)
        self.btn_choose.grid(row=1, column=0, columnspan=2, sticky="ew", pady=2)

        # Status
        self.status_var = tk.StringVar(value="Pronto. Aponte para uma carta ou selecione um arquivo.")
        ttk.Label(left, textvariable=self.status_var, foreground="#888",
                  wraplength=CAM_WIDTH).grid(row=3, column=0, sticky="w", pady=2)

    def _build_right_panel(self):
        right = ttk.Frame(self, padding=6)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(2, weight=1)
        right.rowconfigure(4, weight=1)

        # Info da carta
        info_frame = ttk.LabelFrame(right, text="Carta encontrada", padding=6)
        info_frame.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        info_frame.columnconfigure(1, weight=1)

        self.lbl_code = ttk.Label(info_frame, text="—")
        self.lbl_name = ttk.Label(info_frame, text="—", font=("TkDefaultFont", 10, "bold"))
        ttk.Label(info_frame, text="ID:").grid(row=0, column=0, sticky="w")
        self.lbl_code.grid(row=0, column=1, sticky="w", padx=4)
        ttk.Label(info_frame, text="Nome:").grid(row=1, column=0, sticky="w")
        self.lbl_name.grid(row=1, column=1, sticky="w", padx=4)

        # Seletor de campo
        field_frame = ttk.Frame(right)
        field_frame.grid(row=1, column=0, sticky="ew", pady=(0, 2))
        field_frame.columnconfigure(1, weight=1)

        ttk.Label(field_frame, text="Campo:").grid(row=0, column=0, sticky="w", padx=(0, 4))
        self.field_var = tk.StringVar()
        self.field_combo = ttk.Combobox(field_frame, textvariable=self.field_var,
                                         state="readonly")
        self.field_combo.grid(row=0, column=1, sticky="ew")
        self.field_combo.bind("<<ComboboxSelected>>", self._on_field_selected)

        # Tradução atual (JSON)
        ttk.Label(right, text="Tradução atual (JSON):").grid(row=2, column=0, sticky="w")
        self.txt_json = scrolledtext.ScrolledText(right, height=6, state="disabled",
                                                   wrap=tk.WORD, font=("TkFixedFont", 9))
        self.txt_json.grid(row=3, column=0, sticky="nsew", pady=2)
        right.rowconfigure(3, weight=1)

        # Texto OCR
        ttk.Label(right, text="Texto oficial (OCR):").grid(row=4, column=0, sticky="w")
        self.txt_ocr = scrolledtext.ScrolledText(right, height=6, wrap=tk.WORD,
                                                   font=("TkFixedFont", 9))
        self.txt_ocr.grid(row=5, column=0, sticky="nsew", pady=2)
        right.rowconfigure(5, weight=1)
        self.txt_ocr.bind("<KeyRelease>", self._on_ocr_edit)
        self.txt_ocr.bind("<FocusOut>", self._on_ocr_edit)

        # Nota de classificação de campos
        self.lbl_classify = ttk.Label(
            right,
            text="💡 Ajuste o texto OCR acima se necessário antes de aceitar. A comparação atualiza em tempo real.",
            foreground="#888", wraplength=400
        )
        self.lbl_classify.grid(row=6, column=0, sticky="w")

    def _build_bottom_panel(self):
        bottom = ttk.LabelFrame(self, text="Diferenças", padding=6)
        bottom.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=6, pady=4)
        bottom.columnconfigure(0, weight=1)
        bottom.rowconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # Texto de diff com highlighting
        self.txt_diff = tk.Text(bottom, height=8, wrap=tk.WORD, state="disabled",
                                 font=("TkFixedFont", 9))
        self.txt_diff.grid(row=0, column=0, sticky="nsew")

        # Tags de cor para o diff
        self.txt_diff.tag_configure("equal", foreground="#cccccc")
        self.txt_diff.tag_configure("delete", foreground="#ff6b6b",
                                     background="#3d0000", overstrike=True)
        self.txt_diff.tag_configure("insert", foreground="#6bff6b",
                                     background="#003d00")

        scroll_diff = ttk.Scrollbar(bottom, orient="vertical",
                                     command=self.txt_diff.yview)
        scroll_diff.grid(row=0, column=1, sticky="ns")
        self.txt_diff.config(yscrollcommand=scroll_diff.set)

        # Botões de ação
        btn_row = ttk.Frame(bottom)
        btn_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        ttk.Button(btn_row, text="✅ ACEITAR", command=self._action_accept,
                   style="Accent.TButton").pack(side="left", padx=4)
        ttk.Button(btn_row, text="✏️  EDITAR", command=self._action_edit).pack(side="left", padx=4)
        ttk.Button(btn_row, text="⏭  MANTER", command=self._action_keep).pack(side="left", padx=4)
        ttk.Button(btn_row, text="⏩ PRÓXIMA", command=self._action_next).pack(side="left", padx=4)

    # ------------------------------------------------------------------
    # Câmera e Renderização
    # ------------------------------------------------------------------
    def _refresh_camera_list(self):
        """Detecta câmeras disponíveis e popula o dropdown."""
        indices = ocr_engine.list_cameras()
        if not indices:
            indices = [0]  # fallback

        labels = [f"Câmera {i}" for i in indices]
        self.cam_combo["values"] = labels
        self._camera_indices = indices

        # Seleciona a câmera atual
        if self.current_camera_index in indices:
            self.cam_combo.current(indices.index(self.current_camera_index))
        else:
            self.cam_combo.current(0)
            self.current_camera_index = indices[0]

    def _on_camera_changed(self, event=None):
        idx = self._camera_indices[self.cam_combo.current()]
        if idx != self.current_camera_index or self.is_static_preview:
            self.is_static_preview = False
            self._open_camera(idx)

    def _on_refresh_camera_clicked(self):
        """Atualiza a lista de câmeras e retoma o stream ao vivo."""
        self.is_static_preview = False
        self._refresh_camera_list()
        if self.current_camera_index is not None:
            self._open_camera(self.current_camera_index)
        self.status_var.set("🎥 Câmera ao vivo retomada.")

    def _on_rotation_changed(self, event=None):
        idx = self.rot_combo.current()
        if 0 <= idx < len(ROTATION_OPTIONS):
            self.camera_rotation = ROTATION_OPTIONS[idx][1]

    def _rotate_camera_90(self):
        """Incrementa a rotação em 90 graus."""
        self.camera_rotation = (self.camera_rotation + 90) % 360
        for i, (_, deg) in enumerate(ROTATION_OPTIONS):
            if deg == self.camera_rotation:
                self.rot_combo.current(i)
                break

    def _open_camera(self, index: int):
        """Fecha a câmera atual e abre a nova."""
        if self.cap and self.cap.isOpened():
            self.cap.release()
        self.cap = cv2.VideoCapture(index)
        self.current_camera_index = index
        if not self.cap.isOpened():
            self.status_var.set(f"⚠️  Câmera {index} não encontrada.")

    def _display_frame_on_canvas(self, frame_bgr: np.ndarray):
        """Renderiza uma imagem no canvas mantendo aspect ratio e centralizado."""
        h, w = frame_bgr.shape[:2]
        if h == 0 or w == 0:
            return

        scale = min(CAM_WIDTH / w, CAM_HEIGHT / h)
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))

        resized = cv2.resize(frame_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)
        canvas_bg = np.full((CAM_HEIGHT, CAM_WIDTH, 3), 26, dtype=np.uint8)  # fundo #1a1a2e

        y_off = (CAM_HEIGHT - new_h) // 2
        x_off = (CAM_WIDTH - new_w) // 2
        canvas_bg[y_off:y_off + new_h, x_off:x_off + new_w] = resized

        rgb = cv2.cvtColor(canvas_bg, cv2.COLOR_BGR2RGB)
        imgtk = ImageTk.PhotoImage(image=Image.fromarray(rgb))
        self.cam_canvas.imgtk = imgtk
        self.cam_canvas.create_image(0, 0, anchor="nw", image=imgtk)

    def _update_camera_frame(self):
        """Loop de atualização do frame da câmera no canvas (usa after)."""
        if not self.is_static_preview and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                # Aplica rotação
                if self.camera_rotation == 90:
                    frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
                elif self.camera_rotation == 180:
                    frame = cv2.rotate(frame, cv2.ROTATE_180)
                elif self.camera_rotation == 270:
                    frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

                self._last_frame = frame  # guarda para captura já na orientação correta
                self._display_frame_on_canvas(frame)

        self.after(REFRESH_MS, self._update_camera_frame)

    # ------------------------------------------------------------------
    # Captura, Carregamento de Arquivo e OCR
    # ------------------------------------------------------------------
    def _set_processing_state(self, processing: bool, status_msg: str = ""):
        state = "disabled" if processing else "normal"
        self.btn_capture.config(state=state)
        self.btn_load_file.config(state=state)
        self.btn_choose.config(state=state)
        if status_msg:
            self.status_var.set(status_msg)

    def _capture_and_ocr(self):
        """Captura o frame atual da câmera, congela o preview e roda o OCR em background."""
        frame = getattr(self, '_last_frame', None)
        if frame is None:
            messagebox.showwarning("Câmera", "Nenhum frame disponível. Verifique a câmera.")
            return

        # Congela o preview com a imagem capturada para mostrar o que está sendo processado
        self.is_static_preview = True
        self.captured_frame = frame.copy()
        self._display_frame_on_canvas(self.captured_frame)
        self._set_processing_state(True, "⏳ Imagem capturada! Processando OCR... (clique ↻ Atualizar para retomar a câmera)")

        def run():
            try:
                code = ocr_engine.extract_card_number(self.captured_frame)
                full_text = ocr_engine.extract_text_from_image(self.captured_frame)
                self.after(0, lambda: self._on_ocr_done(code, full_text))
            except Exception as e:
                self.after(0, lambda: self._on_ocr_error(str(e)))
            finally:
                self.after(0, lambda: self._set_processing_state(False))

        threading.Thread(target=run, daemon=True).start()

    def _load_image_from_file(self):
        """Abre diálogo para selecionar arquivo de imagem e executa OCR."""
        filepath = filedialog.askopenfilename(
            title="Buscar foto da carta no computador",
            filetypes=[
                ("Imagens", "*.jpg *.jpeg *.png *.webp *.bmp *.tiff *.JPG *.JPEG *.PNG"),
                ("Todos os arquivos", "*.*")
            ],
            parent=self
        )
        if not filepath:
            return

        try:
            # Lê imagem suportando caminhos com acentos / unicode
            data = np.fromfile(filepath, dtype=np.uint8)
            img = cv2.imdecode(data, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError("Formato de imagem não reconhecido ou arquivo inválido.")
        except Exception as e:
            messagebox.showerror("Erro ao carregar imagem", f"Não foi possível abrir o arquivo:\n{e}")
            return

        self.is_static_preview = True
        self.captured_frame = img.copy()
        self._display_frame_on_canvas(img)

        filename = Path(filepath).name
        self._set_processing_state(True, f"⏳ Processando OCR no arquivo '{filename}'... aguarde.")

        def run():
            try:
                code = ocr_engine.extract_card_number(img)
                full_text = ocr_engine.extract_text_from_image(img)
                self.after(0, lambda: self._on_ocr_done(code, full_text))
            except Exception as e:
                self.after(0, lambda: self._on_ocr_error(str(e)))
            finally:
                self.after(0, lambda: self._set_processing_state(False))

        threading.Thread(target=run, daemon=True).start()

    def _on_ocr_done(self, code: str | None, full_text: str):
        if not code:
            # Não reconheceu o código — pede confirmação manual
            code = simpledialog.askstring(
                "Código não reconhecido",
                "O OCR não identificou o código da carta automaticamente.\n"
                f"Digite o código manualmente (ex.: {config.PACK_PREFIX}026):",
                parent=self
            )

        if not code:
            self.status_var.set("Operação cancelada.")
            return

        code = code.strip()
        entry = card_data.find_card(code, self.all_cards)
        if not entry:
            self.status_var.set(f"❌ Carta '{code}' não encontrada nos JSON.")
            messagebox.showwarning("Não encontrada", f"Código '{code}' não está nos arquivos de tradução.")
            return

        self._load_card(entry, full_text)

    def _on_ocr_error(self, error: str):
        self.status_var.set(f"❌ Erro no OCR: {error}")
        messagebox.showerror("Erro OCR", f"Ocorreu um erro durante o OCR:\n{error}")

    def _choose_card_manually(self):
        """Abre diálogo para o usuário digitar o código da carta manualmente."""
        code = simpledialog.askstring(
            "Escolher Carta",
            f"Digite o código da carta (ex.: {config.PACK_PREFIX}026):",
            parent=self
        )
        if not code:
            return

        code = code.strip()
        entry = card_data.find_card(code, self.all_cards)
        if not entry:
            messagebox.showwarning("Não encontrada", f"Código '{code}' não está nos arquivos de tradução.")
            return

        # Carrega carta sem OCR — campos OCR ficam em branco para o usuário preencher
        self._load_card(entry, full_ocr_text="")

    # ------------------------------------------------------------------
    # Carregamento da carta na UI
    # ------------------------------------------------------------------
    def _load_card(self, entry: dict, full_ocr_text: str):
        """Preenche a UI com os dados da carta e o texto OCR."""
        card = entry["card"]
        self.current_card = card
        self.current_card_file = entry["file"]

        # Campos do JSON
        self.json_fields = card_data.get_card_text_fields(card)

        # Classifica o texto OCR nos campos
        raw_ocr_by_field = _classify_ocr_text(full_ocr_text, self.json_fields)

        # Infere e posiciona os símbolos [token] do JSON dentro do texto OCR para cada campo
        self.ocr_text_by_field = {}
        for field, raw_text in raw_ocr_by_field.items():
            json_text = self.json_fields.get(field, "")
            if raw_text and json_text:
                self.ocr_text_by_field[field] = text_utils.apply_ocr_to_json(json_text, raw_text)
            else:
                self.ocr_text_by_field[field] = raw_text

        # Atualiza labels de informação
        self.lbl_code.config(text=card.get("code", "?"))
        self.lbl_name.config(text=card.get("name", "?"))

        # Popula o seletor de campo com os campos disponíveis
        available_fields = list(self.json_fields.keys())
        field_labels = [f"{FIELD_LABELS.get(f, f)}" for f in available_fields]
        self.field_combo["values"] = field_labels
        self._field_keys = available_fields

        if available_fields:
            self.field_combo.current(0)
            self._show_field(available_fields[0])

        self.status_var.set(f"✅ Carta {card.get('code')} — {card.get('name')} carregada.")

    def _on_field_selected(self, event=None):
        idx = self.field_combo.current()
        if idx >= 0 and idx < len(self._field_keys):
            new_field = self._field_keys[idx]
            if new_field != self._current_field_key:
                # Salva o texto do campo anterior ANTES de carregar o novo
                if self._current_field_key:
                    self.ocr_text_by_field[self._current_field_key] = self.txt_ocr.get("1.0", "end-1c")
                self._show_field(new_field)

    def _show_field(self, field: str):
        """Atualiza os painéis de JSON, OCR e diff para o campo selecionado."""
        self._is_updating_ui = True
        try:
            self._current_field_key = field
            json_text = self.json_fields.get(field, "")
            ocr_text = self.ocr_text_by_field.get(field, "")

            # JSON (readonly)
            self.txt_json.config(state="normal")
            self.txt_json.delete("1.0", tk.END)
            self.txt_json.insert(tk.END, json_text)
            self.txt_json.config(state="disabled")

            # OCR (editável)
            self.txt_ocr.delete("1.0", tk.END)
            self.txt_ocr.insert(tk.END, ocr_text)

            # Diff
            self._update_diff(json_text, ocr_text)
        finally:
            self._is_updating_ui = False

    def _update_diff(self, json_text: str, ocr_text: str):
        """Atualiza o painel de diferenças com highlighting colorido."""
        self.txt_diff.config(state="normal")
        self.txt_diff.delete("1.0", tk.END)

        segments = text_utils.build_diff_html_segments(json_text, ocr_text)
        for text_seg, tag in segments:
            self.txt_diff.insert(tk.END, text_seg, tag)

        self.txt_diff.config(state="disabled")

    # ------------------------------------------------------------------
    # Ações
    # ------------------------------------------------------------------
    def _action_accept(self):
        """Aceita o texto OCR atual e salva no JSON."""
        if not self.current_card:
            return
        field = getattr(self, '_current_field_key', None)
        if not field:
            return

        ocr_text = self.txt_ocr.get("1.0", "end-1c").strip()
        self.ocr_text_by_field[field] = ocr_text
        json_text = self.json_fields.get(field, "")

        # Aplica OCR preservando símbolos do JSON original
        new_text = text_utils.apply_ocr_to_json(json_text, ocr_text)

        try:
            card_data.save_card(self.current_card, self.current_card_file,
                                 {field: new_text})
            # Atualiza estado local
            self.json_fields[field] = new_text
            self.current_card[field] = new_text
            self.ocr_text_by_field[field] = new_text
            self._show_field(field)
            self.status_var.set(f"✅ Campo '{FIELD_LABELS.get(field, field)}' salvo no JSON.")
        except Exception as e:
            messagebox.showerror("Erro ao salvar", str(e))

    def _action_edit(self):
        """Foca no campo OCR para edição manual."""
        self.txt_ocr.focus_set()
        self.txt_ocr.see(tk.END)
        self.status_var.set("✏️  Edite o texto no campo 'Texto oficial (OCR)' — a comparação atualiza em tempo real.")

    def _on_ocr_edit(self, event=None):
        if getattr(self, '_is_updating_ui', False):
            return
        field = getattr(self, '_current_field_key', None)
        if field:
            ocr_text = self.txt_ocr.get("1.0", "end-1c")
            self.ocr_text_by_field[field] = ocr_text
            json_text = self.json_fields.get(field, "")
            self._update_diff(json_text, ocr_text)

    def _action_keep(self):
        """Não altera nada."""
        self.status_var.set("⏭  Mantido sem alteração.")

    def _action_next(self):
        """Pula para a próxima carta (limpa a UI e retoma vídeo)."""
        self._is_updating_ui = True
        try:
            self.is_static_preview = False
            self.current_card = None
            self.current_card_file = None
            self._current_field_key = None
            self.json_fields = {}
            self.ocr_text_by_field = {}

            self.lbl_code.config(text="—")
            self.lbl_name.config(text="—")
            self.field_combo.set("")
            self.field_combo["values"] = []
            self.txt_json.config(state="normal")
            self.txt_json.delete("1.0", tk.END)
            self.txt_json.config(state="disabled")
            self.txt_ocr.delete("1.0", tk.END)
            self.txt_diff.config(state="normal")
            self.txt_diff.delete("1.0", tk.END)
            self.txt_diff.config(state="disabled")

            self.status_var.set("Pronto. Aponte para uma carta ou busque uma imagem no PC.")
        finally:
            self._is_updating_ui = False

    # ------------------------------------------------------------------
    # Limpeza
    # ------------------------------------------------------------------
    def destroy(self):
        if self.cap and self.cap.isOpened():
            self.cap.release()
        super().destroy()


# ---------------------------------------------------------------------------
# Heurísticas de classificação de campos OCR
# ---------------------------------------------------------------------------
def _classify_ocr_text(full_text: str, json_fields: dict) -> dict:
    """
    Tenta classificar o texto OCR corrido nos campos do JSON usando heurísticas.

    Estratégia:
    - O texto da carta tem uma ordem visual típica:
        1. Título (linha curta, topo)
        2. Traits (curtos, terminam com ponto, ex. "Magia." / "Item. Arma.")
        3. Texto do corpo (parágrafo principal)
        4. Flavor (itálico — geralmente no fim da carta ou com aspas)

    Retorna dict { campo: texto_ocr_classificado }.
    O usuário pode ajustar pelo campo OCR editável.
    """
    if not full_text.strip():
        return {field: "" for field in json_fields}

    lines = [l.strip() for l in full_text.split('\n') if l.strip()]
    result = {}

    # --- Nome ---
    if "name" in json_fields:
        name_candidate = ""
        for line in lines[:5]:
            # Ignora números isolados ou palavras genéricas de topo como EVENTO/ATIVO
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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app = App()
    app.mainloop()
