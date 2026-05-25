"""
fixer.py — Aplica correções automáticas em arquivos .prw/.tlpp.

Uso:
    python fixer.py --project /path/to/project --skill-dir /path/to/skill --rules CA3001,CA4000
    python fixer.py --project /path/to/project --skill-dir /path/to/skill --rules safe
    python fixer.py --project /path/to/project --skill-dir /path/to/skill --rules medium
    python fixer.py --project /path/to/project --skill-dir /path/to/skill --rules all
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from rules import RULES_BY_CODE, BUG, CODE_SMELL, VULNERABILIDADE
import analyzer
import report


# Grupos de regras
FIX_GROUPS = {
    "safe":   ["CA3001", "CA4000"],
    "medium": ["CA3001", "CA4000", "CA1004", "CA1006"],
    "all":    ["CA3001", "CA4000", "CA1004", "CA1006", "CA2020", "CA2021", "CA2052"],
}


# ============================================================================
# FIXES INDIVIDUAIS
# ============================================================================

def fix_ca3001(source: str) -> tuple[str, int]:
    """#include "FILE.CH" -> #include "file.ch" """
    count = 0
    def repl(m):
        nonlocal count
        prefix = m.group(1)
        opener = m.group(2)
        name = m.group(3)
        closer = m.group(4)
        if name.lower() != name:
            count += 1
            return f'{prefix}{opener}{name.lower()}{closer}'
        return m.group(0)

    pattern = re.compile(
        r'(^\s*#\s*include\s+)(["\'<])([^"\'>]+)(["\'>])',
        re.IGNORECASE | re.MULTILINE
    )
    new_source = pattern.sub(repl, source)
    return new_source, count


def fix_ca4000(source: str) -> tuple[str, int]:
    """
    IIF(cond, a, b) como statement de linha inteira (atribuição) → If/Else/EndIf.
    Só converte casos seguros: linhas tipo `var := IIF(cond, a, b)`.
    Casos inline em expressões maiores ficam como TODO.
    """
    count = 0
    lines = source.splitlines(keepends=True)
    out = []

    # Regex: linha com IIF dentro de uma atribuição simples
    assign_iif = re.compile(
        r'^(\s*)([\w\->\.]+)\s*:?=\s*IIF\s*\((.+)\)\s*$',
        re.IGNORECASE
    )

    for raw_line in lines:
        # Sem o trailing newline pra match
        line = raw_line.rstrip('\n').rstrip('\r')
        ending = raw_line[len(line):]
        m = assign_iif.match(line)
        if m:
            indent = m.group(1)
            var = m.group(2)
            args_str = m.group(3)
            # Precisa dividir args em 3, respeitando parênteses aninhados
            args = _split_iif_args(args_str)
            if args and len(args) == 3:
                cond, val_true, val_false = args
                out.append(f"{indent}If {cond.strip()}\n")
                out.append(f"{indent}\t{var} := {val_true.strip()}\n")
                out.append(f"{indent}Else\n")
                out.append(f"{indent}\t{var} := {val_false.strip()}\n")
                out.append(f"{indent}EndIf\n")
                count += 1
                continue
        # Marca outras ocorrências de IIF com TODO
        if re.search(r'\bIIF\s*\(', line, re.IGNORECASE) and 'TODO CA4000' not in line:
            out.append(line + '  // TODO CA4000: refatorar IIF para If/Else' + ending)
        else:
            out.append(raw_line)

    return ''.join(out), count


def _split_iif_args(args_str: str) -> list[str] | None:
    """Divide a string interna de IIF(...) em [cond, true_val, false_val] respeitando parênteses."""
    depth = 0
    parts = []
    buf = []
    in_str = None
    for ch in args_str:
        if in_str:
            buf.append(ch)
            if ch == in_str and (len(buf) < 2 or buf[-2] != '\\'):
                in_str = None
            continue
        if ch in ('"', "'"):
            in_str = ch
            buf.append(ch)
            continue
        if ch == '(':
            depth += 1
            buf.append(ch)
            continue
        if ch == ')':
            depth -= 1
            buf.append(ch)
            continue
        if ch == ',' and depth == 0:
            parts.append(''.join(buf))
            buf = []
            continue
        buf.append(ch)
    if buf:
        parts.append(''.join(buf))
    return parts if len(parts) == 3 else None


def fix_ca1004(source: str) -> tuple[str, int]:
    """ConOut/OutErr/OutStd → comenta e adiciona TODO sugerindo FWLogMsg + I18N."""
    count = 0
    lines = source.splitlines(keepends=True)
    out = []
    pattern = re.compile(r'\b(CONOUT|OUTERR|OUTSTD)\s*\(', re.IGNORECASE)
    for raw_line in lines:
        line = raw_line.rstrip('\n').rstrip('\r')
        ending = raw_line[len(line):]
        stripped = line.lstrip()
        # Não tocar se já é comentário ou já tem TODO
        if stripped.startswith('//') or 'TODO CA1004' in line:
            out.append(raw_line)
            continue
        if pattern.search(line):
            indent = line[:len(line) - len(stripped)]
            out.append(f"{indent}// TODO CA1004: substituir por FWLogMsg com I18N\n")
            out.append(f"{indent}// {stripped}{ending}")
            count += 1
        else:
            out.append(raw_line)
    return ''.join(out), count


def fix_ca1006(source: str) -> tuple[str, int]:
    """AllUsers() → FWSFAllUsers()."""
    count = 0
    pattern = re.compile(r'\bAllUsers\s*\(', re.IGNORECASE)
    def repl(m):
        nonlocal count
        count += 1
        return 'FWSFAllUsers('
    new = pattern.sub(repl, source)
    return new, count


def fix_ca2020(source: str) -> tuple[str, int]:
    """Adiciona TODO ao lado de chamadas a funções descontinuadas conhecidas."""
    count = 0
    deprecated = ['MSCBINFO', 'MSCBPRINTLABEL', 'MSGETDB', 'MSWORKAREA']
    pattern = re.compile(r'\b(' + '|'.join(deprecated) + r')\s*\(', re.IGNORECASE)
    lines = source.splitlines(keepends=True)
    out = []
    for raw_line in lines:
        line = raw_line.rstrip('\n').rstrip('\r')
        ending = raw_line[len(line):]
        if pattern.search(line) and 'TODO CA2020' not in line and not line.lstrip().startswith('//'):
            out.append(line + '  // TODO CA2020: função descontinuada — verificar substituta no TDN' + ending)
            count += 1
        else:
            out.append(raw_line)
    return ''.join(out), count


def fix_ca2021(source: str) -> tuple[str, int]:
    """Comenta linha que usa SE5 e adiciona TODO."""
    count = 0
    pattern = re.compile(r'\bSE5\s*->|\bdbSelectArea\s*\(\s*["\']SE5["\']', re.IGNORECASE)
    lines = source.splitlines(keepends=True)
    out = []
    for raw_line in lines:
        line = raw_line.rstrip('\n').rstrip('\r')
        ending = raw_line[len(line):]
        stripped = line.lstrip()
        if stripped.startswith('//') or 'TODO CA2021' in line:
            out.append(raw_line)
            continue
        if pattern.search(line):
            indent = line[:len(line) - len(stripped)]
            out.append(f"{indent}// TODO CA2021: tabela SE5 descontinuada\n")
            out.append(f"{indent}// {stripped}{ending}")
            count += 1
        else:
            out.append(raw_line)
    return ''.join(out), count


def fix_ca2052(source: str) -> tuple[str, int]:
    """Substitui atribuição literal a campos tipo senha com TODO + GetMV."""
    count = 0
    pattern = re.compile(
        r'\b(senha|password|passwd|pwd|secret|api_?key|apitoken|token)(\s*:?=\s*)(["\'][^"\']{3,}["\'])',
        re.IGNORECASE
    )
    lines = source.splitlines(keepends=True)
    out = []
    for raw_line in lines:
        line = raw_line.rstrip('\n').rstrip('\r')
        ending = raw_line[len(line):]
        stripped = line.lstrip()
        if stripped.startswith('//') or 'TODO CA2052' in line:
            out.append(raw_line)
            continue
        if pattern.search(line):
            indent = line[:len(line) - len(stripped)]
            out.append(f"{indent}// TODO CA2052: senha exposta — usar GetMV() ou pipeline de deploy\n")
            out.append(f"{indent}// {stripped}{ending}")
            count += 1
        else:
            out.append(raw_line)
    return ''.join(out), count


# Mapeia código → função de fix
FIX_FUNCTIONS = {
    "CA3001": fix_ca3001,
    "CA4000": fix_ca4000,
    "CA1004": fix_ca1004,
    "CA1006": fix_ca1006,
    "CA2020": fix_ca2020,
    "CA2021": fix_ca2021,
    "CA2052": fix_ca2052,
}


# ============================================================================
# MAIN
# ============================================================================

def parse_rules_arg(arg: str) -> list[str]:
    if arg in FIX_GROUPS:
        return FIX_GROUPS[arg]
    return [r.strip().upper() for r in arg.split(',') if r.strip()]


def main():
    parser = argparse.ArgumentParser(description="Sonar TOTVS — Fixer")
    parser.add_argument("--project", required=True)
    parser.add_argument("--skill-dir", required=True)
    parser.add_argument("--rules", required=True,
                        help="Lista de códigos separados por vírgula, ou 'safe' | 'medium' | 'all'")
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    project_root = Path(args.project).resolve()
    skill_dir = Path(args.skill_dir).resolve()

    if not project_root.is_dir():
        print(f"ERRO: projeto inválido: {project_root}", file=sys.stderr)
        sys.exit(2)

    rules_to_fix = parse_rules_arg(args.rules)
    valid_rules = [r for r in rules_to_fix if r in FIX_FUNCTIONS]
    invalid = [r for r in rules_to_fix if r not in FIX_FUNCTIONS]
    if invalid:
        print(f"[WARN] Regras sem fix automático (serão ignoradas): {invalid}", file=sys.stderr)
    if not valid_rules:
        print(f"ERRO: nenhuma regra válida. Opções: {list(FIX_FUNCTIONS.keys())} ou groups {list(FIX_GROUPS.keys())}", file=sys.stderr)
        sys.exit(2)

    print(f"[INFO] Aplicando correções para regras: {valid_rules}")

    output_dir = Path(args.output_dir) if args.output_dir else (project_root / "sonar_totvs")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Roda análise PRÉ
    files = analyzer.walk_project(project_root)
    if not files:
        print("[WARN] Nenhum arquivo .prw/.tlpp encontrado.", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] Análise pré-correção em {len(files)} arquivos...")
    issues_before = []
    for fp in files:
        issues_before.extend(analyzer.analyze_file(fp, project_root))
    scores_before = analyzer.calculate_scores(issues_before, len(files))
    print(f"[INFO] Antes: {len(issues_before)} issues. Score simples {scores_before['simple']}%, ponderado {scores_before['weighted']}%")

    # 2. Aplica fixes arquivo a arquivo
    fix_log = []  # {file, rule, count}
    total_fixed = 0
    for fp in files:
        try:
            try:
                content = fp.read_text(encoding="utf-8")
                enc = "utf-8"
            except UnicodeDecodeError:
                content = fp.read_text(encoding="cp1252", errors="replace")
                enc = "cp1252"
        except Exception as e:
            print(f"[WARN] Pulando {fp}: {e}", file=sys.stderr)
            continue

        new_content = content
        file_changed = False
        for rule_code in valid_rules:
            fix_fn = FIX_FUNCTIONS[rule_code]
            new_content, count = fix_fn(new_content)
            if count > 0:
                fix_log.append({
                    "file": str(fp.relative_to(project_root)),
                    "rule": rule_code,
                    "count": count,
                })
                total_fixed += count
                file_changed = True

        if file_changed:
            fp.write_text(new_content, encoding=enc)

    print(f"[INFO] Total de fixes aplicados: {total_fixed}")

    # 3. Roda análise PÓS
    print(f"[INFO] Análise pós-correção...")
    issues_after = []
    for fp in files:
        issues_after.extend(analyzer.analyze_file(fp, project_root))
    scores_after = analyzer.calculate_scores(issues_after, len(files))
    print(f"[INFO] Depois: {len(issues_after)} issues. Score simples {scores_after['simple']}%, ponderado {scores_after['weighted']}%")

    # 4. Conta por severidade pós
    counts = {BUG: 0, CODE_SMELL: 0, VULNERABILIDADE: 0}
    for iss in issues_after:
        counts[iss.severity] += 1

    # 5. Anexa prompts às issues remanescentes
    issues_with_prompts = []
    for iss in issues_after:
        d = iss.to_dict()
        d["fix_prompt"] = analyzer.build_fix_prompt(iss)
        issues_with_prompts.append(d)

    # 6. Gera relatório
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"correcao_{timestamp}.html"
    json_path = output_dir / f"correcao_{timestamp}.json"

    payload = {
        "kind": "fix",
        "timestamp": timestamp,
        "project": str(project_root),
        "files_analyzed": len(files),
        "rules_applied": valid_rules,
        "fixed_count": total_fixed,
        "unfixed_count": len(issues_after),
        "fix_log": fix_log,
        "scores_before": scores_before,
        "scores_after": scores_after,
        "scores": scores_after,  # campo unificado para o template
        "counts": {
            "bugs": counts[BUG],
            "code_smells": counts[CODE_SMELL],
            "vulnerabilidades": counts[VULNERABILIDADE],
            "total": len(issues_after),
        },
        "issues": issues_with_prompts,
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    html = report.render_report(payload, skill_dir)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n[OK] {total_fixed} correções aplicadas")
    print(f"[OK] {len(issues_after)} issues remanescentes (geram prompt no relatório)")
    print(f"[OK] Relatório HTML: {report_path}")
    print(f"[OK] Dados JSON: {json_path}")


if __name__ == "__main__":
    main()
