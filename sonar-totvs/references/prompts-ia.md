# Prompts da IA por regra

Este arquivo é referência para o Claude da sessão quando processar a fila de revisão IA (`ai-queue_*.jsonl`).

Para CADA bloco na fila:
1. Leia o `content` do arquivo
2. Para cada regra em `rules`, aplique o prompt correspondente abaixo
3. Para cada ocorrência analisada, gere uma linha JSON em `ai-results_*.jsonl`:

```json
{"file": "src/x.prw", "rule": "CA2050", "results": [
  {"line": 47, "is_violation": true, "confidence": "high", "reasoning": "...", "suggested_fix": "...", "matched_text": "trecho disparador"}
]}
```

**Campos da resposta:**
- `line`: número da linha (1-indexed)
- `is_violation`: `true` se for violação real, `false` se for falso positivo
- `confidence`: `"high"`, `"medium"` ou `"low"`
- `reasoning`: explicação curta (1-2 frases) do raciocínio
- `suggested_fix`: sugestão de correção (opcional, quando `is_violation=true`)
- `matched_text`: trecho de código que dispara a regra (opcional)

**Importante:** se a IA encontrar issues NOVAS que o regex não pegou (em modo `all-files`), inclua na lista de `results` com `is_violation=true`. O `consolidate.py` vai detectá-las pela combinação `(file, rule, line)` que não existia no relatório regex.

---

## CA1000 — Chamada inválida de drive ISAM

**Severidade:** BUG  
**Categoria:** LegacyCode  

Analise o código AdvPL/TLPP contra a regra **CA1000 (Driver ISAM descontinuado)**.

**A regra dispara em uso de drivers ISAM (DBFCDX, ADS), que foram descontinuados no Protheus 12.**

**NÃO é violação se:**
- `DbUseArea` está abrindo uma tabela do dicionário Protheus via `TOPCONN` (modo relacional Top-Connect): `DbUseArea(.T., "TOPCONN", ...)` — esse é o uso CORRETO
- `DbUseArea` aponta para alias de tabela do dicionário (SE1, SF1, SA1, etc) sem driver ISAM explícito
- `MsCreate` está sendo usado para criar arquivo CSV/TXT de exportação (uso legítimo)
- O código já está usando `FWTemporaryTable` ou alternativa moderna

**É violação se:**
- `DbUseArea` usa driver ISAM explicitamente: `DBFCDX`, `ADS`, `DBFNTX`
- `DbCreate`/`MsCreate` cria tabela temporária em formato DBF
- Uso de `CriaTrab(.T.)` para criar trabalho ISAM
- `Copy To` exportando dados para DBF

**Importante:** o uso de `DbUseArea(.T., "TOPCONN", ...)` é o padrão CORRETO e moderno. Não confunda com ISAM.

---

## CA1002 — Chamada de API não permitida em transação

**Severidade:** BUG  
**Categoria:** Performance  

Analise o código AdvPL/TLPP contra a regra **CA1002 (API de interface em transação)**.

**A regra dispara quando uma API de interface é chamada DENTRO de um bloco `Begin Transaction ... End Transaction`.**

**APIs de interface que disparam a regra:**
`MsgAlert`, `MsgYesNo`, `MsgNoYes`, `Alert`, `Aviso`, `Help`, `Pergunte`, `ParamBox`, `MsgRun`, `MsgInfo`, `MsgStop`

**NÃO é violação se:**
- A chamada está FORA de qualquer bloco `Begin Transaction`
- A chamada está dentro de uma função separada que NÃO é chamada de dentro de uma transação
- É uma `MsgRun` que é apenas exibida durante processamento longo (sem interação)

**É violação se:**
- A chamada está sintaticamente dentro de `Begin Transaction ... End Transaction`
- A chamada está dentro de uma função/método chamado de dentro de uma transação

**Importante:** rastreie o escopo de transaction no arquivo. Se a chamada está fora dos blocos `Begin Transaction`, não é violação. Marque a confiança como `medium` quando a chamada estiver em função separada chamada de dentro da transação (não tem como ter certeza sem ver o caller).

---

## CA1003 — Uso não permitido de chamada de API em LOOP

**Severidade:** BUG  
**Categoria:** Performance  

Analise o código AdvPL/TLPP contra a regra **CA1003 (GetMv/ExistBlock em loop)**.

**A regra dispara quando `GetMv()` ou `ExistBlock()` é chamada DENTRO de um loop (For/Next, While/EndDo, dbScan, dbEval).**

**NÃO é violação se:**
- A chamada está FORA de qualquer loop
- O parâmetro de `GetMv` muda a cada iteração (depende da variável do loop, ex: `GetMv("MV_PARAM" + cValToChar(nI))`) — nesse caso é uso legítimo
- A chamada está dentro de loop mas com cache (ex: já existe uma variável que armazena o valor antes do loop)

**É violação se:**
- A chamada está dentro de loop com parâmetro CONSTANTE/fixo (ex: `GetMv("MV_PADRAO")` chamado dentro de `For/Next` — deveria estar fora)
- Múltiplas chamadas com mesmo parâmetro dentro do mesmo loop

**Importante:** se o parâmetro depende da iteração, NÃO é violação — é uso legítimo. Veja se o parâmetro muda a cada volta do loop.

---

## CA2016 — Funções de erro/Log sem I18N

**Severidade:** BUG  
**Categoria:** Maintainability  

Analise o código AdvPL/TLPP contra a regra **CA2016 (Log/erro sem I18N)**.

**A regra dispara quando funções de log ou erro recebem string LITERAL ao invés de string internacionalizada (`I18N(...)` ou `STR0XXX`).**

**NÃO é violação se:**
- A string já está envolta em `I18N("texto")`
- A string é uma constante de `#define STR0XXX I18N("...")`
- A string passada é uma variável (não literal direto)
- É uma string puramente técnica não destinada a usuário final (ex: `FWLogMsg("DEBUG", "step=1")` para log técnico interno; depende do contexto)
- É um separator/formatador simples (ex: `ConOut("---")`)

**É violação se:**
- Função de log/erro recebe string literal em português ou inglês destinada a exibição (mensagem de erro, alerta, info ao usuário)
- A string é claramente uma mensagem para o usuário e não foi internacionalizada

**Importante:** funções afetadas: `ApMsgErro`, `FWLogMsg`, `Help`, `MsgAlert`, `MsgInfo`, `MsgStop`. Strings em variáveis ou já com I18N não são violação.

---

## CA2020 — Função/Classe Descontinuada

**Severidade:** BUG  
**Categoria:** Maintainability  

Analise o código AdvPL/TLPP contra a regra **CA2020 (Função descontinuada)**.

**A regra dispara em chamadas a funções/classes marcadas como descontinuadas no TDN da TOTVS.**

Funções descontinuadas conhecidas: `MsCbInfo`, `MsCbPrintLabel`, `MsGetDB`, `MsWorkArea`, e outras.

**NÃO é violação se:**
- A chamada está dentro de comentário (// ou /* */)
- É uma declaração de função própria do usuário com nome similar mas user function (`User Function MsCbInfo`) — caso muito raro
- O nome aparece como string em log/erro, não como chamada de função

**É violação se:**
- Há chamada real a uma das funções descontinuadas
- A chamada é executável (não comentada)

**Importante:** se confirmado violação, sugira no `suggested_fix` qual é a função substituta moderna (consulte TDN). Marque `confidence: medium` se não souber a substituta exata.

---

## CA2052 — Senha Exposta

**Severidade:** CODE_SMELL  
**Categoria:** Security  

Analise o código AdvPL/TLPP contra a regra **CA2052 (Senha exposta)**.

**A regra dispara quando há credencial sensível (senha, token, API key) com valor LITERAL no código.**

**NÃO é violação se:**
- A string é um placeholder vazio (`""`, `"YOUR_PASSWORD_HERE"`, `"xxx"`, `"changeme"`)
- A string é um valor de exemplo/teste claramente identificável (`"123"`, `"test"`, `"demo"`, `"password"`)
- A variável recebe valor de `GetMv()`, `GetNewPar()`, `ReadVar()`, ou similar
- A variável recebe valor vindo de tabela/registro (ex: `SX6->X6_CONTEUD`)
- É uma string vazia inicializadora (`cSenha := ""`)
- O nome da variável é confuso e não é realmente senha (ex: `cTokenSeparator := ";"` — é separador, não token de auth)

**É violação se:**
- A variável tem nome claro de credencial (senha/password/token/api_key) e recebe valor literal com aparência de credencial real (mistura de letras, números, símbolos, comprimento > 6)
- Aparenta ser uma credencial de produção hardcoded

**Importante:** seja conservador. Marque `is_violation=true` apenas quando claramente houver credencial real exposta. Em caso de dúvida, marque `false` com `reasoning` explicando.

---

## CA2050 — Sql Inject

**Severidade:** VULNERABILIDADE  
**Categoria:** Security  

Analise o código AdvPL/TLPP contra a regra **CA2050 (SQL Injection)**.

**A regra dispara quando há concatenação de variáveis em queries SQL SEM sanitização prévia.**

**NÃO é violação se:**
- A query usa `FWPreparedStatement` com placeholders (`?`) e bind de parâmetros
- A query usa `TcGenQry2` com placeholders
- A variável concatenada passou por função de sanitização antes (ex: `SanitizeSql()`, `EscapeSql()`, `FwSqlEscape()`, ou função custom de limpeza)
- A query é construída com `BeginSql Alias` usando `%Exp:%` (que escapa automaticamente)
- A string SQL é 100% literal (sem variáveis concatenadas)
- A variável concatenada vem de uma constante `#define` ou `Local` com valor literal hardcoded

**É violação se:**
- Concatenação direta com `+` de variáveis vindas de parâmetros de função, registros lidos do banco, valores de tela/usuário, sem sanitização
- Uso de `TcGenQry/TcSqlExec/TcQuery` com `+` direto entre strings e variáveis

**Importante:** rastreie a origem da variável dentro do arquivo. Se ela é atribuída e DEPOIS passada por uma função de limpeza antes do uso na query, é seguro. Se passa direto, é violação.

---

