"""Text similarity utilities used for duplicate detection, contradiction
detection and lexical semantic search. Pure Python, deterministic, offline."""
from __future__ import annotations

import math
import re
from collections import Counter

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "can", "de", "en", "for",
    "from", "has", "had", "he", "her", "his", "in", "into", "is", "it", "its", "la",
    "le", "lo", "me", "no", "not", "of", "on", "or", "our", "she", "so", "the", "to",
    "us", "we", "were", "will", "with", "would", "that", "this", "these", "those",
    "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "may", "might", "must", "shall", "should", "could", "just", "also", "than", "then",
}

_PUNCT_RE = re.compile(r"[^0-9a-zA-Z\s]+")
_WS_RE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    return _WS_RE.sub(" ", _PUNCT_RE.sub(" ", (text or "").lower())).strip()


def tokens(text: str) -> list[str]:
    t = normalize(text)
    if not t:
        return []
    return [w for w in t.split(" ") if w not in _STOPWORDS and len(w) > 1]


def token_set(text: str) -> frozenset[str]:
    return frozenset(tokens(text))


def jaccard(a: str, b: str) -> float:
    """Jaccard similarity over content-token sets. Used for duplicate
    detection; deterministic and explainable."""
    sa, sb = token_set(a), token_set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def cosine(v1: dict[str, float], v2: dict[str, float]) -> float:
    common = set(v1) & set(v2)
    num = sum(v1[k] * v2[k] for k in common)
    d1 = math.sqrt(sum(x * x for x in v1.values()))
    d2 = math.sqrt(sum(x * x for x in v2.values()))
    if d1 == 0 or d2 == 0:
        return 0.0
    return num / (d1 * d2)


def tfidf_vectorize(documents: list[str]) -> list[dict[str, float]]:
    """Return one TF-IDF vector (dict term->weight) per document.

    TF = term frequency in the document (sublinear: 1+log).
    IDF = log((N+1)/(df+1)) + 1  (smoothed).
    """
    n = len(documents)
    df: Counter[str] = Counter()
    tfs: list[Counter[str]] = []
    for doc in documents:
        tf = Counter(tokens(doc))
        tfs.append(tf)
        for term in tf:
            df[term] += 1
    idf = {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}
    vectors = []
    for tf in tfs:
        if not tf:
            vectors.append({})
            continue
        vec = {t: (1.0 + math.log(c)) * idf[t] for t, c in tf.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        vectors.append({t: v / norm for t, v in vec.items()})
    return vectors
