"""Tests for the RAG (Retrieval-Augmented Generation) knowledge base."""

from research_assistant.rag import (
    _KNOWLEDGE_BASE,
    _CUSTOM_DOCS,
    _tokenize,
    _cosine,
    _retrieve_tfidf,
    _Chunk,
    add_document,
    retrieve,
    build_rag_context,
)


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

def test_tokenize_lowercases_and_strips_punctuation() -> None:
    tokens = _tokenize("Hello, World! Options.")
    assert "hello" in tokens
    assert "world" in tokens
    assert "options" in tokens
    assert "," not in tokens


def test_tokenize_returns_list_of_strings() -> None:
    result = _tokenize("iron condor straddle")
    assert isinstance(result, list)
    assert all(isinstance(t, str) for t in result)


def test_tokenize_empty_string() -> None:
    assert _tokenize("") == []


# ---------------------------------------------------------------------------
# Cosine similarity
# ---------------------------------------------------------------------------

def test_cosine_identical_vectors() -> None:
    v = {"a": 1.0, "b": 2.0}
    assert abs(_cosine(v, v) - 1.0) < 1e-9


def test_cosine_orthogonal_vectors() -> None:
    a = {"a": 1.0}
    b = {"b": 1.0}
    assert _cosine(a, b) == 0.0


def test_cosine_zero_vector() -> None:
    assert _cosine({}, {"a": 1.0}) == 0.0
    assert _cosine({"a": 1.0}, {}) == 0.0


# ---------------------------------------------------------------------------
# TF-IDF retrieval
# ---------------------------------------------------------------------------

def test_retrieve_tfidf_returns_top_k() -> None:
    chunks = [
        _Chunk("iron condor options strategy profit", "strategy"),
        _Chunk("ARIMA time series forecasting", "forecast"),
        _Chunk("GDP inflation macro economic", "macro"),
    ]
    results = _retrieve_tfidf("iron condor strategy", chunks, top_k=1)
    assert len(results) <= 1
    assert any("iron condor" in r for r in results)


def test_retrieve_tfidf_respects_top_k() -> None:
    chunks = [_Chunk(f"chunk number {i} text", "test") for i in range(10)]
    results = _retrieve_tfidf("chunk text", chunks, top_k=3)
    assert len(results) <= 3


def test_retrieve_tfidf_empty_query() -> None:
    chunks = [_Chunk("some text here", "test")]
    results = _retrieve_tfidf("", chunks, top_k=2)
    assert isinstance(results, list)


# ---------------------------------------------------------------------------
# Knowledge base
# ---------------------------------------------------------------------------

def test_knowledge_base_is_non_empty() -> None:
    assert len(_KNOWLEDGE_BASE) > 10


def test_knowledge_base_has_required_topics() -> None:
    topics = {c.topic for c in _KNOWLEDGE_BASE}
    assert "options_strategy" in topics
    assert "risk" in topics
    assert "forecasting" in topics
    assert "macro" in topics


def test_knowledge_base_chunks_are_non_empty_strings() -> None:
    for chunk in _KNOWLEDGE_BASE:
        assert isinstance(chunk.text, str) and len(chunk.text) > 10
        assert isinstance(chunk.topic, str) and len(chunk.topic) > 0


# ---------------------------------------------------------------------------
# retrieve()
# ---------------------------------------------------------------------------

def test_retrieve_returns_list_of_strings() -> None:
    results = retrieve("straddle options strategy", top_k=2)
    assert isinstance(results, list)
    assert all(isinstance(r, str) for r in results)


def test_retrieve_returns_at_most_top_k() -> None:
    results = retrieve("any query", top_k=2)
    assert len(results) <= 2


def test_retrieve_options_query_returns_relevant_content() -> None:
    results = retrieve("iron condor four strikes profit", top_k=3)
    combined = " ".join(results).lower()
    assert "condor" in combined or "spread" in combined or "strike" in combined


def test_retrieve_forecasting_query_returns_relevant_content() -> None:
    results = retrieve("ARIMA time series model fit predict", top_k=3)
    combined = " ".join(results).lower()
    assert "arima" in combined or "forecast" in combined or "series" in combined


def test_retrieve_macro_query_returns_relevant_content() -> None:
    results = retrieve("GDP inflation Federal Reserve rates", top_k=3)
    combined = " ".join(results).lower()
    assert any(word in combined for word in ("gdp", "inflation", "cpi", "macro", "rate"))


def test_retrieve_empty_query() -> None:
    results = retrieve("", top_k=3)
    assert isinstance(results, list)


# ---------------------------------------------------------------------------
# add_document()
# ---------------------------------------------------------------------------

def test_add_document_appears_in_retrieval() -> None:
    unique = "xQzWmUniqueTestPhrase2026 special rule for testing only"
    add_document(unique, topic="test_topic")
    results = retrieve("xQzWmUniqueTestPhrase2026 special rule", top_k=5)
    assert any("xQzWmUniqueTestPhrase2026" in r for r in results)


def test_add_document_added_to_custom_docs() -> None:
    initial_count = len(_CUSTOM_DOCS)
    add_document("Another unique custom document text for test.", "custom")
    assert len(_CUSTOM_DOCS) > initial_count


# ---------------------------------------------------------------------------
# build_rag_context()
# ---------------------------------------------------------------------------

def test_build_rag_context_returns_string() -> None:
    ctx = build_rag_context("straddle options volatility", top_k=2)
    assert isinstance(ctx, str)


def test_build_rag_context_non_empty_for_valid_query() -> None:
    ctx = build_rag_context("iron condor strategy", top_k=2)
    assert len(ctx) > 0


def test_build_rag_context_contains_numbered_items() -> None:
    ctx = build_rag_context("options strategy straddle", top_k=2)
    assert "1." in ctx


def test_build_rag_context_contains_header() -> None:
    ctx = build_rag_context("straddle put call strike", top_k=1)
    assert "context" in ctx.lower() or "1." in ctx
