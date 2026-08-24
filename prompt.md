# Arkham Horror LCG Translation Checker

Quero que você desenvolva para mim um programa desktop simples em Python para conferir traduções de cartas de Arkham Horror: The Card Game.

## Objetivo

As traduções em português que quero verificar estão em:

`translations/pt/pack/tde`

Esses arquivos JSON já contêm traduções para português que foram geradas por inteligência artificial.

Eu também tenho as cartas físicas oficiais em português.

Quero usar a câmera do notebook para apontar para uma carta física e fazer OCR do texto oficial em português. O programa deve identificar qual é a carta, encontrar a carta correspondente nos arquivos JSON e comparar:

1. A tradução em português que já está no JSON, gerada por IA.
2. O texto oficial em português da carta física, obtido através do OCR.

O objetivo principal é encontrar diferenças entre as duas traduções e me permitir aceitar ou editar essas diferenças.

---

# IMPORTANTE: mantenha o projeto extremamente simples

Não quero uma arquitetura exageradamente complexa.

Não quero:

- banco de dados;
- servidor;
- API web;
- backend separado;
- Docker;
- autenticação;
- sistema de usuários;
- sistema próprio de backup;
- sistema próprio de versionamento;
- logs complexos;
- arquitetura enterprise;
- microserviços;
- overengineering.

Eu mesmo vou controlar todas as alterações usando Git.

Quero um pequeno aplicativo Python local, fácil de entender, executar e modificar.

Use a solução mais simples que seja tecnicamente adequada.

---

# Gerenciamento do projeto

Use **uv** como gerenciador de projeto e dependências Python.

Crie um projeto Python moderno utilizando `pyproject.toml`.

Use o Python em uma versão estável e atual compatível com as bibliotecas escolhidas.

Pode escolher livremente as bibliotecas necessárias, mas minimize o número de dependências.

Se uma funcionalidade puder ser resolvida com a biblioteca padrão do Python, prefira a biblioteca padrão.

Por exemplo:

- `json` para JSON;
- `difflib` para comparação de textos;
- `tkinter`/`ttk` para GUI, se for suficiente. Pode usar outra, se achar uma melhor na pesquisa.

Não instale uma biblioteca apenas por conveniência quando a biblioteca padrão já resolver.

---

# Interface gráfica

Quero uma interface gráfica desktop simples.

Minha preferência é começar com **Tkinter + ttk**, pois quero manter o projeto pequeno e fácil de manter.

Não use Electron, React ou frameworks maiores sem uma necessidade concreta. PySide6 pode ser considerada, caso seja mais simples que o tkinter.

A interface deve ter aproximadamente:

```text
┌─────────────────────────────────────────────────────────────┐
│ Arkham Horror LCG Translation Checker                     │
├───────────────────────────┬─────────────────────────────────┤
│                           │ Carta encontrada                │
│                           │                                 │
│       CÂMERA              │ ID: XXXXX                       │
│                           │ Nome: XXXXX                     │
│    [ imagem ao vivo ]     │                                 │
│                           │ Tradução atual                  │
│                           │ ┌─────────────────────────────┐ │
│                           │ │ texto do JSON                │ │
│                           │ └─────────────────────────────┘ │
│                           │                                 │
│   [ CAPTURAR CARTA ]      │ Texto oficial (OCR)             │
│   [ Escolher Carta]       │ ┌─────────────────────────────┐ │
│                           │ │ texto reconhecido            │ │
│                           │ └─────────────────────────────┘ │
├───────────────────────────┴─────────────────────────────────┤
│ Diferenças                                                  │
│                                                             │
│ texto com diferenças destacadas                             │
│                                                             │
│ [ ACEITAR ] [ EDITAR ] [ MANTER ] [ PRÓXIMA CARTA ]         │
└─────────────────────────────────────────────────────────────┘
````

A interface não precisa ser bonita ou sofisticada. Ela precisa ser funcional e simples.

---

# Webcam

Use OpenCV para acessar a câmera do notebook.

A aplicação deve:

1. Abrir a webcam.
2. Mostrar o vídeo ao vivo na interface.
3. Permitir capturar uma imagem.
4. Fazer o processamento da imagem capturada.

Não é necessário fazer reconhecimento contínuo em tempo real.

Prefiro que o OCR aconteça quando eu clicar em:

`CAPTURAR CARTA`

Isso reduz complexidade e consumo de recursos.

---

# Identificação da carta

A carta possui um identificador/número que deve ser usado para encontrar a carta correspondente no JSON.

O programa deve tentar reconhecer esse identificador através do OCR.

Depois:

```text
ID reconhecido
      ↓
procurar carta correspondente
      ↓
abrir a entrada correspondente no JSON
```

Se houver mais de uma possibilidade ou o OCR estiver inseguro, mostre a possibilidade para eu confirmar manualmente.

Não invente uma correspondência.

---

# OCR

Escolha uma biblioteca moderna de OCR adequada para português.

Minha primeira preferência é **PaddleOCR**, mas você pode escolher outra biblioteca se houver uma justificativa técnica clara.

O OCR precisa reconhecer português, incluindo:

* á
* é
* í
* ó
* ú
* ã
* õ
* â
* ê
* ô
* ç
* etc.

Antes de passar a imagem para o OCR, use OpenCV apenas para o pré-processamento que realmente melhorar a qualidade:

* correção de perspectiva, se necessário;
* escala;
* contraste;
* redução de ruído;
* outros tratamentos simples se forem necessários.

Não implemente um sistema sofisticado de visão computacional sem necessidade.

Fique atento que as cartas possuem o texto do corpo, traits, flavor, titulo e outras informações que todas devem ser comparadas.
---

# MUITO IMPORTANTE: símbolos Arkham

Os símbolos como:

`[reaction]`
`[action]`
`[fast]`
`[elder_sign]`
`[skull]`
`[cultist]`
etc.

JÁ ESTÃO CORRETAMENTE POSICIONADOS na tradução portuguesa existente no JSON.

A tradução feita pela IA já possui esses símbolos no lugar correto.

Portanto:

**NÃO tente reconstruir a posição dos símbolos usando OCR.**

**NÃO tente reconhecer graficamente os símbolos da carta para depois inseri-los no texto.**

**NÃO altere a posição dos símbolos existentes no JSON.**

O programa deve considerar esses símbolos como elementos protegidos.

Por exemplo, se a tradução atual for:

`Depois que você [reaction] derrotar um inimigo.`

e a tradução oficial for:

`Depois que você [reaction] vencer um inimigo.`

o programa deve identificar somente:

`derrotar` → `vencer`

e manter:

`[reaction]`

exatamente onde está.

---

# Comparação das traduções

A comparação deve ser feita de maneira inteligente, não simplesmente comparando strings inteiras.

É importante lidar razoavelmente com:

* espaços diferentes;
* quebras de linha;
* pontuação;
* diferenças de capitalização quando apropriado;
* símbolos `[reaction]`, `[action]`, etc.;
* pequenas diferenças causadas pelo OCR.

Use `difflib` da biblioteca padrão quando for suficiente.

Não instale uma biblioteca de comparação de texto complexa sem necessidade.

---

# Proteção dos símbolos

Antes da comparação, extraia temporariamente os tokens no formato:

`[qualquer_coisa]`

da tradução existente.

Por exemplo:

```text
Depois que você [reaction] derrotar um inimigo.
```

pode internamente virar:

```text
Depois que você {{SYMBOL_0}} derrotar um inimigo.
```

com:

```python
{
    "{{SYMBOL_0}}": "[reaction]"
}
```

A comparação deve ocorrer sem permitir que esses tokens sejam alterados.

Depois da comparação, os símbolos originais devem ser recolocados exatamente como estavam.

O programa deve preservar:

* `[reaction]`
* `[action]`
* `[fast]`
* `[elder_sign]`
* qualquer outro token existente entre colchetes.

Não faça uma lista limitada de símbolos se isso puder ser evitado. Idealmente, trate qualquer token no padrão `[... ]` como protegido.

---

# OCR e símbolos

O OCR pode interpretar um símbolo visualmente como:

* texto;
* um caractere estranho;
* uma palavra;
* nada.

Isso não deve ser um problema.

A prioridade do OCR é reconhecer o **texto português oficial**.

Não dependa do OCR para determinar qual símbolo Arkham está presente.

Use a estrutura da tradução existente como referência para os símbolos.

---

# Edição

Depois da comparação, quero três possibilidades:

## 1. Aceitar

O programa aplica a tradução oficial reconhecida pelo OCR ao campo correspondente do JSON, preservando os símbolos existentes.

## 2. Manter

Não altera nada e passa para a próxima carta.

## 3. Editar

Abre um campo editável para que eu possa corrigir manualmente o texto antes de salvar.

Também deve haver:

## 4. Próxima carta

Pula a carta atual sem alterar o arquivo.

---

# Escrita do JSON

É extremamente importante preservar a estrutura do JSON existente.

Não altere campos que não precisam ser alterados.

Altere somente o campo da tradução que estamos verificando.

Os caracteres Unicode devem ser gravados no formato esperado pelo repositório.

Por exemplo:

```json
"Voc\u00ea ganhou uma a\u00e7\u00e3o."
```

e não necessariamente:

```json
"Você ganhou uma ação."
```

Use:

```python
json.dump(..., ensure_ascii=True)
```

se isso for compatível com a estrutura existente.

Também preserve os tokens:

```text
[reaction]
[action]
[fast]
[elder_sign]
```

exatamente no formato esperado pelo projeto.

Antes de implementar a escrita, examine a estrutura real dos arquivos do repositório para identificar exatamente:

* qual arquivo contém as cartas de TDE;
* qual campo contém o texto traduzido;
* qual campo contém o identificador;
* como os símbolos são armazenados;
* como as quebras de linha são armazenadas.

Não assuma a estrutura do JSON. Verifique o repositório.

---

# Fluxo completo esperado

O fluxo do usuário deve ser:

```text
Abrir programa
      ↓
Webcam aparece
      ↓
Colocar carta portuguesa diante da câmera
      ↓
Clicar "CAPTURAR CARTA"
      ↓
OCR identifica o ID
      ↓
Encontrar carta no translations/pt/pack/tde
      ↓
OCR identifica o texto oficial português
      ↓
Comparar com tradução atual
      ↓
Mostrar diferenças
      ↓
Usuário escolhe:

[ACEITAR]
      ↓
Atualiza JSON

ou

[EDITAR]
      ↓
Usuário corrige
      ↓
Atualiza JSON

ou

[MANTER]
      ↓
Não altera

ou

[PRÓXIMA CARTA]
      ↓
Continua
```

---

# Git

Não implemente nenhum sistema próprio de backup.

Não crie arquivos `.backup`.

Não faça cópias automáticas.

Não implemente undo persistente.

Eu vou utilizar Git para controlar todas as mudanças.

O programa simplesmente deve editar os arquivos existentes.

---

# Configuração

Evite hardcode desnecessário.

Crie uma configuração simples, por exemplo:

```text
CARD_DATA_PATH=...
```

ou um pequeno `config.py`/`config.json`.

O usuário deve conseguir indicar onde está o repositório:

```text
translations/pt/pack/tde
```

sem precisar alterar código.

Se for mais simples, pode detectar automaticamente a pasta relativa ao projeto.

---

# Qualidade do código

Quero código:

* simples;
* legível;
* pequeno;
* comentado apenas quando necessário;
* sem abstrações desnecessárias;
* sem padrões de projeto desnecessários;
* fácil de modificar por alguém que conhece Python.

Prefira código explícito a código excessivamente abstrato.

Não crie classes para tudo.

Não crie interfaces abstratas para componentes que só terão uma implementação.

---

# Dependências

Use o menor número possível de dependências.

A princípio considere:

* Python standard library
* OpenCV
* PaddleOCR
* Pillow, somente se necessário para integrar OpenCV com Tkinter

Use `uv` para instalar e executar tudo.

Crie:

```text
pyproject.toml
```

e forneça comandos claros como:

```bash
uv sync
uv run python main.py
```

---

# Desenvolvimento incremental

Não tente construir tudo de uma vez.

Primeiro implemente e teste:

1. leitura dos JSON;
2. localização de uma carta pelo ID (padrão nas cartas é 06XXX, onde XXX é um 0-padding left com o valor no canto inferiror direito da carta);
3. extração do texto;
4. proteção dos `[tokens]`;
5. comparação;
6. edição do JSON.

Depois:

7. webcam;
8. OCR do ID;
9. OCR do texto;
10. GUI completa.

Se alguma parte for problemática, priorize fazer uma versão simples funcionar antes de sofisticá-la.

---

# Testes

Crie alguns testes simples para a parte mais importante do projeto: comparação e preservação dos símbolos.

Por exemplo:

Entrada atual:

```text
Depois que você [reaction] derrotar um inimigo.
```

Entrada oficial:

```text
Depois que você [reaction] vencer um inimigo.
```

Resultado esperado:

```text
Depois que você [reaction] vencer um inimigo.
```

O `[reaction]` deve permanecer intacto.

Teste também:

```text
[action]
```

no início;

```text
texto [reaction] no meio
```

e:

```text
texto [elder_sign] no final
```

Além disso, teste caracteres portugueses e Unicode.

---

# Entrega

Ao terminar, quero:

1. Estrutura completa do projeto.
2. `pyproject.toml`.
3. Código fonte.
4. Testes básicos.
5. `README.md`.
6. Instruções para instalar usando `uv`.
7. Instruções para executar.
8. Explicação curta de como o OCR funciona.
9. Explicação de quais arquivos JSON são modificados.
10. Explicação de como adicionar/mudar a pasta de traduções.

Antes de escrever o código, analise esse projeto.

e especificamente:

`translations/pt/pack/tde`

para entender a estrutura real dos dados.

**Não invente a estrutura do JSON.**

Se alguma decisão técnica não for necessária para cumprir o objetivo, escolha a opção mais simples.

O objetivo principal é:

> Uma ferramenta local, pequena e confiável para colocar uma carta portuguesa na frente da webcam, ler sua tradução oficial, comparar com a tradução portuguesa existente no ArkhamDB JSON Data e, após minha confirmação, atualizar somente a tradução correspondente no JSON, preservando os símbolos Arkham já existentes.
> :::```
