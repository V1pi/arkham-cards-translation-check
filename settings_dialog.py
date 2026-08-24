"""
Modal de configurações do Arkham Horror LCG Translation Checker.
Permite selecionar entre PaddleOCR e LLMs (Google Gemini ou Ollama),
configurar chaves de API, URLs de host e testar a conexão.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading

import config
import llm_engine


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, on_save_callback=None):
        super().__init__(parent)
        self.title("Configurações — Motor de Reconhecimento")
        self.geometry("520x560")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.on_save_callback = on_save_callback
        self.settings = config.load_settings()

        self._build_ui()
        self._load_values()
        self._update_visibility()

    def _build_ui(self):
        pad_opts = {"padx": 10, "pady": 6}

        # 1. Seletor do Motor
        self.engine_frame = ttk.LabelFrame(self, text="1. Modo de Reconhecimento", padding=8)
        self.engine_frame.pack(fill="x", **pad_opts)

        self.mode_var = tk.StringVar(value="ocr")
        ttk.Radiobutton(
            self.engine_frame,
            text="PaddleOCR (Reconhecimento de Texto Local via CPU)",
            variable=self.mode_var,
            value="ocr",
            command=self._update_visibility,
        ).pack(anchor="w", pady=2)

        ttk.Radiobutton(
            self.engine_frame,
            text="LLM Multimodal (Visão Inteligente + Auto-Classificação de Símbolos)",
            variable=self.mode_var,
            value="llm",
            command=self._update_visibility,
        ).pack(anchor="w", pady=2)

        # 2. Configurações de LLM (visível apenas quando LLM estiver ativo)
        self.llm_frame = ttk.LabelFrame(self, text="2. Configurações de LLM", padding=8)

        ttk.Label(self.llm_frame, text="Provedor:").grid(row=0, column=0, sticky="w", pady=4)
        self.provider_var = tk.StringVar(value="gemini")
        self.provider_combo = ttk.Combobox(
            self.llm_frame,
            textvariable=self.provider_var,
            values=["Google Gemini", "Ollama (Local)"],
            state="readonly",
            width=24,
        )
        self.provider_combo.grid(row=0, column=1, sticky="w", pady=4)
        self.provider_combo.bind("<<ComboboxSelected>>", self._on_provider_changed)

        # Sub-painel: Gemini
        self.gemini_box = ttk.Frame(self.llm_frame)
        self.gemini_box.grid(row=1, column=0, columnspan=2, sticky="ew", pady=4)
        self.gemini_box.columnconfigure(1, weight=1)

        ttk.Label(self.gemini_box, text="API Key:").grid(row=0, column=0, sticky="w", pady=2)
        self.gemini_key_var = tk.StringVar()
        self.gemini_key_entry = ttk.Entry(self.gemini_box, textvariable=self.gemini_key_var, show="*")
        self.gemini_key_entry.grid(row=0, column=1, sticky="ew", padx=4, pady=2)

        self.show_key_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self.gemini_box, text="👁", variable=self.show_key_var, command=self._toggle_key_visibility
        ).grid(row=0, column=2, padx=2)

        ttk.Label(self.gemini_box, text="Modelo:").grid(row=1, column=0, sticky="w", pady=2)
        self.gemini_model_var = tk.StringVar(value="gemini-3.7-flash")
        self.gemini_model_combo = ttk.Combobox(
            self.gemini_box,
            textvariable=self.gemini_model_var,
            values=["gemini-3.7-flash", "gemini-3.5-flash-lite", "gemini-3.6-flash", "gemini-3.5-flash"],
        )
        self.gemini_model_combo.grid(row=1, column=1, sticky="ew", padx=4, pady=2)

        self.btn_fetch_gemini = ttk.Button(
            self.gemini_box, text="🔄", width=3, command=lambda: self._fetch_gemini_models(silent=False)
        )
        self.btn_fetch_gemini.grid(row=1, column=2, padx=2, pady=2)

        self.btn_test_gemini = ttk.Button(
            self.gemini_box, text="🔌 Testar Conexão Gemini", command=self._test_gemini
        )
        self.btn_test_gemini.grid(row=2, column=0, columnspan=3, sticky="e", pady=4)

        # Sub-painel: Ollama
        self.ollama_box = ttk.Frame(self.llm_frame)
        self.ollama_box.grid(row=2, column=0, columnspan=2, sticky="ew", pady=4)
        self.ollama_box.columnconfigure(1, weight=1)

        ttk.Label(self.ollama_box, text="Host URL:").grid(row=0, column=0, sticky="w", pady=2)
        self.ollama_url_var = tk.StringVar(value="http://localhost:11434")
        ttk.Entry(self.ollama_box, textvariable=self.ollama_url_var).grid(
            row=0, column=1, columnspan=2, sticky="ew", padx=4, pady=2
        )

        ttk.Label(self.ollama_box, text="Modelo:").grid(row=1, column=0, sticky="w", pady=2)
        self.ollama_model_var = tk.StringVar(value="llama3.2-vision")
        self.ollama_model_combo = ttk.Combobox(
            self.ollama_box,
            textvariable=self.ollama_model_var,
            values=["llama3.2-vision", "llava", "minicpm-v", "qwen2.5-vl"],
        )
        self.ollama_model_combo.grid(row=1, column=1, sticky="ew", padx=4, pady=2)

        self.btn_fetch_ollama = ttk.Button(
            self.ollama_box, text="🔄", width=3, command=lambda: self._fetch_ollama_models(silent=False)
        )
        self.btn_fetch_ollama.grid(row=1, column=2, padx=2, pady=2)

        self.btn_test_ollama = ttk.Button(
            self.ollama_box, text="🔌 Testar Conexão Ollama", command=self._test_ollama
        )
        self.btn_test_ollama.grid(row=2, column=0, columnspan=3, sticky="e", pady=4)

        # 3. Configurações Gerais
        self.general_frame = ttk.LabelFrame(self, text="3. Configurações do Pacote", padding=8)
        self.general_frame.pack(fill="x", **pad_opts)
        self.general_frame.columnconfigure(1, weight=1)

        ttk.Label(self.general_frame, text="Prefixo do Ciclo:").grid(row=0, column=0, sticky="w", pady=2)
        self.pack_prefix_var = tk.StringVar(value="06")
        ttk.Entry(self.general_frame, textvariable=self.pack_prefix_var, width=8).grid(
            row=0, column=1, sticky="w", padx=4, pady=2
        )
        ttk.Label(self.general_frame, text="(TDE = 06, Forgotten Age = 04, etc.)", foreground="#888").grid(
            row=0, column=2, sticky="w"
        )

        # Status / Feedback
        self.status_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.status_var, wraplength=480, foreground="#007acc").pack(
            fill="x", padx=14, pady=4
        )

        # 4. Botões de Ação
        btn_row = ttk.Frame(self)
        btn_row.pack(fill="x", side="bottom", padx=10, pady=10)

        ttk.Button(btn_row, text="💾 Salvar Configurações", command=self._save_settings).pack(
            side="right", padx=4
        )
        ttk.Button(btn_row, text="Cancelar", command=self.destroy).pack(side="right", padx=4)

    def _toggle_key_visibility(self):
        show = "" if self.show_key_var.get() else "*"
        self.gemini_key_entry.config(show=show)

    def _load_values(self):
        self.mode_var.set(self.settings.get("recognition_mode", "ocr"))

        provider = self.settings.get("llm_provider", "gemini")
        self.provider_combo.current(0 if provider == "gemini" else 1)

        self.gemini_key_var.set(self.settings.get("gemini_api_key", ""))
        self.gemini_model_var.set(self.settings.get("gemini_model", "gemini-3.7-flash"))

        self.ollama_url_var.set(self.settings.get("ollama_url", "http://localhost:11434"))
        self.ollama_model_var.set(self.settings.get("ollama_model", "llama3.2-vision"))

        self.pack_prefix_var.set(self.settings.get("pack_prefix", "06"))

        # Carrega modelos em segundo plano se configurados
        if self.gemini_key_var.get().strip():
            self._fetch_gemini_models(silent=True)
        if self.ollama_url_var.get().strip():
            self._fetch_ollama_models(silent=True)

    def _update_visibility(self):
        mode = self.mode_var.get()
        if mode == "llm":
            self.llm_frame.pack(fill="x", after=self.engine_frame, padx=10, pady=6)
            self._on_provider_changed()
            self.geometry("520x560")
        else:
            self.llm_frame.pack_forget()
            self.geometry("520x290")

    def _on_provider_changed(self, event=None):
        if self.mode_var.get() != "llm":
            return
        is_gemini = self.provider_combo.current() == 0
        if is_gemini:
            self.gemini_box.grid()
            self.ollama_box.grid_remove()
            if self.gemini_key_var.get().strip() and len(self.gemini_model_combo["values"]) <= 4:
                self._fetch_gemini_models(silent=True)
        else:
            self.gemini_box.grid_remove()
            self.ollama_box.grid()
            if self.ollama_url_var.get().strip() and len(self.ollama_model_combo["values"]) <= 4:
                self._fetch_ollama_models(silent=True)

    def _fetch_gemini_models(self, silent: bool = False):
        key = self.gemini_key_var.get().strip()
        if not key:
            if not silent:
                messagebox.showwarning("Gemini", "Informe a API Key antes de buscar modelos.", parent=self)
            return

        if not silent:
            self.status_var.set("⏳ Carregando modelos da API do Google Gemini...")
            self.btn_fetch_gemini.config(state="disabled")

        def run():
            ok, models, msg = llm_engine.fetch_gemini_models(key)
            self.after(0, lambda s=ok, m=models, t=msg: self._on_gemini_models_loaded(s, m, t, silent))

        threading.Thread(target=run, daemon=True).start()

    def _on_gemini_models_loaded(self, ok: bool, models: list[str], msg: str, silent: bool):
        self.btn_fetch_gemini.config(state="normal")
        if ok and models:
            self.gemini_model_combo["values"] = models
            current = self.gemini_model_var.get()
            if current not in models:
                self.gemini_model_var.set(models[0])
            if not silent:
                self.status_var.set(f"✅ {msg}")
        elif not silent:
            self.status_var.set(f"❌ {msg}")
            messagebox.showerror("Erro ao carregar modelos", msg, parent=self)

    def _fetch_ollama_models(self, silent: bool = False):
        url = self.ollama_url_var.get().strip()
        if not url:
            if not silent:
                messagebox.showwarning("Ollama", "Informe o Host URL do Ollama.", parent=self)
            return

        if not silent:
            self.status_var.set(f"⏳ Buscando modelos no Ollama ({url})...")
            self.btn_fetch_ollama.config(state="disabled")

        def run():
            ok, models, msg = llm_engine.fetch_ollama_models(url)
            self.after(0, lambda s=ok, m=models, t=msg: self._on_ollama_models_loaded(s, m, t, silent))

        threading.Thread(target=run, daemon=True).start()

    def _on_ollama_models_loaded(self, ok: bool, models: list[str], msg: str, silent: bool):
        self.btn_fetch_ollama.config(state="normal")
        if ok and models:
            self.ollama_model_combo["values"] = models
            current = self.ollama_model_var.get()
            if current not in models:
                self.ollama_model_var.set(models[0])
            if not silent:
                self.status_var.set(f"✅ {msg}")
        elif not silent:
            self.status_var.set(f"❌ {msg}")
            messagebox.showerror("Erro ao carregar modelos", msg, parent=self)

    def _test_gemini(self):
        key = self.gemini_key_var.get().strip()
        model = self.gemini_model_var.get().strip()
        self.status_var.set("⏳ Testando conexão com a API do Google Gemini...")
        self.btn_test_gemini.config(state="disabled")

        def run():
            ok, msg = llm_engine.test_gemini_connection(key, model)
            self.after(0, lambda s=ok, m=msg, b=self.btn_test_gemini: self._on_test_result(s, m, b))
            # Atualiza lista de modelos simultaneamente
            self.after(0, lambda: self._fetch_gemini_models(silent=True))

        threading.Thread(target=run, daemon=True).start()

    def _test_ollama(self):
        url = self.ollama_url_var.get().strip()
        model = self.ollama_model_var.get().strip()
        self.status_var.set(f"⏳ Conectando ao Ollama em {url}...")
        self.btn_test_ollama.config(state="disabled")

        def run():
            ok, msg = llm_engine.test_ollama_connection(url, model)
            self.after(0, lambda s=ok, m=msg, b=self.btn_test_ollama: self._on_test_result(s, m, b))
            # Atualiza lista de modelos simultaneamente
            self.after(0, lambda: self._fetch_ollama_models(silent=True))

        threading.Thread(target=run, daemon=True).start()

    def _on_test_result(self, success: bool, message: str, btn):
        btn.config(state="normal")
        if success:
            self.status_var.set(f"✅ {message}")
            messagebox.showinfo("Conexão OK", message, parent=self)
        else:
            self.status_var.set(f"❌ {message}")
            messagebox.showerror("Falha na Conexão", message, parent=self)

    def _save_settings(self):
        provider = "gemini" if self.provider_combo.current() == 0 else "ollama"
        new_settings = {
            "recognition_mode": self.mode_var.get(),
            "llm_provider": provider,
            "gemini_api_key": self.gemini_key_var.get().strip(),
            "gemini_model": self.gemini_model_var.get().strip(),
            "ollama_url": self.ollama_url_var.get().strip(),
            "ollama_model": self.ollama_model_var.get().strip(),
            "pack_prefix": self.pack_prefix_var.get().strip(),
        }

        config.update_settings(new_settings)
        if self.on_save_callback:
            self.on_save_callback(new_settings)

        messagebox.showinfo("Configurações", "Configurações salvas com sucesso!", parent=self)
        self.destroy()
