"""
RAG (Retrieval-Augmented Generation) for the Research Assistant.

Maintains an in-memory knowledge base of financial concepts (options strategies,
risk, forecasting, macro). At query time, retrieves the most relevant chunks and
prepends them to the LLM prompt so the model has domain context.

Architecture
------------
- Knowledge is stored as a list of (text, topic) tuples.
- Similarity is computed with TF-IDF cosine similarity (no external DB needed).
- If ``chromadb`` is installed, it is used instead for better semantic search.
- Custom documents can be added at runtime via ``add_document()``.
- The entire module is optional: if retrieval fails for any reason the callers
  fall back to the base prompt without RAG context.
"""

from __future__ import annotations

import re
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Built-in financial knowledge base
# ---------------------------------------------------------------------------

class _Chunk(NamedTuple):
    text: str
    topic: str


_KNOWLEDGE_BASE: list[_Chunk] = [
    # Options strategy definitions
    _Chunk(
        "A bull call spread (vertical spread call) buys a call at a lower strike "
        "and sells a call at a higher strike with the same expiry. Max profit is "
        "the difference in strikes minus the net premium paid. Max loss is limited "
        "to the net premium paid. Use when moderately bullish.",
        "options_strategy",
    ),
    _Chunk(
        "A bear put spread (vertical spread put) buys a put at a higher strike and "
        "sells a put at a lower strike with the same expiry. Profits when the "
        "underlying falls. Max profit = difference in strikes minus net debit. "
        "Max loss = net debit paid. Use when moderately bearish.",
        "options_strategy",
    ),
    _Chunk(
        "A straddle buys both a call and a put at the same strike and expiry. "
        "Profits from large price moves in either direction. Max loss is the total "
        "premium paid when the stock stays near the strike. Breakeven = strike ± "
        "total premium. Use when expecting high volatility but uncertain direction.",
        "options_strategy",
    ),
    _Chunk(
        "An iron condor sells an out-of-the-money put spread and an out-of-the-money "
        "call spread simultaneously. Four strikes: put_long < put_short < call_short < "
        "call_long. Profits when the underlying stays within a range. Max profit = "
        "net credit received. Max loss = width of either spread minus net credit. "
        "Probability of profit is high in low-volatility environments.",
        "options_strategy",
    ),
    _Chunk(
        "A calendar spread (time spread) sells a near-term option and buys a "
        "longer-term option at the same strike. Profits from time decay (theta) of "
        "the short leg and from implied volatility expanding. Risk: large move in "
        "either direction before expiry of the short leg.",
        "options_strategy",
    ),
    # Greeks
    _Chunk(
        "Delta measures how much an option's price changes per $1 move in the "
        "underlying. Calls have positive delta (0 to 1); puts have negative delta "
        "(-1 to 0). A delta of 0.5 means the option moves ~$0.50 per $1 of stock.",
        "greeks",
    ),
    _Chunk(
        "Theta is time decay: the daily dollar loss in option value as time passes, "
        "all else equal. Sellers benefit from positive theta; buyers lose theta. "
        "Theta accelerates in the final 30 days before expiry.",
        "greeks",
    ),
    _Chunk(
        "Vega measures sensitivity to implied volatility (IV). A long option has "
        "positive vega and gains when IV rises. A short option has negative vega. "
        "Vega risk is greatest for at-the-money options with longer time to expiry.",
        "greeks",
    ),
    _Chunk(
        "Implied volatility (IV) is the market's forecast of future price "
        "variability, extracted from option prices. High IV increases option "
        "premiums; IV crush after earnings often hurts long options buyers.",
        "volatility",
    ),
    # Risk concepts
    _Chunk(
        "Probability of profit (PoP) is the likelihood that a trade will expire "
        "with at least $0.01 profit. Iron condors and credit spreads aim for high "
        "PoP (>60%) at the cost of an unfavorable reward-to-risk ratio.",
        "risk",
    ),
    _Chunk(
        "Maximum loss for defined-risk strategies (spreads, iron condors) is capped "
        "at entry. For naked options or stock positions, losses can be unlimited. "
        "Always size positions so that max loss is a small fraction of portfolio.",
        "risk",
    ),
    _Chunk(
        "Expected value (EV) of a strategy is the probability-weighted average "
        "payoff. A positive EV strategy is theoretically profitable over many "
        "trials, but individual outcomes vary widely.",
        "risk",
    ),
    _Chunk(
        "Value at Risk (VaR) estimates the maximum loss over a given period at a "
        "given confidence level (e.g. 95%). A 5% 1-day VaR of $1,000 means there "
        "is a 5% chance of losing more than $1,000 in a single day.",
        "risk",
    ),
    _Chunk(
        "Maximum drawdown is the largest peak-to-trough decline in portfolio value "
        "over a period. It measures downside risk and capital preservation. "
        "Strategies with lower drawdowns are more robust to losing streaks.",
        "risk",
    ),
    # Forecasting concepts
    _Chunk(
        "ARIMA (AutoRegressive Integrated Moving Average) is a classical time-series "
        "model. It fits linear patterns from lagged values and moving averages. "
        "Order (p, d, q): p=AR lags, d=differencing, q=MA lags. Fast to train but "
        "assumes linear relationships and stationarity.",
        "forecasting",
    ),
    _Chunk(
        "Gradient Boosting (GB) uses an ensemble of decision trees to capture "
        "non-linear patterns. Trained on lagged price features. Generally more "
        "accurate than ARIMA for non-stationary financial series but slower to "
        "train and more prone to overfitting on short datasets.",
        "forecasting",
    ),
    _Chunk(
        "Directional accuracy measures how often a forecast predicts the correct "
        "sign of the price change (up/down). A 50% accuracy equals random; "
        "above 55% is generally considered informative for equities.",
        "forecasting",
    ),
    _Chunk(
        "A forecast horizon is the number of future time steps predicted. Short "
        "horizons (1–5 days) have lower uncertainty; longer horizons accumulate "
        "error. Uncertainty grows with horizon for most models.",
        "forecasting",
    ),
    # Macro / economic context
    _Chunk(
        "GDP (Gross Domestic Product) measures total economic output. Rising GDP "
        "generally correlates with rising equity markets and higher interest rates "
        "as the central bank may tighten policy.",
        "macro",
    ),
    _Chunk(
        "CPI (Consumer Price Index) measures inflation by tracking a basket of "
        "consumer goods. High CPI typically leads the Fed to raise rates, which "
        "pressures stock valuations and increases volatility.",
        "macro",
    ),
    _Chunk(
        "The VIX (CBOE Volatility Index) measures 30-day implied volatility of S&P "
        "500 options. A high VIX (>25) signals market fear and elevated option "
        "premiums. Traders use VIX to time premium-selling strategies.",
        "macro",
    ),
    _Chunk(
        "The unemployment rate measures the fraction of the labor force without "
        "jobs. Rising unemployment often precedes recessions and may lead the Fed "
        "to cut rates, which can be bullish for equities.",
        "macro",
    ),
    _Chunk(
        "The 10-year Treasury yield (DGS10) is a benchmark for risk-free rates. "
        "Rising yields increase the discount rate applied to stock valuations "
        "(hurting growth stocks) and raise the opportunity cost of options premiums.",
        "macro",
    ),
]

# Runtime additions from users or ingested documents
_CUSTOM_DOCS: list[_Chunk] = []


# ---------------------------------------------------------------------------
# TF-IDF similarity (no external deps)
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    """Simple word tokenizer: lowercase, strip punctuation."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _build_tfidf(chunks: list[str]) -> tuple[list[dict[str, float]], set[str]]:
    """Build TF-IDF vectors for a list of text chunks."""
    import math
    tokenized = [_tokenize(c) for c in chunks]
    vocab: set[str] = set()
    for tokens in tokenized:
        vocab.update(tokens)

    # Document frequency
    df: dict[str, int] = {}
    for tokens in tokenized:
        for tok in set(tokens):
            df[tok] = df.get(tok, 0) + 1

    n = len(tokenized)
    vectors: list[dict[str, float]] = []
    for tokens in tokenized:
        tf: dict[str, float] = {}
        for tok in tokens:
            tf[tok] = tf.get(tok, 0) + 1
        tfidf: dict[str, float] = {}
        for tok, count in tf.items():
            idf = math.log((n + 1) / (df.get(tok, 0) + 1)) + 1
            tfidf[tok] = (count / len(tokens)) * idf
        vectors.append(tfidf)
    return vectors, vocab


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    """Cosine similarity between two TF-IDF dicts."""
    dot = sum(a.get(k, 0.0) * v for k, v in b.items())
    norm_a = sum(v * v for v in a.values()) ** 0.5
    norm_b = sum(v * v for v in b.values()) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _retrieve_tfidf(query: str, chunks: list[_Chunk], top_k: int) -> list[str]:
    """Retrieve top_k chunks by TF-IDF cosine similarity."""
    texts = [c.text for c in chunks]
    vectors, _ = _build_tfidf(texts + [query])
    query_vec = vectors[-1]
    doc_vecs = vectors[:-1]
    scores = [(_cosine(doc_vecs[i], query_vec), i) for i in range(len(doc_vecs))]
    scores.sort(key=lambda x: -x[0])
    return [texts[i] for _, i in scores[:top_k] if scores[0][0] > 0]


# ---------------------------------------------------------------------------
# Optional: chromadb backend
# ---------------------------------------------------------------------------

_chroma_collection = None
_chroma_tried = False


def _get_chroma_collection():
    """Lazy-init chromadb in-process collection. Returns None if not available."""
    global _chroma_collection, _chroma_tried
    if _chroma_tried:
        return _chroma_collection
    _chroma_tried = True
    try:
        import chromadb  # type: ignore[import-untyped]  # optional dep
        client = chromadb.Client()
        col = client.get_or_create_collection("optionslab_knowledge")
        # Populate if empty
        if col.count() == 0:
            all_chunks = _KNOWLEDGE_BASE + _CUSTOM_DOCS
            col.add(
                documents=[c.text for c in all_chunks],
                metadatas=[{"topic": c.topic} for c in all_chunks],
                ids=[f"chunk_{i}" for i in range(len(all_chunks))],
            )
        _chroma_collection = col
    except Exception:
        _chroma_collection = None
    return _chroma_collection


def _retrieve_chroma(query: str, top_k: int) -> list[str]:
    """Retrieve using chromadb. Returns empty list on failure."""
    col = _get_chroma_collection()
    if col is None:
        return []
    try:
        result = col.query(query_texts=[query], n_results=top_k)
        return result["documents"][0] if result["documents"] else []
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def add_document(text: str, topic: str = "custom") -> None:
    """
    Add a custom document to the knowledge base at runtime.

    The document is included in future retrievals. If chromadb is available,
    it is also added to the chromadb collection.
    """
    chunk = _Chunk(text=text, topic=topic)
    _CUSTOM_DOCS.append(chunk)
    col = _get_chroma_collection()
    if col is not None:
        try:
            idx = col.count()
            col.add(
                documents=[text],
                metadatas=[{"topic": topic}],
                ids=[f"custom_{idx}"],
            )
        except Exception:
            pass


def retrieve(query: str, top_k: int = 3) -> list[str]:
    """
    Retrieve the top_k most relevant knowledge chunks for a query.

    Uses chromadb if available; otherwise falls back to TF-IDF cosine similarity.
    Returns an empty list if retrieval fails or no relevant chunks are found.
    """
    try:
        chroma_results = _retrieve_chroma(query, top_k)
        if chroma_results:
            return chroma_results
        all_chunks = _KNOWLEDGE_BASE + _CUSTOM_DOCS
        return _retrieve_tfidf(query, all_chunks, top_k)
    except Exception:
        return []


def build_rag_context(query: str, top_k: int = 3) -> str:
    """
    Return a formatted context string to prepend to an LLM prompt.

    Returns an empty string if no relevant chunks are found.
    """
    chunks = retrieve(query, top_k=top_k)
    if not chunks:
        return ""
    lines = ["Relevant financial context:"]
    for i, chunk in enumerate(chunks, 1):
        lines.append(f"{i}. {chunk}")
    return "\n".join(lines)
