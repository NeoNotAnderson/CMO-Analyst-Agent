"""
RAG Pipeline Logger

Writes structured logs for every query through the pipeline:
  - User query
  - LLM calls (which model, how many messages)
  - Tool calls (name + args)
  - Semantic search results (top chunks + scores)
  - Keyword search results (top chunks + BM25 scores)
  - RRF merged results
  - Final reranked results
  - Agent final answer

Log files are written to: backend/logs/rag_<date>.log
One query = one clearly delimited block.
"""

import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

# ── Log file location ──────────────────────────────────────────────────────────
_LOG_DIR = Path(__file__).resolve().parents[3] / "logs"
_LOG_DIR.mkdir(exist_ok=True)

def _get_log_path() -> Path:
    date_str = datetime.now().strftime("%Y-%m-%d")
    return _LOG_DIR / f"rag_{date_str}.log"


def _get_logger() -> logging.Logger:
    logger = logging.getLogger("rag_pipeline")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    handler = logging.FileHandler(_get_log_path(), encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    # Also mirror to console so existing print behaviour is preserved
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console)
    return logger


def _write(lines: list[str]) -> None:
    logger = _get_logger()
    for line in lines:
        logger.info(line)


# ── Public helpers ─────────────────────────────────────────────────────────────

def log_query_start(
    session_id: str,
    thread_id: str | None,
    user_query: str,
    prospectus_id: str | None,
    prospectus_name: str | None,
) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    _write([
        "",
        "=" * 80,
        f"RAG QUERY  [{ts}]",
        "=" * 80,
        f"SESSION       : {session_id}",
        f"THREAD        : {thread_id or 'none'}",
        f"PROSPECTUS    : {prospectus_name or 'none'} ({prospectus_id or 'none'})",
        f"USER QUERY    : {user_query}",
        "-" * 80,
    ])


def log_llm_call(step: str, model: str, n_messages: int, tool_calls: list[dict] | None) -> None:
    lines = [
        f"[LLM CALL] {step}",
        f"  model     : {model}",
        f"  messages  : {n_messages}",
    ]
    if tool_calls:
        lines.append(f"  tool_calls: {len(tool_calls)}")
        for tc in tool_calls:
            args_str = json.dumps(tc.get("args", {}), ensure_ascii=False)[:200]
            lines.append(f"    → {tc['name']}({args_str})")
    else:
        lines.append("  tool_calls: none  (direct response)")
    _write(lines)


def log_tool_call(tool_name: str, args: dict) -> None:
    args_str = json.dumps(args, ensure_ascii=False, indent=2)
    _write([
        f"[TOOL CALL] {tool_name}",
        f"  args: {args_str}",
    ])


def log_semantic_results(query: str, results: list[dict]) -> None:
    lines = [
        f"[SEMANTIC SEARCH]  query='{query}'  results={len(results)}",
    ]
    for r in results[:10]:
        meta = r.get("metadata", {})
        section = " > ".join(meta.get("section_path", [])) or "?"
        lines.append(
            f"  rank={r['rank']:2d}  score={r['similarity_score']:.4f}"
            f"  page={meta.get('page_num', '?'):>4}  [{section[:60]}]"
        )
        lines.append(f"    {r['chunk_text'][:120].replace(chr(10), ' ')}…")
    _write(lines)


def log_keyword_results(query: str, results: list[dict]) -> None:
    lines = [
        f"[KEYWORD SEARCH (BM25)]  query='{query}'  results={len(results)}",
    ]
    for r in results[:10]:
        meta = r.get("metadata", {})
        section = " > ".join(meta.get("section_path", [])) or "?"
        lines.append(
            f"  rank={r['rank']:2d}  bm25={r['bm25_score']:.4f}"
            f"  page={meta.get('page_num', '?'):>4}  [{section[:60]}]"
        )
        lines.append(f"    {r['chunk_text'][:120].replace(chr(10), ' ')}…")
    _write(lines)


def log_rrf_results(results: list[dict]) -> None:
    lines = [f"[RRF MERGE]  total unique chunks={len(results)}"]
    for i, r in enumerate(results[:10], 1):
        meta = r.get("metadata", {})
        section = " > ".join(meta.get("section_path", [])) or "?"
        lines.append(
            f"  #{i:2d}  rrf={r['rrf_score']:.6f}"
            f"  sem_rank={r['semantic_rank'] or '-':>3}"
            f"  kw_rank={r['keyword_rank'] or '-':>3}"
            f"  [{section[:55]}]"
        )
    _write(lines)


def log_rerank_results(query: str, results: list[dict]) -> None:
    lines = [
        f"[CROSS-ENCODER RERANK]  query='{query}'  final chunks={len(results)}",
    ]
    for i, r in enumerate(results, 1):
        meta = r.get("metadata", {})
        section = " > ".join(meta.get("section_path", [])) or "?"
        lines.append(
            f"  #{i:2d}  rerank={r.get('rerank_score', '?'):>8.4f}"
            f"  rrf={r.get('rrf_score', 0):.6f}"
            f"  page={meta.get('page_num', '?'):>4}"
            f"  [{section[:50]}]"
        )
        lines.append(f"    {r['chunk_text'][:150].replace(chr(10), ' ')}…")
    _write(lines)


def log_query_end(final_answer: str) -> None:
    _write([
        "-" * 80,
        "[FINAL ANSWER]",
        final_answer[:2000],
        "=" * 80,
    ])
