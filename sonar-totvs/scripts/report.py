"""
report.py — Gera o relatório HTML com dashboard visual.
"""

import html
import json
from pathlib import Path


def _escape(s) -> str:
    if s is None:
        return ""
    return html.escape(str(s))


def _score_color(score: float) -> str:
    if score >= 80:
        return "var(--c-success)"
    if score >= 50:
        return "var(--c-warn)"
    return "var(--c-danger)"


def render_report(payload: dict, skill_dir: Path) -> str:
    """payload é o dict gerado pelo analyzer (kind=analysis) ou fixer (kind=fix)."""
    is_fix = payload.get("kind") == "fix"

    # ---------- Dados ----------
    timestamp_raw = payload.get("timestamp", "")
    # YYYYMMDD_HHMMSS → YYYY-MM-DD HH:MM:SS
    pretty_ts = timestamp_raw
    if len(timestamp_raw) == 15:
        pretty_ts = f"{timestamp_raw[0:4]}-{timestamp_raw[4:6]}-{timestamp_raw[6:8]} {timestamp_raw[9:11]}:{timestamp_raw[11:13]}:{timestamp_raw[13:15]}"

    scores = payload.get("scores", {})
    counts = payload.get("counts", {})
    issues = payload.get("issues", [])

    # Para o modo fix, scores são "before" e "after"
    if is_fix:
        scores_before = payload.get("scores_before", {})
        scores_after = payload.get("scores_after", {})
        fixed_count = payload.get("fixed_count", 0)
        unfixed_count = payload.get("unfixed_count", 0)
    else:
        scores_before = scores_after = {}
        fixed_count = unfixed_count = 0

    # ---------- Sidebar: contagem por regra ----------
    rule_counts = {}
    for i in issues:
        code = i["rule_code"]
        rule_counts.setdefault(code, {"title": i["rule_title"], "severity": i["severity"], "count": 0})
        rule_counts[code]["count"] += 1
    rules_list = sorted(rule_counts.items(), key=lambda x: (-x[1]["count"], x[0]))

    # ---------- Issues como JSON para o front ----------
    issues_json = json.dumps(issues, ensure_ascii=False)

    project_path = _escape(payload.get("project", ""))
    files_analyzed = payload.get("files_analyzed", 0)

    title_main = "Relatório de Correção" if is_fix else "Análise de Conformidade"
    subtitle = "Sonar TOTVS"

    # ---------- HTML ----------
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sonar TOTVS — {pretty_ts}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {{
  --c-bg: #0e1116;
  --c-bg-2: #161b22;
  --c-bg-3: #1c232c;
  --c-border: #2a323d;
  --c-text: #e6edf3;
  --c-text-dim: #8b949e;
  --c-text-faint: #6e7681;
  --c-accent: #ff6b35;        /* accent */
  --c-accent-2: #ffaa00;
  --c-success: #3fb950;
  --c-warn: #d29922;
  --c-danger: #f85149;
  --c-bug: #f85149;
  --c-smell: #d29922;
  --c-vuln: #a371f7;
  --shadow-card: 0 1px 3px rgba(0,0,0,.4), 0 8px 24px rgba(0,0,0,.2);
  --radius: 10px;
  --radius-sm: 6px;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: 'Space Grotesk', system-ui, sans-serif;
  background: var(--c-bg);
  color: var(--c-text);
  line-height: 1.55;
  font-size: 14px;
  min-height: 100vh;
}}
.app {{
  display: grid;
  grid-template-columns: 280px 1fr;
  min-height: 100vh;
}}
/* ---------- SIDEBAR ---------- */
aside {{
  background: var(--c-bg-2);
  border-right: 1px solid var(--c-border);
  padding: 24px 20px;
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
}}
.brand {{
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 28px;
}}
.brand-mark {{
  width: 36px; height: 36px;
  background: linear-gradient(135deg, var(--c-accent), var(--c-accent-2));
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 18px; color: #fff;
}}
.brand-text strong {{ display: block; font-size: 15px; letter-spacing: -.02em; }}
.brand-text span {{ font-size: 11px; color: var(--c-text-faint); text-transform: uppercase; letter-spacing: .08em; }}

.side-section {{ margin-bottom: 24px; }}
.side-section h3 {{
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: .1em;
  color: var(--c-text-faint);
  margin-bottom: 10px;
  font-weight: 600;
}}
.meta-item {{
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  font-size: 13px;
  border-bottom: 1px dashed var(--c-border);
}}
.meta-item:last-child {{ border-bottom: none; }}
.meta-item span:first-child {{ color: var(--c-text-dim); }}
.meta-item span:last-child {{ font-family: 'JetBrains Mono', monospace; font-size: 12px; }}

.rule-list {{ display: flex; flex-direction: column; gap: 2px; }}
.rule-pill {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 7px 10px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  cursor: pointer;
  transition: background .12s;
  border-left: 3px solid transparent;
}}
.rule-pill:hover {{ background: var(--c-bg-3); }}
.rule-pill.active {{ background: var(--c-bg-3); border-left-color: var(--c-accent); }}
.rule-pill .code {{ font-family: 'JetBrains Mono', monospace; font-weight: 500; }}
.rule-pill .count {{
  background: var(--c-bg-3);
  padding: 2px 8px;
  border-radius: 10px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 500;
}}
.rule-pill[data-sev="BUG"] .code {{ color: var(--c-bug); }}
.rule-pill[data-sev="CODE_SMELL"] .code {{ color: var(--c-smell); }}
.rule-pill[data-sev="VULNERABILIDADE"] .code {{ color: var(--c-vuln); }}

/* ---------- MAIN ---------- */
main {{ padding: 32px 40px 80px; max-width: 1400px; }}

header.page-head {{
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 36px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--c-border);
}}
header.page-head h1 {{
  font-size: 32px;
  font-weight: 600;
  letter-spacing: -.025em;
  margin-bottom: 6px;
}}
header.page-head .sub {{ color: var(--c-text-dim); font-size: 14px; }}
header.page-head .timestamp {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: var(--c-text-faint);
}}

/* ---------- SCORE CARDS ---------- */
.score-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
  margin-bottom: 32px;
}}
.score-card {{
  background: var(--c-bg-2);
  border: 1px solid var(--c-border);
  border-radius: var(--radius);
  padding: 20px 22px;
  position: relative;
  overflow: hidden;
}}
.score-card .label {{
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: .1em;
  color: var(--c-text-faint);
  font-weight: 600;
}}
.score-card .value {{
  font-size: 42px;
  font-weight: 600;
  letter-spacing: -.03em;
  margin-top: 8px;
  font-family: 'Space Grotesk', sans-serif;
}}
.score-card .value .pct {{ font-size: 22px; color: var(--c-text-dim); margin-left: 2px; }}
.score-card .desc {{ color: var(--c-text-dim); font-size: 12px; margin-top: 4px; }}
.score-card .bar {{
  height: 4px;
  background: var(--c-bg-3);
  border-radius: 2px;
  margin-top: 14px;
  overflow: hidden;
}}
.score-card .bar > div {{ height: 100%; border-radius: 2px; transition: width .6s; }}

.cat-card {{
  background: var(--c-bg-2);
  border: 1px solid var(--c-border);
  border-left-width: 4px;
  border-radius: var(--radius);
  padding: 18px 20px;
  display: flex; align-items: center; justify-content: space-between;
}}
.cat-card.bug {{ border-left-color: var(--c-bug); }}
.cat-card.smell {{ border-left-color: var(--c-smell); }}
.cat-card.vuln {{ border-left-color: var(--c-vuln); }}
.cat-card .info .label {{
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: .1em;
  color: var(--c-text-faint);
  font-weight: 600;
}}
.cat-card .info .name {{ font-size: 18px; font-weight: 600; margin-top: 2px; }}
.cat-card .num {{
  font-size: 36px;
  font-weight: 600;
  font-family: 'Space Grotesk', sans-serif;
  letter-spacing: -.03em;
}}
.cat-card.bug .num {{ color: var(--c-bug); }}
.cat-card.smell .num {{ color: var(--c-smell); }}
.cat-card.vuln .num {{ color: var(--c-vuln); }}

/* ---------- FILTERS ---------- */
.filters {{
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin-bottom: 16px;
  padding: 14px 16px;
  background: var(--c-bg-2);
  border: 1px solid var(--c-border);
  border-radius: var(--radius);
}}
.filter-group {{ display: flex; align-items: center; gap: 6px; }}
.filter-group label {{ font-size: 12px; color: var(--c-text-dim); }}
.chip {{
  padding: 5px 12px;
  border-radius: 16px;
  border: 1px solid var(--c-border);
  background: var(--c-bg-3);
  color: var(--c-text-dim);
  font-size: 12px;
  cursor: pointer;
  transition: all .12s;
  user-select: none;
}}
.chip:hover {{ color: var(--c-text); }}
.chip.active {{
  background: var(--c-text);
  color: var(--c-bg);
  border-color: var(--c-text);
}}
.chip[data-sev="BUG"].active {{ background: var(--c-bug); border-color: var(--c-bug); color: #fff; }}
.chip[data-sev="CODE_SMELL"].active {{ background: var(--c-smell); border-color: var(--c-smell); color: #fff; }}
.chip[data-sev="VULNERABILIDADE"].active {{ background: var(--c-vuln); border-color: var(--c-vuln); color: #fff; }}

input.search {{
  flex: 1;
  min-width: 200px;
  background: var(--c-bg-3);
  border: 1px solid var(--c-border);
  color: var(--c-text);
  padding: 7px 12px;
  border-radius: var(--radius-sm);
  font-family: inherit;
  font-size: 13px;
}}
input.search:focus {{ outline: 1px solid var(--c-accent); border-color: var(--c-accent); }}

.results-meta {{
  font-size: 12px;
  color: var(--c-text-dim);
  margin-bottom: 12px;
  font-family: 'JetBrains Mono', monospace;
}}

/* ---------- ISSUE CARDS ---------- */
.issue {{
  background: var(--c-bg-2);
  border: 1px solid var(--c-border);
  border-radius: var(--radius);
  margin-bottom: 10px;
  overflow: hidden;
  transition: border-color .12s;
}}
.issue:hover {{ border-color: var(--c-border); }}
.issue-head {{
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 18px;
  cursor: pointer;
  user-select: none;
}}
.issue-head:hover {{ background: var(--c-bg-3); }}
.sev-badge {{
  font-size: 10px;
  padding: 3px 9px;
  border-radius: 4px;
  text-transform: uppercase;
  letter-spacing: .08em;
  font-weight: 700;
  font-family: 'JetBrains Mono', monospace;
}}
.sev-badge.BUG {{ background: rgba(248,81,73,.15); color: var(--c-bug); }}
.sev-badge.CODE_SMELL {{ background: rgba(210,153,34,.15); color: var(--c-smell); }}
.sev-badge.VULNERABILIDADE {{ background: rgba(163,113,247,.15); color: var(--c-vuln); }}

.ai-badge {{
  font-size: 10px;
  padding: 3px 8px;
  border-radius: 4px;
  font-weight: 600;
  letter-spacing: .03em;
  border: 1px solid transparent;
}}
.ai-badge.confirmed {{ background: rgba(63,185,80,.15); color: var(--c-success); border-color: rgba(63,185,80,.3); }}
.ai-badge.rejected  {{ background: rgba(110,118,129,.15); color: var(--c-text-faint); border-color: rgba(110,118,129,.3); }}
.ai-badge.pending   {{ background: rgba(56,139,253,.15); color: #58a6ff; border-color: rgba(56,139,253,.3); }}
.ai-badge.ai-new    {{ background: rgba(255,107,53,.15); color: var(--c-accent); border-color: rgba(255,107,53,.3); }}

.issue.rejected {{ opacity: .55; }}
.issue.rejected:hover {{ opacity: 1; }}
.issue.rejected .issue-title {{ text-decoration: line-through; }}

.ai-reasoning {{
  background: rgba(56,139,253,.08);
  border-left: 3px solid #58a6ff;
  padding: 10px 14px;
  font-size: 13px;
  color: var(--c-text-dim);
  border-radius: 4px;
  font-style: italic;
}}
.conf-dot {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  color: var(--c-text-faint);
  margin-left: 6px;
  letter-spacing: 2px;
}}

.rule-code {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: var(--c-text-dim);
  padding: 2px 6px;
  background: var(--c-bg-3);
  border-radius: 4px;
}}
.issue-title {{
  flex: 1;
  font-size: 14px;
  font-weight: 500;
}}
.issue-loc {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: var(--c-text-dim);
}}
.toggle {{
  color: var(--c-text-faint);
  transition: transform .2s;
  font-size: 12px;
}}
.issue.open .toggle {{ transform: rotate(90deg); }}

.issue-body {{
  display: none;
  padding: 0 18px 18px;
  border-top: 1px solid var(--c-border);
}}
.issue.open .issue-body {{ display: block; }}

.issue-body h4 {{
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: .1em;
  color: var(--c-text-faint);
  margin-top: 16px;
  margin-bottom: 8px;
  font-weight: 600;
}}
.issue-body p {{ color: var(--c-text-dim); font-size: 13px; }}

pre.code {{
  background: #0a0d12;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm);
  padding: 14px 16px;
  overflow-x: auto;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12.5px;
  line-height: 1.6;
  color: #c9d1d9;
}}
pre.code .marker {{ color: var(--c-accent); font-weight: 700; }}

.prompt-box {{
  background: #0a0d12;
  border: 1px solid var(--c-border);
  border-left: 3px solid var(--c-accent);
  border-radius: var(--radius-sm);
  padding: 14px 16px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12.5px;
  line-height: 1.7;
  white-space: pre-wrap;
  color: #c9d1d9;
  position: relative;
}}
.copy-btn {{
  position: absolute;
  top: 10px;
  right: 10px;
  background: var(--c-bg-3);
  border: 1px solid var(--c-border);
  color: var(--c-text);
  padding: 5px 12px;
  border-radius: 4px;
  font-size: 11px;
  cursor: pointer;
  font-family: inherit;
  transition: all .12s;
}}
.copy-btn:hover {{ background: var(--c-accent); color: #fff; border-color: var(--c-accent); }}
.copy-btn.copied {{ background: var(--c-success); color: #fff; border-color: var(--c-success); }}

.empty {{
  text-align: center;
  padding: 60px 20px;
  color: var(--c-text-dim);
}}
.empty h3 {{ font-size: 24px; margin-bottom: 8px; color: var(--c-text); }}

/* fix mode */
.fix-banner {{
  background: linear-gradient(90deg, rgba(63,185,80,.15), transparent);
  border: 1px solid var(--c-success);
  border-left-width: 4px;
  padding: 16px 20px;
  border-radius: var(--radius);
  margin-bottom: 24px;
}}
.fix-banner strong {{ color: var(--c-success); }}

@media (max-width: 900px) {{
  .app {{ grid-template-columns: 1fr; }}
  aside {{ position: static; height: auto; }}
  main {{ padding: 24px 18px; }}
}}
</style>
</head>
<body>
<div class="app">
  <aside>
    <div class="brand">
      <div class="brand-mark">S</div>
      <div class="brand-text">
        <strong>Sonar TOTVS</strong>
        <span>Análise AdvPL/TLPP</span>
      </div>
    </div>

    <div class="side-section">
      <h3>Análise</h3>
      <div class="meta-item"><span>Arquivos</span><span>{files_analyzed}</span></div>
      <div class="meta-item"><span>Issues</span><span>{counts.get('total', 0)}</span></div>
      <div class="meta-item"><span>Bugs</span><span style="color:var(--c-bug)">{counts.get('bugs', 0)}</span></div>
      <div class="meta-item"><span>Smells</span><span style="color:var(--c-smell)">{counts.get('code_smells', 0)}</span></div>
      <div class="meta-item"><span>Vulnerab.</span><span style="color:var(--c-vuln)">{counts.get('vulnerabilidades', 0)}</span></div>
    </div>

    <div class="side-section">
      <h3>Regras Acionadas</h3>
      <div class="rule-list">
        {''.join(_rule_pill(code, info) for code, info in rules_list) if rules_list else '<p style="color:var(--c-text-faint);font-size:12px">Nenhuma 🎉</p>'}
      </div>
    </div>
  </aside>

  <main>
    <header class="page-head">
      <div>
        <h1>{title_main}</h1>
        <div class="sub">{subtitle} · <code style="color:var(--c-text)">{project_path}</code></div>
      </div>
      <div class="timestamp">{pretty_ts}</div>
    </header>

    {_fix_banner(payload) if is_fix else ''}

    <section class="score-grid">
      {_score_section(scores, scores_before, scores_after, is_fix)}
    </section>

    <section class="score-grid">
      <div class="cat-card bug">
        <div class="info"><div class="label">Severidade</div><div class="name">Bugs</div></div>
        <div class="num">{counts.get('bugs', 0)}</div>
      </div>
      <div class="cat-card smell">
        <div class="info"><div class="label">Severidade</div><div class="name">Code Smells</div></div>
        <div class="num">{counts.get('code_smells', 0)}</div>
      </div>
      <div class="cat-card vuln">
        <div class="info"><div class="label">Severidade</div><div class="name">Vulnerabilidades</div></div>
        <div class="num">{counts.get('vulnerabilidades', 0)}</div>
      </div>
    </section>

    <div class="filters">
      <div class="filter-group">
        <label>Severidade:</label>
        <span class="chip active" data-filter-sev="all">Todas</span>
        <span class="chip" data-filter-sev="BUG" data-sev="BUG">Bugs</span>
        <span class="chip" data-filter-sev="CODE_SMELL" data-sev="CODE_SMELL">Smells</span>
        <span class="chip" data-filter-sev="VULNERABILIDADE" data-sev="VULNERABILIDADE">Vulnerab.</span>
      </div>
      <div class="filter-group">
        <span class="chip" id="toggle-rejected">Mostrar rejeitadas pela IA</span>
      </div>
      <input class="search" placeholder="Buscar arquivo, regra ou trecho de código…">
    </div>

    <div class="results-meta" id="results-meta"></div>

    <section id="issues"></section>
  </main>
</div>

<script>
const ISSUES = {issues_json};
const state = {{
  sev: 'all',
  rule: null,
  q: '',
  showRejected: false,
}};

function escapeHtml(s) {{
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}}

function renderIssue(issue, idx) {{
  const snippetHtml = escapeHtml(issue.snippet).replace(/^&gt;&gt; /gm, '<span class="marker">&gt;&gt;</span> ');

  // Badge da IA + classe extra
  let aiBadge = '';
  let extraClass = '';
  if (issue.ai_status === 'confirmed') {{
    aiBadge = '<span class="ai-badge confirmed" title="Confirmada pela IA">🤖 IA confirmou</span>';
  }} else if (issue.ai_status === 'rejected') {{
    aiBadge = '<span class="ai-badge rejected" title="IA descartou como falso positivo">🤖 IA descartou</span>';
    extraClass = 'rejected';
  }} else if (issue.ai_status === 'pending') {{
    aiBadge = '<span class="ai-badge pending" title="Aguardando revisão IA">🤖 pendente</span>';
  }} else if (issue.origin === 'ai') {{
    aiBadge = '<span class="ai-badge ai-new" title="Encontrada pela IA (não pelo regex)">🤖 IA detectou</span>';
  }}

  // Bloco de raciocínio da IA, se houver
  let aiBlock = '';
  if (issue.ai_reasoning) {{
    const confIcon = issue.ai_confidence === 'high' ? '●●●' :
                     issue.ai_confidence === 'medium' ? '●●○' : '●○○';
    aiBlock = `
      <h4>Análise da IA <span class="conf-dot">${{confIcon}}</span></h4>
      <div class="ai-reasoning">${{escapeHtml(issue.ai_reasoning)}}</div>`;
  }}

  return `
  <div class="issue ${{extraClass}}" data-sev="${{issue.severity}}" data-rule="${{issue.rule_code}}" data-ai-status="${{issue.ai_status || ''}}">
    <div class="issue-head" onclick="this.parentElement.classList.toggle('open')">
      <span class="sev-badge ${{issue.severity}}">${{issue.severity.replace('_',' ')}}</span>
      <span class="rule-code">${{escapeHtml(issue.rule_code)}}</span>
      <span class="issue-title">${{escapeHtml(issue.rule_title)}}</span>
      ${{aiBadge}}
      <span class="issue-loc">${{escapeHtml(issue.file)}}:${{issue.line}}</span>
      <span class="toggle">▶</span>
    </div>
    <div class="issue-body">
      ${{aiBlock}}
      <h4>Trecho do código</h4>
      <pre class="code">${{snippetHtml}}</pre>
      <h4>Match detectado</h4>
      <pre class="code">${{escapeHtml(issue.matched_text)}}</pre>
      <h4>Prompt para correção via Claude</h4>
      <div class="prompt-box">
        <button class="copy-btn" data-idx="${{idx}}" onclick="copyPrompt(event, ${{idx}})">Copiar</button>
${{escapeHtml(issue.fix_prompt)}}
      </div>
    </div>
  </div>`;
}}

function copyPrompt(e, idx) {{
  e.stopPropagation();
  const text = ISSUES[idx].fix_prompt;
  navigator.clipboard.writeText(text).then(() => {{
    const btn = e.target;
    btn.classList.add('copied');
    btn.textContent = '✓ Copiado';
    setTimeout(() => {{ btn.classList.remove('copied'); btn.textContent = 'Copiar'; }}, 1500);
  }});
}}

function applyFilters() {{
  const container = document.getElementById('issues');
  const q = state.q.toLowerCase();
  const filtered = ISSUES.map((iss, idx) => ({{iss, idx}})).filter(({{iss}}) => {{
    if (!state.showRejected && iss.ai_status === 'rejected') return false;
    if (state.sev !== 'all' && iss.severity !== state.sev) return false;
    if (state.rule && iss.rule_code !== state.rule) return false;
    if (q) {{
      const hay = `${{iss.rule_code}} ${{iss.rule_title}} ${{iss.file}} ${{iss.snippet}} ${{iss.matched_text}}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }}
    return true;
  }});

  const rejectedCount = ISSUES.filter(i => i.ai_status === 'rejected').length;
  const rejectedLabel = rejectedCount > 0 && !state.showRejected
    ? ` · ${{rejectedCount}} rejeitada(s) pela IA ocultas`
    : '';
  document.getElementById('results-meta').textContent =
    `Mostrando ${{filtered.length}} de ${{ISSUES.length}} issues${{state.rule ? ' · regra ' + state.rule : ''}}${{rejectedLabel}}`;

  if (filtered.length === 0) {{
    container.innerHTML = '<div class="empty"><h3>Nada por aqui</h3><p>Nenhuma issue corresponde aos filtros aplicados.</p></div>';
  }} else {{
    container.innerHTML = filtered.map(({{iss, idx}}) => renderIssue(iss, idx)).join('');
  }}
}}

// Filtros de severidade
document.querySelectorAll('[data-filter-sev]').forEach(chip => {{
  chip.addEventListener('click', () => {{
    document.querySelectorAll('[data-filter-sev]').forEach(c => c.classList.remove('active'));
    chip.classList.add('active');
    state.sev = chip.dataset.filterSev;
    applyFilters();
  }});
}});

// Filtros de regra (sidebar)
document.querySelectorAll('.rule-pill').forEach(pill => {{
  pill.addEventListener('click', () => {{
    const code = pill.dataset.code;
    if (state.rule === code) {{
      state.rule = null;
      pill.classList.remove('active');
    }} else {{
      document.querySelectorAll('.rule-pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      state.rule = code;
    }}
    applyFilters();
  }});
}});

// Busca
document.querySelector('input.search').addEventListener('input', (e) => {{
  state.q = e.target.value;
  applyFilters();
}});

// Toggle issues rejeitadas pela IA
const toggleRejBtn = document.getElementById('toggle-rejected');
if (toggleRejBtn) {{
  // Esconde o botão se não há rejeitadas
  const hasRejected = ISSUES.some(i => i.ai_status === 'rejected');
  if (!hasRejected) {{
    toggleRejBtn.style.display = 'none';
  }} else {{
    toggleRejBtn.addEventListener('click', () => {{
      state.showRejected = !state.showRejected;
      toggleRejBtn.classList.toggle('active', state.showRejected);
      toggleRejBtn.textContent = state.showRejected ? 'Ocultar rejeitadas pela IA' : 'Mostrar rejeitadas pela IA';
      applyFilters();
    }});
  }}
}}

applyFilters();
</script>
</body>
</html>"""


def _rule_pill(code: str, info: dict) -> str:
    return (
        f'<div class="rule-pill" data-sev="{_escape(info["severity"])}" data-code="{_escape(code)}">'
        f'<span class="code">{_escape(code)}</span>'
        f'<span class="count">{info["count"]}</span>'
        f'</div>'
    )


def _score_section(scores: dict, scores_before: dict, scores_after: dict, is_fix: bool) -> str:
    if is_fix and scores_after:
        s_after = scores_after
        s_before = scores_before
        delta_simple = round(s_after.get("simple", 0) - s_before.get("simple", 0), 2)
        delta_weighted = round(s_after.get("weighted", 0) - s_before.get("weighted", 0), 2)
        return f"""
        <div class="score-card">
          <div class="label">Score simples · após</div>
          <div class="value" style="color:{_score_color(s_after.get('simple', 0))}">{s_after.get('simple', 0)}<span class="pct">%</span></div>
          <div class="desc">era {s_before.get('simple', 0)}% (Δ {('+' if delta_simple >= 0 else '')}{delta_simple})</div>
          <div class="bar"><div style="width:{s_after.get('simple', 0)}%;background:{_score_color(s_after.get('simple', 0))}"></div></div>
        </div>
        <div class="score-card">
          <div class="label">Score ponderado · após</div>
          <div class="value" style="color:{_score_color(s_after.get('weighted', 0))}">{s_after.get('weighted', 0)}<span class="pct">%</span></div>
          <div class="desc">era {s_before.get('weighted', 0)}% (Δ {('+' if delta_weighted >= 0 else '')}{delta_weighted})</div>
          <div class="bar"><div style="width:{s_after.get('weighted', 0)}%;background:{_score_color(s_after.get('weighted', 0))}"></div></div>
        </div>
        <div class="score-card">
          <div class="label">Arquivos limpos</div>
          <div class="value">{s_after.get('files_clean', 0)}<span class="pct">/{s_after.get('files_total', 0)}</span></div>
          <div class="desc">arquivos sem nenhuma issue</div>
        </div>"""
    else:
        s = scores
        return f"""
        <div class="score-card">
          <div class="label">Score simples</div>
          <div class="value" style="color:{_score_color(s.get('simple', 0))}">{s.get('simple', 0)}<span class="pct">%</span></div>
          <div class="desc">% de arquivos sem nenhuma issue</div>
          <div class="bar"><div style="width:{s.get('simple', 0)}%;background:{_score_color(s.get('simple', 0))}"></div></div>
        </div>
        <div class="score-card">
          <div class="label">Score ponderado</div>
          <div class="value" style="color:{_score_color(s.get('weighted', 0))}">{s.get('weighted', 0)}<span class="pct">%</span></div>
          <div class="desc">Bug=3 · Vulnerab.=5 · Smell=1</div>
          <div class="bar"><div style="width:{s.get('weighted', 0)}%;background:{_score_color(s.get('weighted', 0))}"></div></div>
        </div>
        <div class="score-card">
          <div class="label">Arquivos limpos</div>
          <div class="value">{s.get('files_clean', 0)}<span class="pct">/{s.get('files_total', 0)}</span></div>
          <div class="desc">arquivos sem nenhuma issue</div>
        </div>"""


def _fix_banner(payload: dict) -> str:
    return f"""
    <div class="fix-banner">
      <strong>Correção aplicada</strong> · {payload.get('fixed_count', 0)} issues corrigidas automaticamente
      &nbsp;·&nbsp; {payload.get('unfixed_count', 0)} issues remanescentes (geram prompt para correção manual)
    </div>
    """
