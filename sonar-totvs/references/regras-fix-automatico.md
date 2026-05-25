# Regras com Fix Automático

Esta skill implementa correção automática para 7 das ~60 regras catalogadas. As demais são **detectadas e reportadas com prompt para o Claude**, mas não corrigidas automaticamente.

## Tabela de fixes

| Código | Severidade | Risco do fix | Estratégia |
|--------|-----------|--------------|------------|
| CA3001 | Code Smell | Muito baixo | Lowercase no nome do arquivo do `#include` |
| CA4000 | Code Smell | Médio | Converte `IIF()` standalone em `If/Else/EndIf` (apenas quando é statement de linha inteira; expressões inline ficam como TODO) |
| CA1004 | Code Smell | Baixo | Comenta a linha original e adiciona comentário TODO sugerindo `FWLogMsg` com `I18N` |
| CA1006 | Code Smell | Baixo | Substituição direta de identificador: `AllUsers()` → `FWSFAllUsers()` |
| CA2021 | Bug | Médio | Comenta a linha e adiciona TODO indicando tabela descontinuada |
| CA2020 | Bug | Baixo | Adiciona `// TODO: função descontinuada — verificar substituta no TDN` ao lado |
| CA2052 | Code Smell (Security) | Médio | Comenta a atribuição literal e adiciona TODO indicando uso de `GetMV()` ou pipeline de deploy |

## Modos de execução

Quando o usuário pedir correção, a skill aceita três níveis:

### `safe` (padrão sugerido)
Apenas as duas regras de risco muito baixo / triviais:
- `CA3001` (include lowercase)
- `CA4000` (IIF → If/Else, só os standalone)

### `medium`
As `safe` mais as substituições diretas de identificador:
- `CA3001`, `CA4000`, `CA1004`, `CA1006`

### `all`
Todas as 7 regras com fix implementado. Use com cuidado — inclui comentar linhas (CA2021, CA2052) o que pode quebrar comportamento se não for revisado.

### Customizado
Lista explícita: `--rules CA3001,CA1006,CA2020`

## Regras sem fix automático (geram só prompt)

Todas as demais regras CA0000-CA2050 não listadas acima caem em uma destas categorias e por isso não têm fix automático:

- **Refatoração arquitetural** (CA1000 ISAM → FWTemporaryTable, CA1002 interface em transação): requer entender contexto do programa
- **Manipulação de metadados** (CA2000-CA2014): cada caso depende da API substituta correta para aquele alias
- **Sql Inject** (CA2050): refatorar para PreparedStatement requer entender a query inteira
- **Erro de compilação** (CA0000): cada caso é único
- **APIs proibidas** (CA2017, CA2018, CA2019, CA2022, CA2023): substituição varia caso a caso

Para essas, o relatório gera um **prompt específico por ocorrência** que o desenvolvedor cola em outra conversa com o Claude.
