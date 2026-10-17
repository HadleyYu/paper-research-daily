"""Deterministic UTF-8 Markdown reports; analysis is supplied by the agent."""
from __future__ import annotations

from urllib.parse import quote
from datetime import datetime
from zoneinfo import ZoneInfo

SECTION_KEYS = ("abstract", "problem", "mechanism", "novelty", "evidence", "limitations",
                "relevance", "microexperiment", "reading")
ZH = ("作者原始摘要的中文转述", "研究问题与设定", "核心方法与必要公式", "相对已有工作的创新",
      "实质证据与原文位置", "具体局限与失败", "对研究主线的用途", "建议的可验证小实验／下一步", "阅读路线与复现入口")
EN = ("Author abstract, faithfully paraphrased", "Question and setting", "Method and necessary equations",
      "Novelty relative to prior work", "Evidence and original locations", "Limitations and failures",
      "Use for the research question", "Proposed test or next step", "Reading route and reproduction")


def _cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def _pdf_target(value):
    return value if value.startswith("file://") else quote(value)


def _content(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        if value and all(isinstance(v, dict) for v in value):
            keys = list(dict.fromkeys(k for row in value for k in row))
            return "| " + " | ".join(map(_cell, keys)) + " |\n| " + " | ".join("---" for _ in keys) + " |\n" + "\n".join("| " + " | ".join(_cell(row.get(k, "")) for k in keys) + " |" for row in value)
        return "\n".join("- " + _content(v) for v in value)
    if isinstance(value, dict):
        return "\n".join(f"- **{k}:** {_content(v)}" for k, v in value.items())
    return str(value or "")


def render_overview(date: str, papers: list[dict], profile: dict, updates=None) -> str:
    zh = profile.get("language", "zh-CN") == "zh-CN"
    labels = ZH if zh else EN
    heading = "研究文献日报" if zh else "Research paper daily"
    question = profile.get("project", {}).get("research_question", "")
    lines = [f"# {date} · {heading}", "", question, ""]
    zone = profile.get("timezone", "UTC")
    timestamp = datetime.now(ZoneInfo(zone)).isoformat(timespec="seconds")
    published = sum(p.get("category") == "published" for p in papers)
    new = sum(p.get("category") in {"new", "new_arxiv"} for p in papers)
    pdfs = sum(bool(p.get("pdf_file") or p.get("source_pdf")) for p in papers)
    lines += [f"{'生成时间' if zh else 'Generated'}: {timestamp} ({zone}). "
              f"{'论文' if zh else 'Papers'}: {len(papers)}; "
              f"{'正式发表' if zh else 'published'}: {published}; "
              f"{'近期新文' if zh else 'recent'}: {new}; PDF: {pdfs}.", ""]
    if updates is not None:
        from .watch import render_updates
        lines += [render_updates(updates, profile.get("language", "zh-CN")), "", "## 今日论文" if zh else "## Today's papers", ""]
    if papers:
        first = papers[0]
        lines += [f"**{'先读' if zh else 'Read first'}: {first['title']}** — {first.get('selection_reason', '')}", ""]
    lines += (["按阅读优先级排序。下文的建议实验与独立分析不属于作者已验证结论；外部链接仅提供出处，本地校验不代表已验证远程页面可访问。", ""] if zh else ["Ordered by reading priority. Proposed experiments and independent analysis are not author-validated findings. Local validation does not verify remote URL availability.", ""])
    lines += ["| # | " + ("论文 | 来源 / 日期 | 一句话价值 | 分数 | PDF / 入口 |" if zh else "Paper | Source / date | One-sentence value | Score | PDF / entry |"), "| --- | --- | --- | --- | --- | --- |"]
    for p in papers:
        score = p.get("score_total")
        source = p.get('venue') or p.get('category', '')
        paper_date = p.get('first_announced_date') or p.get('publication_date', '')
        entry = f"[PDF]({_pdf_target(p['pdf_file'])})" if p.get('pdf_file') else f"[{'入口' if zh else 'Entry'}]({p.get('official_url', '')})"
        lines.append(f"| {p['rank']:02d} | {_cell(p['title'])} | {_cell(source)} · {_cell(paper_date)} | {_cell(p.get('one_sentence', ''))} | {score if score is not None else 'pending'} | {entry} |")
    for p in papers:
        lines += ["", f"## {p['rank']:02d} · {p['title']}", "", "；".join(p.get("authors", [])), "",
                  f"{p.get('venue', '')} · {p.get('publication_status', '')} · {p.get('version', 'version not supplied')}", ""]
        links = []
        if p.get("pdf_file"):
            links.append(f"[PDF]({_pdf_target(p['pdf_file'])})")
        if p.get("doi"):
            links.append(f"[DOI](https://doi.org/{p['doi']})")
        if p.get("arxiv_id"):
            links.append(f"[arXiv](https://arxiv.org/abs/{p['arxiv_id']})")
        if p.get("official_url"):
            links.append(f"[{'官方入口' if zh else 'Official source'}]({p['official_url']})")
        lines += [" · ".join(links), ""]
        if not p.get("pdf_file"):
            lines += [f"{'PDF未下载' if zh else 'PDF unavailable'}: {p.get('download_reason', p.get('download_status', 'not supplied'))}", ""]
        if p.get("one_sentence"):
            lines += [f"**{'一句话定位' if zh else 'In one sentence'}：** {p['one_sentence']}", ""]
        if p.get("evidence_level") != "fulltext":
            lines += ["> " + ("仅摘要级阅读，质量评估待核验；未核实的方法、数字和复现结论不能视为全文证据。" if zh else "Abstract-only reading. Quality assessment is pending; unverified methods, numbers and reproduction claims are not full-text evidence."), ""]
        for key, label in zip(SECTION_KEYS, labels):
            value = p.get("sections", {}).get(key)
            lines += [f"### {label}", "", _content(value) if value else ("待全文核验。" if zh else "Pending full-text verification."), ""]
        lines += [f"### {'评分与排序理由' if zh else 'Score and ranking rationale'}", "",
                  f"{p.get('score_total') if p.get('score_total') is not None else 'pending'}/100 · " + ", ".join(f"{k} {v}" for k, v in p.get("score", {}).items()), "",
                  p.get("score_reason", ""), "", p.get("selection_reason", ""), ""]
        if p.get("fallback_reason"):
            lines += [f"{'补位说明' if zh else 'Quota fallback'}: {p['fallback_reason']}", ""]
        lines += [f"**{'核验来源' if zh else 'Verification sources'}**", ""]
        for source in p.get("sources", []):
            if isinstance(source, dict) and source.get("url"):
                lines.append(f"- [{source.get('role', 'source')}]({source['url']})")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
