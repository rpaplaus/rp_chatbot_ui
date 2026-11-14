"""
Query-aware passage selection for scraped web pages.

Instead of truncating a page to its first N characters (which often keeps only menus and
intros), the page is split into passages, ranked with BM25 against the search query and the
best passages are returned in their original order within a character budget.
"""
import math
import re
import unicodedata
from collections import Counter
from typing import List, Set

TABLE_START = "[TABELA EXTRAÍDA]"
TABLE_END = "[/TABELA EXTRAÍDA]"

_STOPWORDS: Set[str] = {
    "a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "em", "no", "na", "nos", "nas",
    "um", "uma", "para", "por", "com", "sem", "que", "qual", "quais", "como", "se", "ou", "ao",
    "the", "of", "and", "to", "in", "on", "for", "is", "are", "what", "how", "with", "by", "at",
}


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def tokenize(text: str) -> List[str]:
    return [t for t in re.findall(r"[a-z0-9][a-z0-9\-\.]*[a-z0-9]|[a-z0-9]", _normalize(text)) if t not in _STOPWORDS]


def split_passages(text: str, target_chars: int = 600) -> List[str]:
    """Groups consecutive lines into ~target_chars passages, keeping extracted tables intact."""
    passages: List[str] = []
    buffer: List[str] = []
    buffer_len = 0
    in_table = False

    def flush() -> None:
        nonlocal buffer, buffer_len
        if buffer:
            passages.append("\n".join(buffer))
        buffer, buffer_len = [], 0

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped == TABLE_START:
            flush()
            in_table = True
        buffer.append(stripped)
        buffer_len += len(stripped) + 1
        if stripped == TABLE_END:
            in_table = False
            flush()
        elif not in_table and buffer_len >= target_chars:
            flush()
    flush()
    return passages


def select_relevant_passages(text: str, query: str, max_chars: int, target_chars: int = 600) -> str:
    """
    Returns the most query-relevant passages of `text` (BM25), in original order, within `max_chars`.
    The first passage (page title/lead) is always kept for context. Falls back to the page head
    when the query has no usable terms or the page already fits the budget.
    """
    if not text:
        return ""
    if len(text) <= max_chars:
        return text

    query_terms = set(tokenize(query))
    passages = split_passages(text, target_chars)
    if not query_terms or len(passages) <= 1:
        return text[:max_chars]

    tokenized = [tokenize(p) for p in passages]
    n_docs = len(tokenized)
    avg_len = sum(len(t) for t in tokenized) / n_docs or 1.0
    doc_freq = Counter(term for toks in tokenized for term in set(toks) if term in query_terms)

    k1, b = 1.5, 0.75
    scores: List[float] = []
    for toks in tokenized:
        tf = Counter(toks)
        score = 0.0
        for term in query_terms:
            if tf[term] == 0:
                continue
            idf = math.log(1 + (n_docs - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
            score += idf * (tf[term] * (k1 + 1)) / (tf[term] + k1 * (1 - b + b * len(toks) / avg_len))
        scores.append(score)

    selected = {0}
    used = len(passages[0])
    for idx in sorted(range(n_docs), key=lambda i: scores[i], reverse=True):
        if scores[idx] <= 0:
            break
        if idx in selected:
            continue
        cost = len(passages[idx]) + 5
        if used + cost > max_chars:
            continue
        selected.add(idx)
        used += cost

    # Nothing matched the query: keep the page head as before.
    if len(selected) == 1:
        return text[:max_chars]

    output: List[str] = []
    previous = -1
    for idx in sorted(selected):
        if previous != -1 and idx != previous + 1:
            output.append("[...]")
        output.append(passages[idx])
        previous = idx
    return "\n".join(output)[:max_chars]
