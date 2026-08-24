# Arkham Horror LCG — Translation Checker

Ferramenta local em Python para conferir traduções portuguesas de cartas físicas de **Arkham Horror: The Card Game**.

## O que faz

1. Abre a webcam e mostra o vídeo ao vivo (com controle de orientação: Paisagem ou Retrato 90°/180°/270°)
2. Permite escolher o motor de análise: **PaddleOCR (Local)** ou **LLM Multimodal (Google Gemini ou Ollama)** via modal de configurações (`⚙️ Configurar`)
3. Você pode capturar da câmera (`Shift+Enter`) ou clicar em **BUSCAR CARTA NO PC** para selecionar uma imagem salva no computador
4. O motor analisa a imagem, identifica automaticamente o código da carta (ex.: `06026`) e classifica os campos (`name`, `traits`, `text`, `flavor`, etc.)
5. Busca a carta correspondente nos arquivos JSON em `translations/pt/pack/tde/`
6. Compara campo a campo a tradução do JSON com o texto oficial reconhecido
7. Mostra as diferenças com highlighting colorido
8. Você escolhe: **ACEITAR** (salva no JSON preservando símbolos `[reaction]`, `[action]`, etc.), **MANTER** ou **PRÓXIMA CARTA** (você pode editar o texto diretamente no campo a qualquer momento)

---

## Instalação

Pré-requisito: [uv](https://github.com/astral-sh/uv) instalado.

**Passo 1** — Instale o suporte a Tkinter (se estiver no macOS usando Python via Homebrew):
```bash
brew install python-tk@3.13
```

**Passo 2** — Instale as demais dependências:
```bash
uv sync
```

---

## Execução

```bash
uv run python main.py
```

### Configuração de LLM (Opcional)
Clique no botão **`⚙️ Configurar`** na interface para alternar entre:
- **PaddleOCR (Padrão / Local)**: Execução 100% offline via CPU.
- **Google Gemini**: Insira sua chave de API (ou exporte `export GEMINI_API_KEY="..."`) e selecione o modelo (ex.: `gemini-3.7-flash`).
- **OpenAI Compatible**: Suporte a qualquer API compatível com OpenAI (OpenAI oficial, OpenRouter, LM Studio, vLLM, DeepSeek, Groq, etc.) informando a URL e a API Key.
- **Ollama**: Conecte ao seu Ollama local (ex.: `http://localhost:11434`) com modelos de visão como `llama3.2-vision` ou `llava`.

### Atalhos de teclado
- **`Shift + Enter`**: Captura a foto da câmera e congela a imagem para OCR.
- Clique em **`↻ Atualizar`** para retomar o vídeo ao vivo da câmera quando quiser capturar uma nova carta.

---

## Testes

```bash
uv run python -m pytest tests/ -v
```

---

## Como o OCR funciona

O programa usa **PaddleOCR v3** com o modelo de reconhecimento de texto em português (`lang="pt"`), que suporta todos os caracteres acentuados (á, é, ã, ç, etc.).

Fluxo do OCR:

1. **Pré-processamento** (OpenCV): o frame capturado é redimensionado, convertido para escala de cinza, desfocado levemente (Gaussian blur 3×3) e tem o contraste aumentado via CLAHE — isso melhora a qualidade do reconhecimento sem overengineering.

2. **Extração do número**: um crop do canto inferior direito da carta (~20% × 15% da imagem) é passado ao OCR separadamente. O número de 2–3 dígitos encontrado é combinado com o prefixo do pacote (`PACK_PREFIX = "06"`) para formar o código completo (ex.: `"26"` → `"06026"`).

3. **Extração do texto completo**: o OCR processa a imagem inteira e retorna os blocos de texto ordenados de cima para baixo. O resultado é uma string única separada por `\n`.

4. **Classificação por campo**: heurísticas simples tentam separar o texto corrido do OCR nos campos do JSON (nome, traits, texto, flavor). O usuário pode ajustar qualquer campo manualmente pela interface antes de salvar.

5. **Proteção de símbolos**: antes da comparação, os tokens `[reaction]`, `[action]`, `[elder_sign]`, `[willpower]`, etc. são extraídos do JSON e substituídos por placeholders. Após a edição/aceitação, são recolocados na posição proporcional ao texto final.

---

## Arquivos JSON modificados

Os arquivos modificados ficam em:

```
translations/pt/pack/tde/
├── dsm.json
├── pnr.json
├── sfk.json
├── tde.json
├── tsh.json
├── wgd.json
└── woc.json
```

Cada arquivo é um array JSON de objetos de carta. O programa **só altera os campos** que você aceitar (ex.: `"text"`, `"traits"`, `"flavor"`). Todos os outros campos e cartas permanecem intactos.

O JSON é gravado com `ensure_ascii=True` (ex.: `\u00e9` em vez de `é`), `indent=4` e uma linha final — compatível com o padrão do repositório.

---

## Como mudar a pasta de traduções

Edite `config.py`:

```python
# Caminho para o diretório com os .json de tradução
TRANSLATIONS_PATH = PROJECT_ROOT / "translations" / "pt" / "pack" / "tde"

# Prefixo do código das cartas do ciclo atual
# TDE = "06" | Forgotten Age = "04" | etc.
PACK_PREFIX = "06"
```

Não é necessário alterar nenhum outro arquivo.

---

## Estrutura do projeto

```
auto_translate/
├── main.py          ← interface gráfica (Tkinter)
├── ocr_engine.py    ← PaddleOCR + pré-processamento OpenCV
├── card_data.py     ← leitura e escrita dos JSON
├── text_utils.py    ← proteção de símbolos, diff, comparação
├── config.py        ← configuração (caminhos, prefixo, câmera)
├── tests/
│   └── test_text_utils.py
├── translations/
│   └── pt/pack/tde/   ← arquivos JSON modificados pelo programa
├── pyproject.toml
└── README.md
```

---

## Controle de versão

Use Git normalmente — o programa não cria arquivos de backup, não gera cópias e não tem sistema próprio de versionamento. Cada salvamento é uma alteração simples no arquivo JSON.

```bash
git diff translations/  # ver o que mudou
git add translations/   # adicionar ao commit
git commit -m "Corrige tradução da carta 06026"
```