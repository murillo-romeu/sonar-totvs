"""
analyzer.py — Varredura de projetos TOTVS Protheus contra regras Sonar TOTVS.

Uso:
    python analyzer.py --project /path/to/project --skill-dir /path/to/skill
"""

import argparse
import os
import re
import sys
import json
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# Garante import local
sys.path.insert(0, str(Path(__file__).parent))
from rules import RULES, BUG, CODE_SMELL, VULNERABILIDADE, get_rule, regex_only_rules, ai_review_rules
import report


SUPPORTED_EXTENSIONS = {".prw", ".tlpp"}
IGNORE_DIRS = {".git", "node_modules", "dist", "build", ".vscode", "sonar_totvs", ".advpl", ".tlpp"}


@dataclass
class Issue:
    rule_code: str
    rule_title: str
    severity: str
    category: str
    file: str          # caminho relativo ao projeto
    line: int          # 1-indexed
    column: int        # 1-indexed
    snippet: str       # contexto (linha + vizinhas)
    matched_text: str  # texto exato que disparou a regra
    # Origem: "regex" (detecção pura) ou "ai" (confirmada pela IA)
    origin: str = "regex"
    # Status da revisão de IA: None (não precisa), "pending", "confirmed", "rejected"
    ai_status: Optional[str] = None
    # Justificativa quando ai_status == "rejected" ou "confirmed"
    ai_reasoning: Optional[str] = None
    # Nível de confiança da IA: "high" / "medium" / "low"
    ai_confidence: Optional[str] = None

    def to_dict(self):
        return asdict(self)


# ============================================================================
# MASCARAMENTO DE COMENTÁRIOS E STRINGS
# ============================================================================

def mask_comments(source: str) -> str:
    """Substitui comentários por espaços preservando posições (newlines mantidas)."""
    out = []
    i = 0
    n = len(source)
    while i < n:
        c = source[i]
        nxt = source[i+1] if i+1 < n else ''
        # Bloco /* ... */
        if c == '/' and nxt == '*':
            j = source.find('*/', i+2)
            if j == -1:
                j = n
            else:
                j += 2
            for k in range(i, j):
                out.append('\n' if source[k] == '\n' else ' ')
            i = j
            continue
        # Linha //
        if c == '/' and nxt == '/':
            j = source.find('\n', i)
            if j == -1:
                j = n
            for k in range(i, j):
                out.append(' ')
            i = j
            continue
        # Linha de comentário AdvPL/TLPP com //
        # Linha de comentário com * no início (AdvPL clássico): * comment
        if c == '*':
            # Verifica se é inicio de linha (só whitespace antes nessa linha)
            line_start = source.rfind('\n', 0, i)
            line_start = 0 if line_start == -1 else line_start + 1
            if source[line_start:i].strip() == '':
                j = source.find('\n', i)
                if j == -1:
                    j = n
                for k in range(i, j):
                    out.append(' ')
                i = j
                continue
        out.append(c)
        i += 1
    return ''.join(out)


def mask_strings(source: str) -> str:
    """Substitui conteúdo de strings literais por espaços (preservando aspas).

    Importante: AdvPL/TLPP NÃO usa contrabarra como escape em strings.
    "C:\\TOTVS\\" é literalmente C:\\TOTVS\\ — a string termina na primeira aspa
    que aparece depois da abertura, e strings não podem cruzar linhas.
    """
    def repl(m):
        text = m.group(0)
        quote = text[0]
        inner = text[1:-1]
        return quote + (' ' * len(inner)) + quote

    # Strings não cruzam newlines. Aspas duplas e simples são delimitadores literais.
    pattern = re.compile(r'"[^"\n]*"' + r"|'[^'\n]*'")
    return pattern.sub(repl, source)


def line_col_from_offset(source: str, offset: int) -> tuple[int, int]:
    """Converte offset para (linha, coluna) ambos 1-indexed."""
    if offset >= len(source):
        offset = len(source) - 1 if len(source) > 0 else 0
    line = source.count('\n', 0, offset) + 1
    last_nl = source.rfind('\n', 0, offset)
    col = offset - last_nl if last_nl >= 0 else offset + 1
    return line, col


def extract_snippet(source: str, line: int, context: int = 2) -> str:
    """Retorna a linha + N linhas de contexto, prefixada com numeração."""
    lines = source.splitlines()
    start = max(0, line - 1 - context)
    end = min(len(lines), line + context)
    out = []
    width = len(str(end))
    for i in range(start, end):
        marker = ">> " if (i + 1) == line else "   "
        out.append(f"{marker}{str(i+1).rjust(width)} | {lines[i]}")
    return "\n".join(out)


# ============================================================================
# DETECÇÃO
# ============================================================================

def analyze_file(filepath: Path, project_root: Path) -> list[Issue]:
    """Analisa um arquivo individual aplicando todas as regras."""
    issues: list[Issue] = []
    try:
        try:
            raw = filepath.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raw = filepath.read_text(encoding="cp1252", errors="replace")
    except Exception as e:
        print(f"[WARN] Não foi possível ler {filepath}: {e}", file=sys.stderr)
        return issues

    # Versão sem comentários (mantém posições)
    no_comments = mask_comments(raw)
    # Versão também sem strings (para regras que não precisam ler conteúdo de string)
    no_strings = mask_strings(no_comments)

    rel_path = str(filepath.relative_to(project_root))

    for rule in RULES:
        target = no_comments if rule.needs_strings else no_strings
        seen_lines = set()  # evita duplicar issue da mesma linha pra mesma regra
        for pattern in rule.patterns:
            for match in pattern.finditer(target):
                offset = match.start()
                line, col = line_col_from_offset(raw, offset)
                key = (rule.code, line)
                if key in seen_lines:
                    continue
                seen_lines.add(key)
                snippet = extract_snippet(raw, line)
                matched = match.group(0)[:120]
                issues.append(Issue(
                    rule_code=rule.code,
                    rule_title=rule.title,
                    severity=rule.severity,
                    category=rule.category,
                    file=rel_path,
                    line=line,
                    column=col,
                    snippet=snippet,
                    matched_text=matched,
                    origin="regex",
                    ai_status="pending" if rule.needs_ai_review else None,
                ))
    return issues


def walk_project(project_root: Path) -> list[Path]:
    """Encontra todos os .prw e .tlpp no projeto, ignorando dirs irrelevantes."""
    found: list[Path] = []
    for root, dirs, files in os.walk(project_root):
        # filtra in-place pra os.walk não descer
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith('.')]
        for fname in files:
            if Path(fname).suffix.lower() in SUPPORTED_EXTENSIONS:
                found.append(Path(root) / fname)
    return found


# ============================================================================
# SCORE
# ============================================================================

WEIGHTS = {BUG: 3, VULNERABILIDADE: 5, CODE_SMELL: 1}


def calculate_scores(issues: list[Issue], total_files: int) -> dict:
    if total_files == 0:
        return {"simple": 100.0, "weighted": 100.0, "files_clean": 0, "files_total": 0}

    files_with_issues = {i.file for i in issues}
    files_clean = total_files - len(files_with_issues)
    simple = (files_clean / total_files) * 100

    # Score ponderado: penaliza issues ponderadas por severidade, normalizado por # arquivos.
    # Fórmula: 100 - min(100, (Σ pesos / arquivos) * 2)
    # Calibração: ~10 bugs em 10 arquivos = 100-20 = 80%. 5 vulnerab. em 10 arqs = 100-5 = 95%
    # (fórmula anterior multiplicava por 10, era agressiva demais)
    weighted_sum = sum(WEIGHTS[i.severity] for i in issues)
    penalty = min(100.0, (weighted_sum / total_files) * 2)
    weighted = max(0.0, 100.0 - penalty)

    return {
        "simple": round(simple, 2),
        "weighted": round(weighted, 2),
        "files_clean": files_clean,
        "files_total": total_files,
    }


# ============================================================================
# PROMPT PARA CORREÇÃO VIA CLAUDE
# ============================================================================

def build_fix_prompt(issue: Issue) -> str:
    rule = get_rule(issue.rule_code)
    return f"""Corrija a violação da regra Sonar TOTVS **{issue.rule_code} ({rule.title})** no arquivo `{issue.file}`, linha {issue.line}.

**Descrição da regra:**
{rule.description}

**Como corrigir (orientação do Sonar):**
{rule.how_to_fix}

**Trecho atual do código:**
```advpl
{issue.snippet}
```

**Texto que disparou a regra:** `{issue.matched_text}`

Refatore aplicando a orientação acima. Preserve a lógica original, o estilo e a indentação do arquivo. Se a correção não for trivial ou exigir contexto adicional (outras chamadas, escopo de transação, etc), explique o que precisaria ser verificado antes de aplicar."""


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Sonar TOTVS — Analyzer")
    parser.add_argument("--project", required=True, help="Caminho raiz do projeto a analisar")
    parser.add_argument("--skill-dir", required=True, help="Diretório raiz da skill (para encontrar templates)")
    parser.add_argument("--output-dir", default=None, help="Override do diretório de saída (default: {project}/sonar_totvs)")
    parser.add_argument(
        "--ai-mode",
        choices=["none", "candidates", "all-files"],
        default="candidates",
        help=(
            "Como gerar a fila de revisão IA: "
            "'none' = não gera fila (só regex); "
            "'candidates' = só arquivos com candidatos de regex (default, mais rápido); "
            "'all-files' = todos os arquivos do projeto contra todas as regras complexas (mais lento, mais completo)."
        ),
    )
    args = parser.parse_args()

    project_root = Path(args.project).resolve()
    skill_dir = Path(args.skill_dir).resolve()

    if not project_root.is_dir():
        print(f"ERRO: projeto não é um diretório válido: {project_root}", file=sys.stderr)
        sys.exit(2)

    output_dir = Path(args.output_dir) if args.output_dir else (project_root / "sonar_totvs")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] Analisando: {project_root}")
    files = walk_project(project_root)
    print(f"[INFO] Encontrados {len(files)} arquivos .prw/.tlpp")

    if not files:
        print("[WARN] Nenhum arquivo .prw ou .tlpp encontrado. Abortando.", file=sys.stderr)
        sys.exit(1)

    all_issues: list[Issue] = []
    for i, fp in enumerate(files, 1):
        if i % 50 == 0:
            print(f"[INFO] Progresso: {i}/{len(files)}")
        all_issues.extend(analyze_file(fp, project_root))

    print(f"[INFO] {len(all_issues)} issues encontradas (regex)")

    # Conta por severidade
    counts = {BUG: 0, CODE_SMELL: 0, VULNERABILIDADE: 0}
    for iss in all_issues:
        counts[iss.severity] += 1
    print(f"[INFO] Bugs: {counts[BUG]} | Code Smells: {counts[CODE_SMELL]} | Vulnerabilidades: {counts[VULNERABILIDADE]}")

    # Identifica issues pendentes de revisão IA
    pending_ai = [iss for iss in all_issues if iss.ai_status == "pending"]
    print(f"[INFO] {len(pending_ai)} issues marcadas como 'pending' (precisam de revisão IA)")

    scores = calculate_scores(all_issues, len(files))
    print(f"[INFO] Score simples: {scores['simple']}%  |  Score ponderado: {scores['weighted']}%")

    # Gera arquivos
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"relatorio_{timestamp}.html"
    json_path = output_dir / f"relatorio_{timestamp}.json"
    queue_path = output_dir / f"ai-queue_{timestamp}.jsonl"

    # Gera a fila de IA se aplicável
    ai_queue_info = generate_ai_queue(
        mode=args.ai_mode,
        files=files,
        all_issues=all_issues,
        project_root=project_root,
        queue_path=queue_path,
    )

    # Anexa prompts às issues
    issues_with_prompts = []
    for iss in all_issues:
        d = iss.to_dict()
        d["fix_prompt"] = build_fix_prompt(iss)
        issues_with_prompts.append(d)

    payload = {
        "kind": "analysis",
        "timestamp": timestamp,
        "project": str(project_root),
        "files_analyzed": len(files),
        "scores": scores,
        "counts": {
            "bugs": counts[BUG],
            "code_smells": counts[CODE_SMELL],
            "vulnerabilidades": counts[VULNERABILIDADE],
            "total": len(all_issues),
        },
        "ai_review": ai_queue_info,
        "issues": issues_with_prompts,
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    html = report.render_report(payload, skill_dir)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n[OK] Relatório HTML: {report_path}")
    print(f"[OK] Dados JSON: {json_path}")
    if ai_queue_info["queue_size"] > 0:
        print(f"[OK] Fila IA: {queue_path} ({ai_queue_info['queue_size']} arquivos para revisão)")
        print(f"\n[INFO] Próximo passo: instruir o Claude da sessão a processar a fila de IA.")
        print(f"       Veja {skill_dir}/SKILL.md, seção 'Fase 2: Revisão IA'.")


def generate_ai_queue(
    mode: str,
    files: list[Path],
    all_issues: list[Issue],
    project_root: Path,
    queue_path: Path,
) -> dict:
    """Gera o arquivo .jsonl com blocos para revisão IA pelo Claude da sessão.

    Retorna metadados sobre a fila para inclusão no payload.
    """
    if mode == "none":
        return {"mode": "none", "queue_size": 0, "queue_file": None, "rules": []}

    ai_rules = ai_review_rules()
    ai_rule_codes = {r.code for r in ai_rules}

    # Agrupa issues "pending" por arquivo
    pending_by_file: dict[str, list[Issue]] = {}
    for iss in all_issues:
        if iss.ai_status == "pending":
            pending_by_file.setdefault(iss.file, []).append(iss)

    # Lista de arquivos que vão entrar na fila
    if mode == "candidates":
        target_files = [project_root / rel for rel in pending_by_file.keys()]
    elif mode == "all-files":
        target_files = files
    else:
        target_files = []

    # Escreve a fila
    with open(queue_path, "w", encoding="utf-8") as f:
        for fp in target_files:
            rel = str(fp.relative_to(project_root))
            try:
                try:
                    content = fp.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    content = fp.read_text(encoding="cp1252", errors="replace")
            except Exception as e:
                print(f"[WARN] Pulando {fp} na fila IA: {e}", file=sys.stderr)
                continue

            # Decide quais regras aplicar a este arquivo
            if mode == "candidates":
                # Só as regras que regex marcou como pendentes nesse arquivo
                file_rule_codes = sorted({iss.rule_code for iss in pending_by_file.get(rel, [])})
            else:  # all-files
                file_rule_codes = sorted(ai_rule_codes)

            if not file_rule_codes:
                continue

            block = {
                "file": rel,
                "rules": file_rule_codes,
                "candidates": [
                    {"rule_code": iss.rule_code, "line": iss.line, "matched_text": iss.matched_text}
                    for iss in pending_by_file.get(rel, [])
                ],
                "content": content,
            }
            f.write(json.dumps(block, ensure_ascii=False) + "\n")

    # Conta entradas
    queue_size = 0
    with open(queue_path, "r", encoding="utf-8") as f:
        for _ in f:
            queue_size += 1

    return {
        "mode": mode,
        "queue_size": queue_size,
        "queue_file": queue_path.name,
        "rules": sorted(ai_rule_codes),
    }


if __name__ == "__main__":
    main()
