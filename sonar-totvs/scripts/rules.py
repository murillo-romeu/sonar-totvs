"""
Catálogo de regras Sonar TOTVS com padrões de detecção (regex) e metadados.

A detecção é por regex sobre código já com comentários/strings mascarados
(exceto onde nota indica que precisa do conteúdo da string, como CA2050).
"""

import re
from dataclasses import dataclass, field
from typing import Optional, Callable


# Severidades / categorias
BUG = "BUG"
CODE_SMELL = "CODE_SMELL"
VULNERABILIDADE = "VULNERABILIDADE"


@dataclass
class Rule:
    code: str
    title: str
    severity: str  # BUG / CODE_SMELL / VULNERABILIDADE
    category: str  # Performance / Security / Maintainability etc
    description: str
    how_to_fix: str
    # Lista de regex pré-compiladas. Match = issue detectada.
    patterns: list = field(default_factory=list)
    # Se True, aplica patterns sobre código com strings preservadas
    needs_strings: bool = False
    # Nome do fix automático, se houver
    auto_fix: Optional[str] = None
    # Se True, a regra precisa de revisão semântica pela IA (Claude da sessão).
    # Regex apenas pré-filtra candidatos; IA confirma ou descarta.
    needs_ai_review: bool = False
    # Prompt específico que o Claude usa para revisar a regra (markdown)
    ai_prompt: Optional[str] = None


# ============================================================================
# CATÁLOGO COMPLETO
# ============================================================================

RULES: list[Rule] = [
    # --------------- BUGS ---------------
    Rule(
        code="CA1000",
        title="Chamada inválida de drive ISAM",
        severity=BUG,
        category="LegacyCode",
        description="Uso de drivers ISAM foi descontinuado a partir do Protheus 12. Migre para FWTemporaryTable (modo relacional) ou exportação CSV via ExpExcel.",
        how_to_fix="Substitua chamadas ISAM por FWTemporaryTable em modo relacional. Para exportação, use ExpExcel/CSV.",
        patterns=[
            re.compile(r"\bMSCREATE\s*\(", re.IGNORECASE),
            re.compile(r"\bMSFILE\s*\(", re.IGNORECASE),
            re.compile(r"\bMSCOPYFILE\b", re.IGNORECASE),
            re.compile(r"\bMSERASE\b", re.IGNORECASE),
            re.compile(r"\bDBCREATE\s*\(", re.IGNORECASE),
            re.compile(r"\bDBUSEAREA\s*\(", re.IGNORECASE),
            re.compile(r"\bCRIATRAB\s*\(\s*\.T\.\s*\)", re.IGNORECASE),
            re.compile(r"\bCOPY\s+TO\b", re.IGNORECASE),
        ],
        needs_ai_review=True,
        ai_prompt="""Analise o código AdvPL/TLPP contra a regra **CA1000 (Driver ISAM descontinuado)**.

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

**Importante:** o uso de `DbUseArea(.T., "TOPCONN", ...)` é o padrão CORRETO e moderno. Não confunda com ISAM.""",
    ),
    Rule(
        code="CA1002",
        title="Chamada de API não permitida em transação",
        severity=BUG,
        category="Performance",
        description="APIs de interface (MsgAlert, MsgYesNo, Alert, Help, Pergunte, ParamBox) não podem ser chamadas dentro de Begin Transaction / End Transaction.",
        how_to_fix="Reestruture a lógica para que a transação não tenha interrupções de interface.",
        patterns=[
            # Detecção mais grosseira: marca uso dessas APIs; análise contextual de transaction
            # exige parser real. Por ora, marca como "verificar se está em transaction".
            re.compile(r"\b(MSGALERT|MSGYESNO|MSGNOYES|ALERT|AVISO|HELP|PERGUNTE|PARAMBOX)\s*\(", re.IGNORECASE),
        ],
        needs_ai_review=True,
        ai_prompt="""Analise o código AdvPL/TLPP contra a regra **CA1002 (API de interface em transação)**.

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

**Importante:** rastreie o escopo de transaction no arquivo. Se a chamada está fora dos blocos `Begin Transaction`, não é violação. Marque a confiança como `medium` quando a chamada estiver em função separada chamada de dentro da transação (não tem como ter certeza sem ver o caller).""",
    ),
    Rule(
        code="CA1003",
        title="Uso não permitido de chamada de API em LOOP",
        severity=BUG,
        category="Performance",
        description="GetMv() e ExistBlock() em loops degradam performance. Mova para fora do laço armazenando em variável local.",
        how_to_fix="Armazene o resultado em variável local antes do loop.",
        patterns=[
            # Aproximação: marca uso de GetMv/ExistBlock; contexto de loop precisa de parser
            re.compile(r"\bGETMV\s*\(", re.IGNORECASE),
            re.compile(r"\bEXISTBLOCK\s*\(", re.IGNORECASE),
        ],
        needs_ai_review=True,
        ai_prompt="""Analise o código AdvPL/TLPP contra a regra **CA1003 (GetMv/ExistBlock em loop)**.

**A regra dispara quando `GetMv()` ou `ExistBlock()` é chamada DENTRO de um loop (For/Next, While/EndDo, dbScan, dbEval).**

**NÃO é violação se:**
- A chamada está FORA de qualquer loop
- O parâmetro de `GetMv` muda a cada iteração (depende da variável do loop, ex: `GetMv("MV_PARAM" + cValToChar(nI))`) — nesse caso é uso legítimo
- A chamada está dentro de loop mas com cache (ex: já existe uma variável que armazena o valor antes do loop)

**É violação se:**
- A chamada está dentro de loop com parâmetro CONSTANTE/fixo (ex: `GetMv("MV_PADRAO")` chamado dentro de `For/Next` — deveria estar fora)
- Múltiplas chamadas com mesmo parâmetro dentro do mesmo loop

**Importante:** se o parâmetro depende da iteração, NÃO é violação — é uso legítimo. Veja se o parâmetro muda a cada volta do loop.""",
    ),
    Rule(
        code="CA2000",
        title="Uso não permitido do Metadados - SM0",
        severity=BUG,
        category="Performance",
        description="Manipulação direta da SM0 (tabela de empresas) não é permitida. Em futuras versões o alias só abrirá em modo Query.",
        how_to_fix="Use APIs padrões de leitura do metadados. Manipulação deve ser feita pelo Configurador ou rotina de upgrade.",
        patterns=[
            re.compile(r"\bSM0\s*->", re.IGNORECASE),
            re.compile(r'dbSelectArea\s*\(\s*["\']SM0["\']\s*\)', re.IGNORECASE),
        ],
    ),
    Rule(
        code="CA2001",
        title="Uso não permitido do Metadados - SIX",
        severity=BUG,
        category="Performance",
        description="Manipulação direta da SIX (índices) não é permitida.",
        how_to_fix="Use APIs padrões de forma indireta.",
        patterns=[
            re.compile(r"\bSIX\s*->", re.IGNORECASE),
            re.compile(r'dbSelectArea\s*\(\s*["\']SIX["\']\s*\)', re.IGNORECASE),
        ],
    ),
    Rule(
        code="CA2002",
        title="Uso não permitido de atribuição do Metadados - SX1",
        severity=BUG,
        category="Performance",
        description="Atribuição direta na SX1 (perguntas) não é permitida. Use Pergunte.",
        how_to_fix="Use a API Pergunte. Manipulação de dados deve ser feita pelo Configurador.",
        patterns=[
            re.compile(r"\bSX1\s*->\s*\w+\s*:?=", re.IGNORECASE),
            re.compile(r"RecLock\s*\(\s*['\"]SX1['\"]", re.IGNORECASE),
        ],
    ),
    Rule(
        code="CA2002-2",
        title="Formato de leitura não permitida do Metadados - SX1",
        severity=BUG,
        category="Performance",
        description="Leitura direta da SX1 não é permitida.",
        how_to_fix="Use a API Pergunte.",
        patterns=[
            re.compile(r"\bSX1\s*->\s*\w+", re.IGNORECASE),
        ],
    ),
    Rule(
        code="CA2003",
        title="Uso não permitido do Metadados - SX2",
        severity=BUG,
        category="Performance",
        description="Manipulação da SX2 (tabelas) não é permitida. Use RetSqlName/X2Nome.",
        how_to_fix="Use RetSqlName/X2Nome. Manipulação só via Configurador.",
        patterns=[
            re.compile(r"\bSX2\s*->\s*\w+\s*:?=", re.IGNORECASE),
            re.compile(r"RecLock\s*\(\s*['\"]SX2['\"]", re.IGNORECASE),
        ],
    ),
    Rule(
        code="CA2003-2",
        title="Leitura não permitida do Metadados - SX2",
        severity=BUG,
        category="Performance",
        description="Leitura direta da SX2 não é permitida.",
        how_to_fix="Use RetSqlName.",
        patterns=[
            re.compile(r"\bSX2\s*->\s*\w+", re.IGNORECASE),
        ],
    ),
    Rule(
        code="CA2004",
        title="Uso não permitido do Metadados - SX3",
        severity=BUG,
        category="Performance",
        description="Manipulação direta da SX3 (campos) não é permitida.",
        how_to_fix="Use FWSX3Util. Manipulação só via Configurador.",
        patterns=[
            re.compile(r"\bSX3\s*->\s*\w+\s*:?=", re.IGNORECASE),
            re.compile(r"RecLock\s*\(\s*['\"]SX3['\"]", re.IGNORECASE),
        ],
    ),
    Rule(
        code="CA2004-2",
        title="Leitura não permitida do Metadados - SX3",
        severity=BUG,
        category="Performance",
        description="Leitura direta da SX3 não é permitida.",
        how_to_fix="Use FWSX3Util.",
        patterns=[
            re.compile(r"\bSX3\s*->\s*\w+", re.IGNORECASE),
        ],
    ),
    Rule(
        code="CA2005",
        title="Uso indevido do Metadados - SX7",
        severity=BUG,
        category="Performance",
        description="Manipulação da SX7 (gatilhos) não é permitida.",
        how_to_fix="Use APIs padrões indiretas. Manipulação só via Configurador.",
        patterns=[
            re.compile(r"\bSX7\s*->\s*\w+\s*:?=", re.IGNORECASE),
            re.compile(r"RecLock\s*\(\s*['\"]SX7['\"]", re.IGNORECASE),
        ],
    ),
    Rule(
        code="CA2006",
        title="Uso indevido do Metadados - SX9",
        severity=BUG,
        category="Performance",
        description="Manipulação da SX9 (relacionamento) não é permitida.",
        how_to_fix="Use APIs padrões indiretas.",
        patterns=[
            re.compile(r"\bSX9\s*->\s*\w+\s*:?=", re.IGNORECASE),
            re.compile(r"RecLock\s*\(\s*['\"]SX9['\"]", re.IGNORECASE),
        ],
    ),
    Rule(
        code="CA2007",
        title="Uso não permitido do Metadados - SXA",
        severity=BUG,
        category="Performance",
        description="Manipulação da SXA (pastas) não é permitida.",
        how_to_fix="Use APIs padrões. Manipulação só via Configurador.",
        patterns=[
            re.compile(r"\bSXA\s*->\s*\w+", re.IGNORECASE),
        ],
    ),
    Rule(
        code="CA2008",
        title="Uso não permitido do Metadados - SXB",
        severity=BUG,
        category="Performance",
        description="Manipulação da SXB (lookups/consultas) não é permitida.",
        how_to_fix="Use APIs padrões.",
        patterns=[
            re.compile(r"\bSXB\s*->\s*\w+", re.IGNORECASE),
        ],
    ),
    Rule(
        code="CA2009",
        title="Uso descontinuado SX5",
        severity=BUG,
        category="Performance",
        description="A tabela SX5 está descontinuada.",
        how_to_fix="Use FwTabFil ou APIs equivalentes.",
        patterns=[
            re.compile(r"\bSX5\s*->\s*\w+", re.IGNORECASE),
            re.compile(r'dbSelectArea\s*\(\s*["\']SX5["\']\s*\)', re.IGNORECASE),
        ],
    ),
    Rule(
        code="CA2010",
        title="Uso descontinuado SX6",
        severity=BUG,
        category="Performance",
        description="Leitura/atualização direta da SX6 está descontinuada.",
        how_to_fix="Use GetMv()/PutMv() ou FwxFilial().",
        patterns=[
            re.compile(r"\bSX6\s*->\s*\w+", re.IGNORECASE),
        ],
    ),
    Rule(
        code="CA2011",
        title="Uso inválido do Metadados - SXG",
        severity=BUG,
        category="Performance",
        description="Manipulação da SXG (grupos de campos) não é permitida.",
        how_to_fix="Use APIs padrões.",
        patterns=[
            re.compile(r"\bSXG\s*->\s*\w+", re.IGNORECASE),
        ],
    ),
    Rule(
        code="CA2012",
        title="Uso descontinuado do Metadados - SXD",
        severity=BUG,
        category="Performance",
        description="Manipulação da SXD está descontinuada.",
        how_to_fix="Use APIs padrões.",
        patterns=[
            re.compile(r"\bSXD\s*->\s*\w+", re.IGNORECASE),
        ],
    ),
    Rule(
        code="CA2013",
        title="Uso não permitido das tabelas de Framework",
        severity=BUG,
        category="Performance",
        description="Manipulação direta de tabelas internas do framework.",
        how_to_fix="Use APIs padrões.",
        patterns=[
            re.compile(r"\b(FWA|FWB|FWG|FWH|FWM)\s*->\s*\w+", re.IGNORECASE),
        ],
    ),
    Rule(
        code="CA2016",
        title="Funções de erro/Log sem I18N",
        severity=BUG,
        category="Maintainability",
        description="Funções de log/erro devem usar a API I18N para internacionalização.",
        how_to_fix="Envolva strings literais em I18N() ou STR0XXX (#define com I18N).",
        # heurística básica: ApMsgErro / FwLogMsg / Help com string literal direta
        patterns=[
            re.compile(r"\b(APMSGERRO|FWLOGMSG|HELP)\s*\(\s*[\"']", re.IGNORECASE),
        ],
        needs_ai_review=True,
        ai_prompt="""Analise o código AdvPL/TLPP contra a regra **CA2016 (Log/erro sem I18N)**.

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

**Importante:** funções afetadas: `ApMsgErro`, `FWLogMsg`, `Help`, `MsgAlert`, `MsgInfo`, `MsgStop`. Strings em variáveis ou já com I18N não são violação.""",
    ),
    Rule(
        code="CA2017",
        title="Uso não permitido de API SPF",
        severity=BUG,
        category="Security",
        description="APIs SPF (sistema de privacidade) não são permitidas em customizações.",
        how_to_fix="Remova chamadas SPF.",
        patterns=[
            re.compile(r"\bSPF[A-Z][A-Z0-9_]*\s*\(", re.IGNORECASE),
        ],
    ),
    Rule(
        code="CA2018",
        title="Uso não permitido de API",
        severity=BUG,
        category="Security",
        description="Uso de APIs restritas/internas.",
        how_to_fix="Substitua por APIs públicas equivalentes.",
        patterns=[
            re.compile(r"\b__(\w+)\s*\(", re.IGNORECASE),  # APIs internas que começam com __
        ],
    ),
    Rule(
        code="CA2019",
        title="Funções de leitura/gravação binária não permitidas",
        severity=BUG,
        category="Security",
        description="Funções binárias diretas (FRead, FWrite, FOpen, FCreate, FClose com binário) não são permitidas.",
        how_to_fix="Use APIs do framework para manipulação de arquivos.",
        patterns=[
            re.compile(r"\b(FREAD|FWRITE|FOPEN|FCREATE)\s*\(", re.IGNORECASE),
        ],
    ),
    Rule(
        code="CA2020",
        title="Função/Classe Descontinuada",
        severity=BUG,
        category="Maintainability",
        description="Uso de função ou classe marcada como descontinuada.",
        how_to_fix="Substitua pela função/classe atual conforme documentação TDN.",
        patterns=[
            # Lista de funções conhecidamente descontinuadas
            re.compile(r"\b(MSCBINFO|MSCBPRINTLABEL|MSGETDB|MSWORKAREA)\s*\(", re.IGNORECASE),
        ],
        auto_fix="add_todo_comment",
        needs_ai_review=True,
        ai_prompt="""Analise o código AdvPL/TLPP contra a regra **CA2020 (Função descontinuada)**.

**A regra dispara em chamadas a funções/classes marcadas como descontinuadas no TDN da TOTVS.**

Funções descontinuadas conhecidas: `MsCbInfo`, `MsCbPrintLabel`, `MsGetDB`, `MsWorkArea`, e outras.

**NÃO é violação se:**
- A chamada está dentro de comentário (// ou /* */)
- É uma declaração de função própria do usuário com nome similar mas user function (`User Function MsCbInfo`) — caso muito raro
- O nome aparece como string em log/erro, não como chamada de função

**É violação se:**
- Há chamada real a uma das funções descontinuadas
- A chamada é executável (não comentada)

**Importante:** se confirmado violação, sugira no `suggested_fix` qual é a função substituta moderna (consulte TDN). Marque `confidence: medium` se não souber a substituta exata.""",
    ),
    Rule(
        code="CA2021",
        title="Tabela/campos descontinuados SE5",
        severity=BUG,
        category="Maintainability",
        description="Tabela SE5 está descontinuada.",
        how_to_fix="Use as APIs/tabelas atuais do módulo financeiro.",
        patterns=[
            re.compile(r"\bSE5\s*->\s*\w+", re.IGNORECASE),
            re.compile(r'dbSelectArea\s*\(\s*["\']SE5["\']\s*\)', re.IGNORECASE),
        ],
        auto_fix="comment_with_todo",
    ),
    Rule(
        code="CA2022",
        title="Uso não permitido de StaticCall",
        severity=BUG,
        category="Security",
        description="A função StaticCall é restrita.",
        how_to_fix="Não use StaticCall; refatore para chamada direta.",
        patterns=[
            re.compile(r"\bSTATICCALL\s*\(", re.IGNORECASE),
        ],
    ),
    Rule(
        code="CA2023",
        title="Uso não permitido de PTInternal",
        severity=BUG,
        category="Security",
        description="PTInternal é função restrita ao framework.",
        how_to_fix="Não use PTInternal em customizações.",
        patterns=[
            re.compile(r"\bPTINTERNAL\s*\(", re.IGNORECASE),
        ],
    ),
    Rule(
        code="CA3002",
        title="Herança feita de forma incorreta",
        severity=BUG,
        category="Maintainability",
        description="Herança de classes do framework feita sem seguir o padrão recomendado.",
        how_to_fix="Siga o padrão de herança documentado (FROM ClasseBase).",
        patterns=[
            # Heurística: 'inherits' (não-padrão) em vez de 'from'
            re.compile(r"\bclass\b.*\binherits\b", re.IGNORECASE),
        ],
    ),

    # --------------- CODE SMELLS ---------------
    Rule(
        code="CA1001",
        title="Uso indevido de Bloqueio Exclusivo no FileSystem/RootPath",
        severity=CODE_SMELL,
        category="Performance",
        description="Bloqueios exclusivos no RootPath afetam SmartERP com filesystem compartilhado.",
        how_to_fix="Use diretórios locais ou bloqueios cooperativos.",
        patterns=[
            re.compile(r"\bLockByName\s*\(.*\.T\.\s*,\s*\.T\.\s*\)", re.IGNORECASE),
        ],
    ),
    Rule(
        code="CA1004",
        title="Uso não permitido de API de Console",
        severity=CODE_SMELL,
        category="Maintainability",
        description="ConOut, OutErr, OutStd, ? e ?? devem ser substituídos por FWLogMsg com I18N.",
        how_to_fix="Use FWLogMsg para logging, com strings internacionalizadas (I18N).",
        patterns=[
            re.compile(r"\b(CONOUT|OUTERR|OUTSTD)\s*\(", re.IGNORECASE),
        ],
        auto_fix="comment_with_fwlogmsg_todo",
    ),
    Rule(
        code="CA1006",
        title="Função descontinuada - AllUsers",
        severity=CODE_SMELL,
        category="Maintainability",
        description="AllUsers() foi descontinuada. Use FWSFAllUsers().",
        how_to_fix="Substitua AllUsers() por FWSFAllUsers().",
        patterns=[
            re.compile(r"\bAllUsers\s*\(", re.IGNORECASE),
        ],
        auto_fix="replace_identifier",
    ),
    Rule(
        code="CA2015",
        title="Sobrescrita de FormCommit não recomendada",
        severity=CODE_SMELL,
        category="Pitfall",
        description="Sobrescrita do FormCommit não é recomendada.",
        how_to_fix="Use API de ciclo de vida (FWModelEvent).",
        patterns=[
            # Detecta declaração de função chamada FormCommit
            re.compile(r"\b(STATIC\s+)?FUNCTION\s+FormCommit\b", re.IGNORECASE),
        ],
    ),
    Rule(
        code="CA2052",
        title="Senha Exposta",
        severity=CODE_SMELL,
        category="Security",
        description="Possível senha em texto literal no código-fonte.",
        how_to_fix="Use GetMV() ou substitua via pipeline de deploy.",
        # Heurística: variáveis com nome típico de senha recebendo string literal
        patterns=[
            re.compile(
                r"\b(senha|password|passwd|pwd|secret|api_?key|apitoken|token)\s*:?=\s*[\"'][^\"']{3,}[\"']",
                re.IGNORECASE,
            ),
        ],
        needs_strings=True,
        auto_fix="comment_password_with_todo",
        needs_ai_review=True,
        ai_prompt="""Analise o código AdvPL/TLPP contra a regra **CA2052 (Senha exposta)**.

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

**Importante:** seja conservador. Marque `is_violation=true` apenas quando claramente houver credencial real exposta. Em caso de dúvida, marque `false` com `reasoning` explicando.""",
    ),
    Rule(
        code="CA3001",
        title="Include deve estar em lower case",
        severity=CODE_SMELL,
        category="Pitfall",
        description="O nome do arquivo de include deve estar em lowercase. Qualquer letra maiúscula no nome do arquivo dispara esta regra.",
        how_to_fix="Coloque o nome do arquivo de include em minúsculas. Ex: `#include \"PROTHEUS.CH\"` → `#include \"protheus.ch\"`.",
        # Detecta include cujo NOME DE ARQUIVO contém pelo menos uma letra maiúscula.
        # IMPORTANTE: usamos (?i:include) para tornar APENAS a palavra "include" case-insensitive,
        # mantendo o [A-Z] do nome do arquivo case-sensitive. Aplicar re.IGNORECASE no regex
        # inteiro fazia o [A-Z] casar qualquer letra, gerando falso positivo em todo include.
        patterns=[
            re.compile(
                r'^\s*#\s*(?i:include)\s+["\'<]([^"\'>]*[A-Z][^"\'>]*)["\'>]',
                re.MULTILINE,
            ),
        ],
        needs_strings=True,
        auto_fix="lowercase_include",
    ),
    Rule(
        code="CA4000",
        title="Não utilização de IIF",
        severity=CODE_SMELL,
        category="Maintainability",
        description="Construções IIF()/IF() ternárias dificultam leitura e debug.",
        how_to_fix="Refatore para if/else/endif tradicional.",
        patterns=[
            re.compile(r"\bIIF\s*\(", re.IGNORECASE),
        ],
        auto_fix="iif_to_if_else",
    ),

    # --------------- VULNERABILIDADES ---------------
    Rule(
        code="CA2050",
        title="Sql Inject",
        severity=VULNERABILIDADE,
        category="Security",
        description="Concatenação de strings em queries SQL permite injeção. Use parameter binding.",
        how_to_fix="Use FWPreparedStatement ou TcGenQry2 com placeholders (?).",
        # Detecta múltiplos padrões de concatenação suspeita em SQL
        patterns=[
            # 1. TcGenQry/TcSqlExec/TcQuery com concatenação literal nos parâmetros
            re.compile(
                r"\b(TCGENQRY|TCSQLEXEC|TCQUERY)\s*\([^)]*\+[^)]*\)",
                re.IGNORECASE | re.DOTALL,
            ),
            # 2. Variável recebendo string com SQL DML + concatenação na mesma linha
            re.compile(
                r":?=\s*[\"'].*\b(SELECT|INSERT|UPDATE|DELETE|WHERE|FROM)\b.*[\"']\s*\+",
                re.IGNORECASE,
            ),
            # 3. Continuação de SQL: " + var + " " seguida de palavra SQL
            re.compile(
                r"[\"']\s*\+\s*\w+\s*\+\s*[\"']\s*(AND|OR|WHERE|FROM|SET|VALUES)\b",
                re.IGNORECASE,
            ),
            # 4. BeginSql + concat (BeginSql Alias normalmente é seguro, mas se tiver + é suspeito)
            re.compile(
                r"\bBeginSql\b[^E]*\+[^E]*\bEndSql\b",
                re.IGNORECASE | re.DOTALL,
            ),
        ],
        needs_strings=True,
        needs_ai_review=True,
        ai_prompt="""Analise o código AdvPL/TLPP contra a regra **CA2050 (SQL Injection)**.

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

**Importante:** rastreie a origem da variável dentro do arquivo. Se ela é atribuída e DEPOIS passada por uma função de limpeza antes do uso na query, é seguro. Se passa direto, é violação.""",
    ),
]


# Dicionário por código pra lookup rápido
RULES_BY_CODE: dict[str, Rule] = {r.code: r for r in RULES}


def get_rule(code: str) -> Optional[Rule]:
    return RULES_BY_CODE.get(code)


def rules_by_severity() -> dict[str, list[Rule]]:
    out = {BUG: [], CODE_SMELL: [], VULNERABILIDADE: []}
    for r in RULES:
        out[r.severity].append(r)
    return out


def regex_only_rules() -> list[Rule]:
    """Regras que NÃO precisam de revisão da IA. São inequívocas por regex."""
    return [r for r in RULES if not r.needs_ai_review]


def ai_review_rules() -> list[Rule]:
    """Regras que precisam de revisão semântica da IA (Claude da sessão)."""
    return [r for r in RULES if r.needs_ai_review]
