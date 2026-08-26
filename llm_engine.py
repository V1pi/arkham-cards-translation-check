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
import card_data

CARD_ANALYSIS_PROMPT = """Você é um assistente especialista no jogo de cartas "Arkham Horror: The Card Game" (Arkham Horror LCG) em Português.
Sua tarefa é analisar visualmente a imagem da carta fornecida e extrair as informações estruturadas em formato JSON estrito.

Retorne APENAS um objeto JSON válido (sem blocos de código markdown adicionais ou texto fora do JSON) com o seguinte esquema:

{
  "code": "Código da carta (ex.: '06026', '06202' ou '06015a'). No canto inferior direito da carta há um número impresso de 2 ou 3 dígitos, que pode conter uma letra de sufixo (ex.: '26', '202' ou '15a'). O prefixo do pacote é '{PACK_PREFIX}'. Se o número for '26', o código é '{PACK_PREFIX}026'. Se for '15a', o código é '{PACK_PREFIX}015a'. Se não conseguir ler com certeza, retorne null.",
  "name": "Nome/Título da carta no topo (ex.: 'Alvo Fácil', 'Palavra de Comando'). Não use tags HTML no nome.",
  "subname": "Subtítulo da carta logo abaixo do nome, se houver (geralmente em cartas únicas com um asterisco ou personagens). Se não houver, use null.",
  "traits": "Características/Traits da carta logo abaixo da ilustração ou nome, terminando com ponto final (ex.: 'Truque. Miríade.' ou 'Magia.'). Não use tags HTML como <i> ou <b> aqui, retorne apenas o texto puro dos traits.",
  "text": "Texto principal de regras da carta. Fica abaixo das traits. MANTENHA as quebras de linha com \\n.
    - REGRAS COMPLETAS: Transcreva com extrema atenção TODO o texto da caixa de regras na íntegra, sem omitir parágrafos. Isso inclui custos adicionais para jogar, restrições, habilidades constantes, reações ([reaction]), ações ([action]), gatilhos livres ([fast]) e textos explicativos entre parênteses. Não transcreva apenas as habilidades com ícones ou termos em negrito.
    - PONTUAÇÃO E HIFENIZAÇÃO (MUITO IMPORTANTE):
      - USE SEMPRE O HÍFEN SIMPLES '-' (ASCII 0x2D) e NUNCA use travessão ('—') ou meia-risca ('–') após palavras-chave, gatilhos ou no meio do texto.
      - Exemplos obrigatórios: '<b>Forçado</b> - ', '<b>Revelação</b> - ', '<b>Presa</b> - ', '<b>Geração</b> - '.
      - Use aspas retas normais (" e ').
    - FORMATAÇÃO DE TEXTO E TRAITS:
      - Trait / Característica referenciada no texto (palavras em negrito e itálico simultâneos na imagem, ex.: ***Tomo***, ***Magia***, ***Pesquisa***, ***Item***): Use delimitadores de colchetes duplos [[NomeDaTrait]] (ex.: 'carta de [[Magia]]', 'ativo [[Tomo]]', 'habilidade [[Pesquisa]]').
      - Negrito simples: use o delimitador html <b></b> (ex.: '<b>Forçado</b> - ', '<b>Ação:</b>', '<b>Presa</b> - ', '<b>Revelação</b> - ').
      - Itálico simples: use o delimitador html <i></i> (ex.: '<i>(Limite de 1 por rodada.)</i>').
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
  "back_text": "Texto do verso da carta (se for o verso de uma carta dupla face ou local). Aplique as mesmas regras de <b></b>, <i></i>, [[traits]] e [símbolos]. Caso contrário, null.",
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
  "text": "Nomeie uma carta de [[Magia]]. Procure 1 cópia da carta nomeada em seu baralho e compre-a.\\nEmbaralhe o seu baralho.",
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
    "text": "Usa (9 recursos).\\n[reaction] Quando você iniciar um teste de perícia, gaste até 3 recursos de Gregory Gry: Se este teste de perícia for bem-sucedido por pelo menos esse valor, gaste essa quantidade de recursos.",
    "traits": "Aliado. Criminoso. Sonhador.",
    "back_text": null,
    "back_flavor": null
}

Exemplo 4 (Carta com múltiplos parágrafos e custo adicional - 06024 Cristalizador de Sonhos):
{
    "code": "06024",
    "name": "Cristalizador de Sonhos",
    "subname": null,
    "traits": "Item. Relíquia.",
    "text": "Como um custo adicional para jogar esta carta, você deve procurar 1 cópia de Guardião do Cristalizador em suas cartas vinculadas e embaralhá-la em seu baralho.\\n[reaction] Após você jogar um evento: Anexe-o virado para baixo ao Cristalizador de Sonhos em vez de descartá-lo (até um máximo de 5 eventos anexados). Os eventos anexados podem ser comprometidos em testes de perícia como se estivessem em sua mão.",
    "flavor": null,
    "back_text": null,
    "back_flavor": null
}

Exemplo 5 (Carta com palavras-chave e gatilhos em negrito usando hífen simples '-' - 06017 Observador de Outra Dimensão):
{
    "code": "06017",
    "name": "Observador de Outra Dimensão",
    "subname": null,
    "traits": "Monstro. Extradimensional.",
    "text": "Perigo. Oculto. Caçador.\\n<b>Revelação</b> - Adicione secretamente este inimigo à sua mão. Você pode evadir ou lutar contra este inimigo enquanto ele estiver na sua mão (como se ele estivesse em seu local). Se você tiver sucesso, descarte-o da sua mão. Se você falhar, faça-o surgir engajado com você.\\n<b>Forçado</b> - Quando o seu baralho ficar sem cartas, se este inimigo estiver na sua mão: Ele ataca você <i>(da sua mão)</i>.",
    "flavor": null,
    "back_text": null,
    "back_flavor": null
}
"""

# JSON Schema estrito para Structured Outputs (OpenAI, Ollama, etc.)
CARD_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "code": {
            "type": ["string", "null"],
            "description": "Código da carta (ex.: '06026', '06202' ou '06015a'), ou null se não legível.",
        },
        "name": {
            "type": "string",
            "description": "Nome/Título da carta no topo, sem tags HTML.",
        },
        "subname": {
            "type": ["string", "null"],
            "description": "Subtítulo da carta logo abaixo do nome, se houver, ou null.",
        },
        "traits": {
            "type": ["string", "null"],
            "description": "Características/Traits da carta terminando com ponto final, texto puro, ou null.",
        },
        "text": {
            "type": "string",
            "description": "Texto principal de regras da carta, com tags <b></b>, <i></i>, [[traits]], [ícones] e SEMPRE hífen simples '-' (nunca travessão) após palavras-chave como <b>Forçado</b> - ou <b>Revelação</b> -.",
        },
        "flavor": {
            "type": ["string", "null"],
            "description": "Texto de ambientação/flavor text puro, sem tags <b>/<i>, ou null.",
        },
        "back_text": {
            "type": ["string", "null"],
            "description": "Texto de regras do verso da carta se houver, ou null.",
        },
        "back_flavor": {
            "type": ["string", "null"],
            "description": "Texto de flavor do verso da carta se houver, ou null.",
        },
    },
    "required": [
        "code",
        "name",
        "subname",
        "traits",
        "text",
        "flavor",
        "back_text",
        "back_flavor",
    ],
    "additionalProperties": False,
}

# Schema adaptado para o formato do Google Gemini (responseSchema)
GEMINI_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "code": {
            "type": "STRING",
            "nullable": True,
            "description": "Código da carta (ex.: '06026' ou '06015a') ou null.",
        },
        "name": {
            "type": "STRING",
            "description": "Nome/Título da carta no topo, sem tags HTML.",
        },
        "subname": {
            "type": "STRING",
            "nullable": True,
            "description": "Subtítulo da carta logo abaixo do nome, ou null.",
        },
        "traits": {
            "type": "STRING",
            "nullable": True,
            "description": "Características/Traits da carta, texto puro, ou null.",
        },
        "text": {
            "type": "STRING",
            "description": "Texto principal de regras com tags HTML, traits [[Trait]] e símbolos entre colchetes.",
        },
        "flavor": {
            "type": "STRING",
            "nullable": True,
            "description": "Texto de ambientação/flavor puro, ou null.",
        },
        "back_text": {
            "type": "STRING",
            "nullable": True,
            "description": "Texto de regras do verso da carta, ou null.",
        },
        "back_flavor": {
            "type": "STRING",
            "nullable": True,
            "description": "Texto de flavor do verso da carta, ou null.",
        },
    },
    "required": [
        "code",
        "name",
        "subname",
        "traits",
        "text",
        "flavor",
        "back_text",
        "back_flavor",
    ],
}


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

    success, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
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
    """Envia a imagem para a API do Google Gemini com Structured Outputs e retorna os campos extraídos."""
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
            "responseMimeType": "application/json",
            "responseSchema": GEMINI_RESPONSE_SCHEMA,
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
        # Se falhar pelo schema em modelos legados, tenta sem responseSchema
        if e.code == 400 and ("responseSchema" in err_body or "response_schema" in err_body):
            payload["generationConfig"].pop("responseSchema", None)
            req_retry = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req_retry, timeout=30) as resp_retry:
                data = json.loads(resp_retry.read().decode("utf-8"))
                candidates = data.get("candidates", [])
                parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
                text_content = parts[0].get("text", "{}") if parts else "{}"
                return _normalize_llm_result(_clean_json_response(text_content), pack_prefix)
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
    """Envia a imagem para o Ollama local com Structured Outputs e retorna os campos extraídos."""
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
        "format": CARD_JSON_SCHEMA,
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
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        # Fallback para versões mais antigas do Ollama que aceitam apenas "json"
        if e.code == 400 and "format" in err_body:
            payload["format"] = "json"
            req_retry = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req_retry, timeout=60) as resp_retry:
                data = json.loads(resp_retry.read().decode("utf-8"))
                content = data.get("message", {}).get("content", "{}")
                return _normalize_llm_result(_clean_json_response(content), pack_prefix)
        raise RuntimeError(f"Erro no Ollama (HTTP {e.code}): {err_body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Não foi possível conectar ao Ollama em '{ollama_url}'. Verifique se o Ollama está rodando. ({e})")
    except Exception as e:
        raise RuntimeError(f"Falha na requisição para o Ollama: {e}")


# ---------------------------------------------------------------------------
# Provedor: OpenAI Compatible (OpenAI, OpenRouter, LM Studio, vLLM, etc.)
# ---------------------------------------------------------------------------
def analyze_with_openai(
    frame_or_path,
    openai_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    pack_prefix: str | None = None,
) -> dict:
    """Envia a imagem para um endpoint compatível com OpenAI usando Structured Outputs."""
    openai_url = openai_url or config.get_setting("openai_url", "https://api.openai.com/v1")
    openai_url = openai_url.rstrip("/")
    api_key = api_key if api_key is not None else config.get_setting("openai_api_key", "")
    model = model or config.get_setting("openai_model", "gpt-4o")
    pack_prefix = pack_prefix or config.get_setting("pack_prefix", "06")

    b64_image = _frame_to_base64_jpeg(frame_or_path)
    prompt = CARD_ANALYSIS_PROMPT.replace("{PACK_PREFIX}", pack_prefix)

    url = f"{openai_url}/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt,
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{b64_image}",
                            "detail": "high",
                        },
                    },
                ],
            }
        ],
        "temperature": 0.1,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "card_analysis",
                "strict": True,
                "schema": CARD_JSON_SCHEMA,
            },
        },
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "ArkhamTranslator/1.0",
        "HTTP-Referer": "https://github.com/v1pi/arkham-cards-translation-check",
        "X-Title": "Arkham Translator",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            choices = data.get("choices", [])
            if not choices:
                raise ValueError("Nenhuma resposta retornada pela API OpenAI Compatible.")
            content = choices[0].get("message", {}).get("content", "{}")
            result_json = _clean_json_response(content)
            return _normalize_llm_result(result_json, pack_prefix)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        # Se falhar por suporte estrito a json_schema em proxies ou modelos legados, tenta fallback
        if e.code == 400 and ("response_format" in err_body or "json_schema" in err_body or "schema" in err_body):
            try:
                # Tenta fallback para JSON mode padrão
                payload["response_format"] = {"type": "json_object"}
                req_retry = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                    method="POST",
                )
                with urllib.request.urlopen(req_retry, timeout=60) as resp_retry:
                    data = json.loads(resp_retry.read().decode("utf-8"))
                    choices = data.get("choices", [])
                    content = choices[0].get("message", {}).get("content", "{}") if choices else "{}"
                    return _normalize_llm_result(_clean_json_response(content), pack_prefix)
            except Exception:
                # Tenta sem response_format
                payload.pop("response_format", None)
                req_retry2 = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                    method="POST",
                )
                with urllib.request.urlopen(req_retry2, timeout=60) as resp_retry2:
                    data = json.loads(resp_retry2.read().decode("utf-8"))
                    choices = data.get("choices", [])
                    content = choices[0].get("message", {}).get("content", "{}") if choices else "{}"
                    return _normalize_llm_result(_clean_json_response(content), pack_prefix)
        raise RuntimeError(f"Erro na API OpenAI Compatible (HTTP {e.code}): {err_body}")
    except Exception as e:
        raise RuntimeError(f"Falha na requisição para OpenAI Compatible: {e}")


def _normalize_llm_result(raw_dict: dict, pack_prefix: str) -> dict:
    """Padroniza e sanitiza o dicionário retornado pela LLM."""
    code = raw_dict.get("code")
    if code:
        code = card_data.normalize_code(code, pack_prefix)

    fields = {}
    field_keys = ["name", "subname", "traits", "text", "flavor", "back_text", "back_flavor"]
    for k in field_keys:
        val = raw_dict.get(k)
        if val is not None:
            text_val = str(val).strip()
            # Substitui travessões (—), meia-risca (–) e sinal de menos (−) por hífen simples (-)
            text_val = text_val.replace("—", "-").replace("–", "-").replace("−", "-")
            # Substitui aspas curvas por aspas normais
            text_val = text_val.replace("“", "\"").replace("”", "\"").replace("‘", "'").replace("’", "'")
            fields[k] = text_val
        else:
            fields[k] = ""

    return {
        "code": code,
        "fields": fields,
    }


# ---------------------------------------------------------------------------
# Testes de Conexão e Busca Dinâmica de Modelos
# ---------------------------------------------------------------------------
def fetch_gemini_models(api_key: str) -> tuple[bool, list[str], str]:
    """
    Consulta a API do Google Gemini e retorna a lista de modelos de visão/geração disponíveis.
    Retorna (sucesso, lista_de_modelos, mensagem).
    """
    if not api_key:
        return False, [], "Chave de API do Gemini não informada."

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    req = urllib.request.Request(url, headers={"User-Agent": "ArkhamTranslator/1.0"})

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_models = data.get("models", [])

            models = []
            for m in raw_models:
                name = m.get("name", "").replace("models/", "")
                methods = m.get("supportedGenerationMethods", [])
                if "generateContent" in methods and "gemini" in name.lower():
                    # Exclui modelos apenas de áudio/tts ou embedding
                    if not name.endswith("-tts") and "embedding" not in name:
                        models.append(name)

            models.sort(key=str.lower)
            if not models:
                models = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.6-flash", "gemini-3.7-flash"]

            return True, models, f"{len(models)} modelos carregados da API do Gemini."
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="ignore")
        return False, [], f"Erro na API Gemini (HTTP {e.code}): {err}"
    except Exception as e:
        return False, [], f"Erro ao buscar modelos do Gemini: {e}"


def fetch_openai_models(openai_url: str, api_key: str = "") -> tuple[bool, list[str], str]:
    """
    Consulta o endpoint /models da API compatível com OpenAI e retorna os modelos disponíveis.
    """
    if not openai_url:
        return False, [], "URL do endpoint OpenAI não informada."

    openai_url = openai_url.rstrip("/")
    url = f"{openai_url}/models"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "ArkhamTranslator/1.0",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_data = data.get("data", [])
            models = []
            for item in raw_data:
                if isinstance(item, dict):
                    m_id = item.get("id")
                    if m_id:
                        models.append(m_id)
                elif isinstance(item, str):
                    models.append(item)

            models.sort(key=str.lower)
            if not models:
                models = ["gpt-4-turbo", "gpt-4o", "gpt-4o-mini"]
            return True, models, f"{len(models)} modelos carregados da API OpenAI Compatible."
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="ignore")
        return False, [], f"Erro na API (HTTP {e.code}): {err}"
    except Exception as e:
        return False, [], f"Erro ao conectar a {openai_url}: {e}"


def fetch_ollama_models(ollama_url: str) -> tuple[bool, list[str], str]:
    """
    Consulta o servidor Ollama e retorna os modelos instalados/disponíveis.
    Retorna (sucesso, lista_de_modelos, mensagem).
    """
    ollama_url = ollama_url.rstrip("/")
    url = f"{ollama_url}/api/tags"
    req = urllib.request.Request(url, headers={"Content-Type": "application/json", "User-Agent": "ArkhamTranslator/1.0"})

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_models = data.get("models", [])
            models = [m.get("name") for m in raw_models if m.get("name")]
            models.sort(key=str.lower)
            if not models:
                return False, [], "Nenhum modelo encontrado no Ollama local."
            return True, models, f"{len(models)} modelo(s) encontrado(s) no Ollama."
    except Exception as e:
        return False, [], f"Não foi possível conectar ao Ollama em {ollama_url}: {e}"


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


def test_openai_connection(openai_url: str, api_key: str, model: str) -> tuple[bool, str]:
    """Testa a conexão com o endpoint OpenAI compatível."""
    if not openai_url:
        return False, "Host URL não informada."
    openai_url = openai_url.rstrip("/")
    url = f"{openai_url}/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Hello, reply with 'OK'."}],
        "max_tokens": 10,
    }
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "ArkhamTranslator/1.0",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                return True, f"Conexão com {openai_url} (modelo '{model}') realizada com sucesso!"
            return False, f"Resposta inesperada (HTTP {resp.status})"
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="ignore")
        return False, f"Erro na API OpenAI (HTTP {e.code}): {err}"
    except Exception as e:
        return False, f"Erro de conexão: {e}"


def test_ollama_connection(ollama_url: str, model: str) -> tuple[bool, str]:
    """Testa se o host do Ollama está acessível e se o modelo existe."""
    ollama_url = ollama_url.rstrip("/")
    try:
        tags_url = f"{ollama_url}/api/tags"
        req = urllib.request.Request(tags_url, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = [m.get("name") for m in data.get("models", [])]
            model_matched = any(model in m for m in models) if models else False
            if model_matched:
                return True, f"Ollama online! Modelo '{model}' disponível."
            elif models:
                return True, f"Ollama online! Modelos encontrados: {', '.join(models[:3])}"
            return True, "Ollama online!"
    except Exception as e:
        return False, f"Não foi possível conectar ao Ollama em {ollama_url}: {e}"
