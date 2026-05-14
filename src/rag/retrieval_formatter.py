"""Standardized formatting layer for LangChain retrieval outputs."""

from __future__ import annotations

from typing import Dict, List


def _sanitize_text(text: str) -> str:
    return " ".join(text.split())


def _format_candidate_line(item: Dict) -> str:
    rank = int(item.get("rank", 0))
    source = str(item.get("source", "unknown")).strip() or "unknown"
    score = item.get("score")
    similarity = item.get("similarity")
    matched = bool(item.get("matched", False))
    fallback = bool(item.get("fallback", False))

    score_text = f"{float(score):.6f}" if isinstance(score, (int, float)) else "N/A"
    similarity_text = (
        f"{float(similarity):.6f}" if isinstance(similarity, (int, float)) else "N/A"
    )
    return (
        f"- rank: {rank}; source: {source}; score: {score_text}; "
        f"similarity: {similarity_text}; matched: {str(matched).lower()}; "
        f"fallback: {str(fallback).lower()}"
    )


def format_retrieved_context(
    *,
    query: str,
    candidates: List[Dict],
    selected: List[Dict],
    min_similarity: float,
) -> str:
    """Format retrieval results into a strict structured block for prompt injection."""
    if not selected:
        return ""

    lines: List[str] = []
    lines.append("\n\n【RAG_RETRIEVAL_BLOCK_START】")
    lines.append(f"query: {_sanitize_text(str(query))}")
    lines.append(f"min_similarity: {float(min_similarity):.6f}")
    lines.append(f"candidate_count: {len(candidates)}")
    lines.append(f"matched_count: {len(selected)}")

    lines.append("candidates:")
    if candidates:
        for item in candidates:
            lines.append(_format_candidate_line(item))
    else:
        lines.append("- none")

    lines.append("selected_context:")
    for item in selected:
        text = _sanitize_text(str(item.get("text", "")))
        if not text:
            continue
        lines.append(_format_candidate_line(item))
        lines.append(f"  content: {text}")

    lines.append("【RAG_RETRIEVAL_BLOCK_END】")
    lines.append("")

    return "\n".join(lines)
