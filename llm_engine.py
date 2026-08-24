"""
Módulo de integração com LLMs multimodais (Google Gemini e Ollama).
Lê a imagem da carta, identifica o código e classifica os campos diretamente em JSON estruturado.
"""

import base64
import json
import re
import urllib.request
import urllib.error
import cv2
import numpy as np
from pathlib import Path

import config

CARD_ANALYSIS_PROMPT = """Você é um assistente especialista no jogo de cartas "Arkham Horror: The Card Game" (Arkham Horror LCG) em Português.
Sua tarefa é analisar visualmente a imagem da carta fornecida e extrair as informações estruturadas em formato JSON estrito.

Retorne APENAS um objeto JSON válido (sem blocos de código markdown adicionais ou texto fora do JSON) com o seguinte esquema:

{
  "code": "Código numérico de 5 dígitos da carta (ex.: '06026' ou '06202'). No canto inferior direito da carta há um número impresso de 2 ou 3 dígitos (ex.: '26' ou '202'). O prefixo do pacote é '{PACK_PREFIX}'. Se o número for '26', o código é '{PACK_PREFIX}026'. Se for '202', é '{PACK_PREFIX}202'. Se não conseguir ler com certeza, retorne null.",
  "name": "Nome/Título da carta no topo (ex.: 'Alvo Fácil', 'Palavra de Comando'). Não use tags HTML no nome.",
  "subname": "Subtítulo da carta logo abaixo do nome, se houver (geralmente em cartas únicas com um asterisco ou personagens). Se não houver, use null.",
  "traits": "Características/Traits da carta logo abaixo da ilustração ou nome, terminando com ponto final (ex.: 'Truque. Miríade.' ou 'Magia.'). Não use tags HTML como <i> ou <b> aqui, retorne apenas o texto puro dos traits.",
  "text": "Texto principal de regras da carta. MANTENHA as quebras de linha com \\n.
    - FORMATAÇÃO HTML: Caso o texto na imagem esteja em negrito, use o delimitador html <b></b> (ex.: '<b>Forçado</b> - ', '<b>Ação:</b>'). Caso esteja em itálico, use o delimitador html <i></i> (ex.: '<i>(Limite de 1 por rodada.)</i>', 'carta de <i>Magia</i>').
    - SÍMBOLOS DO JOGO: Substitua qualquer ícone ou símbolo do jogo no texto pelos marcadores correspondentes entre colchetes:
      - Gatilhos e Ações:
        - Ícone de Ação (seta) -> [action]
        - Ícone de Reação (seta curva) -> [reaction]
        - Ícone de Ação Rápida / Gatilho Livre (raio) -> [fast]
      - Perícias:
        - Ícone de Vontade (cabeça) -> [willpower]
        - Ícone de Intelecto (livro) -> [intellect]
        - Ícone de Combate (punho) -> [combat]
        - Ícone de Agilidade (pé) -> [agility]
        - Ícone Coringa (interrogação) -> [wild]
      - Tokens de Caos:
        - Sinal dos Anciãos -> [elder_sign]
        - Caveira -> [skull]
        - Cultista -> [cultist]
        - Tabuleta -> [tablet]
        - Coisa Anciã -> [elder_thing]
        - Falha Automática (tentáculos) -> [auto_fail]
        - Bênção -> [bless]
        - Maldição -> [curse]
        - Gelo -> [frost]
      - Classes:
        - Guardião -> [guardian]
        - Buscador -> [seeker]
        - Ladino -> [rogue]
        - Místico -> [mystic]
        - Sobrevivente -> [survivor]
        - Neutro -> [neutral]
      - Atributos e Mecânicas:
        - Vida (coração) -> [health]
        - Sanidade (cérebro) -> [sanity]
        - Por Investigador (ícone de pessoa/multiplicador) -> [per_investigator]
        - Sangue -> [blood]
        - Selos de Hemlock Vale -> [seal_a], [seal_b], [seal_c], [seal_d], [seal_e]",
  "flavor": "Texto de ambientação/sabor (flavor text), que fica na parte inferior da caixa de texto. NÃO use tags <i></i> ou <b></b> aqui (flavor é texto puro, pois o jogo já o renderiza naturalmente em itálico). Se não houver, use null.",
  "back_text": "Texto do verso da carta (se for o verso de uma carta dupla face ou local). Aplique as mesmas regras de <b></b>, <i></i> e [símbolos]. Caso contrário, null.",
  "back_flavor": "Flavor text do verso da carta (texto puro, sem tags <i></i> ou <b></b>). Caso contrário, null."
}

Exemplo 1 (Carta 06026 - Alvo Fácil):
{
  "code": "06026",
  "name": "Alvo Fácil",
  "subname": null,
  "traits": "Truque.",
  "text": "Miríade.\\nGanhe 2 recursos e compre 1 carta.\\n[reaction] Após você jogar Alvo Fácil: Jogue outro Alvo Fácil da sua mão, sem custo.",
  "flavor": null,
  "back_text": null,
  "back_flavor": null
}

Exemplo 2 (Carta 06202 - Palavra de Comando):
{
  "code": "06202",
  "name": "Palavra de Comando",
  "subname": null,
  "traits": "Magia.",
  "text": "Nomeie uma carta de <i>Magia</i>. Procure 1 cópia da carta nomeada em seu baralho e compre-a.\\nEmbaralhe o seu baralho.",
  "flavor": "Luz para salvar nossos olhos.\\nCalor para salvar nossa pele.\\nUma fagulha para salvar nossas almas.",
  "back_text": null,
  "back_flavor": null
}

Exemplo 3 (Carta 06162 - Gregory Gry):
{
    "code": "06162",
    "flavor": "Muito antes de receber sua primeira mão, o rapaz fora capaz de observar um homem e discernir o significado de suas apostas.",
    "name": "Gregory Gry",
    "subname": "Jornalista Investigativo",
    "text": "Usa (9 recursos).\n[reaction] Quando você iniciar um teste de perícia, gaste até 3 recursos de Gregory Gry: Se este teste de perícia for bem-sucedido por pelo menos esse valor, gaste essa quantidade de recursos.",
    "traits": "Aliado. Criminoso. Sonhador.",
    "slot": "Aliado"
}
"""


def _frame_to_base64_jpeg(frame_or_path) -> str:
    """Converte um frame numpy (BGR) ou caminho de arquivo em string base64 JPEG."""
    if isinstance(frame_or_path, (str, Path)):
        data = np.fromfile(str(frame_or_path), dtype=np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"Não foi possível abrir a imagem: {frame_or_path}")
        frame = img
    else:
        frame = frame_or_path

    # Redimensiona caso seja excessivamente grande para otimizar velocidade de rede
    h, w = frame.shape[:2]
    max_dim = 1600
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        frame = cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

    success, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if not success:
        raise ValueError("Falha ao codificar imagem para JPEG")

    return base64.b64encode(buffer).decode("utf-8")


def _clean_json_response(raw_text: str) -> dict:
    """Extrai e faz parse de JSON a partir da resposta da LLM."""
    text = raw_text.strip()
    # Remove blocos markdown ```json ... ``` se houver
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

    # Se ainda houver texto ao redor, busca pelo primeiro { até o último }
    match = re.search(r"(\{.*\})", text, flags=re.DOTALL)
    if match:
        text = match.group(1)

    return json.loads(text)


# ---------------------------------------------------------------------------
# Provedor: Google Gemini
# ---------------------------------------------------------------------------
def analyze_with_gemini(
    frame_or_path,
    api_key: str | None = None,
    model: str | None = None,
    pack_prefix: str | None = None,
) -> dict:
    """Envia a imagem para a API do Google Gemini e retorna os campos extraídos."""
    api_key = api_key or config.get_setting("gemini_api_key")
    if not api_key:
        raise ValueError("Chave de API do Google Gemini não configurada. Configure nas Configurações.")

    model = model or config.get_setting("gemini_model", "gemini-3.7-flash")
    pack_prefix = pack_prefix or config.get_setting("pack_prefix", "06")

    b64_image = _frame_to_base64_jpeg(frame_or_path)
    prompt = CARD_ANALYSIS_PROMPT.replace("{PACK_PREFIX}", pack_prefix)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": b64_image,
                        }
                    },
                ]
            }
        ],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.1,
        },
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            candidates = data.get("candidates", [])
            if not candidates:
                raise ValueError("A API do Gemini não retornou respostas válidas.")

            parts = candidates[0].get("content", {}).get("parts", [])
            text_content = parts[0].get("text", "{}") if parts else "{}"
            result_json = _clean_json_response(text_content)
            return _normalize_llm_result(result_json, pack_prefix)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Erro na API do Gemini (HTTP {e.code}): {err_body}")
    except Exception as e:
        raise RuntimeError(f"Falha na requisição para o Gemini: {e}")


# ---------------------------------------------------------------------------
# Provedor: Ollama
# ---------------------------------------------------------------------------
def analyze_with_ollama(
    frame_or_path,
    ollama_url: str | None = None,
    model: str | None = None,
    pack_prefix: str | None = None,
) -> dict:
    """Envia a imagem para o Ollama local e retorna os campos extraídos."""
    ollama_url = ollama_url or config.get_setting("ollama_url", "http://localhost:11434")
    ollama_url = ollama_url.rstrip("/")
    model = model or config.get_setting("ollama_model", "llama3.2-vision")
    pack_prefix = pack_prefix or config.get_setting("pack_prefix", "06")

    b64_image = _frame_to_base64_jpeg(frame_or_path)
    prompt = CARD_ANALYSIS_PROMPT.replace("{PACK_PREFIX}", pack_prefix)

    url = f"{ollama_url}/api/chat"

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [b64_image],
            }
        ],
        "format": "json",
        "stream": False,
        "options": {
            "temperature": 0.1,
        },
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data.get("message", {}).get("content", "{}")
            result_json = _clean_json_response(content)
            return _normalize_llm_result(result_json, pack_prefix)
    except urllib.error.URLError as e:
        raise RuntimeError(f"Não foi possível conectar ao Ollama em '{ollama_url}'. Verifique se o Ollama está rodando. ({e})")
    except Exception as e:
        raise RuntimeError(f"Falha na requisição para o Ollama: {e}")


def _normalize_llm_result(raw_dict: dict, pack_prefix: str) -> dict:
    """Padroniza e sanitiza o dicionário retornado pela LLM."""
    code = raw_dict.get("code")
    if code:
        code_str = str(code).strip()
        # Se veio apenas o número curto (ex.: 26 ou 202), formata com o prefixo
        digits = re.findall(r"\d+", code_str)
        if digits:
            num = digits[0]
            if len(num) <= 3:
                code = pack_prefix + num.zfill(3)
            elif len(num) == 5:
                code = num
            else:
                code = code_str
        else:
            code = code_str

    fields = {}
    field_keys = ["name", "subname", "traits", "text", "flavor", "back_text", "back_flavor"]
    for k in field_keys:
        val = raw_dict.get(k)
        fields[k] = str(val).strip() if val is not None else ""

    return {
        "code": code,
        "fields": fields,
    }


# ---------------------------------------------------------------------------
# Testes de Conexão
# ---------------------------------------------------------------------------
def test_gemini_connection(api_key: str, model: str) -> tuple[bool, str]:
    """Testa se a chave de API e modelo do Gemini são válidos."""
    if not api_key:
        return False, "Chave de API não informada."
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": "Hello, answer with 'OK'."}]}],
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                return True, "Conexão com Google Gemini realizada com sucesso!"
            return False, f"Resposta inesperada (HTTP {resp.status})"
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="ignore")
        return False, f"Erro na API Gemini (HTTP {e.code}): {err}"
    except Exception as e:
        return False, f"Erro de conexão: {e}"


def test_ollama_connection(ollama_url: str, model: str) -> tuple[bool, str]:
    """Testa se o host do Ollama está acessível e se o modelo existe."""
    ollama_url = ollama_url.rstrip("/")
    try:
        # Testa listar modelos instalados no Ollama
        tags_url = f"{ollama_url}/api/tags"
        req = urllib.request.Request(tags_url, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = [m.get("name") for m in data.get("models", [])]
            # Verifica se o modelo especificado está instalado
            model_matched = any(model in m for m in models) if models else False
            if model_matched:
                return True, f"Ollama online! Modelo '{model}' disponível."
            elif models:
                return True, f"Ollama online! Modelos encontrados: {', '.join(models[:3])}"
            return True, "Ollama online!"
    except Exception as e:
        return False, f"Não foi possível conectar ao Ollama em {ollama_url}: {e}"
