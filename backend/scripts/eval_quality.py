#!/usr/bin/env python3.12
"""
Brubru Quality Evaluation Suite

Runs golden answer queries against the live backend (or local),
scores each response against quality criteria, and reports
aggregate quality metrics including the Brubru Quality Score (BQS).

Usage:
    python3.12 scripts/eval_quality.py                         # Run all 30 golden answers
    python3.12 scripts/eval_quality.py --pattern explain_topic  # Run one query type
    python3.12 scripts/eval_quality.py --language CA             # Run one language
    python3.12 scripts/eval_quality.py --id GA-001               # Run a single golden answer
    python3.12 scripts/eval_quality.py --backend http://localhost:8000  # Custom backend URL
    python3.12 scripts/eval_quality.py --json                    # Machine-readable output
    python3.12 scripts/eval_quality.py --verbose                 # Show full response text

Prerequisites:
    - Backend running (local or production)
    - data/golden_answers/golden_answers.json exists

Quality criteria checked per response:
    1. mentions_celex_or_com       - Response contains a CELEX number or COM reference
    2. includes_doc_refs_from_guide - Response includes document refs from the guide's QUICK FACTS
    3. british_english              - Uses British English spellings (analyse, behaviour, etc.)
    4. does_not_say_search_eurlex   - No deflection to "search EUR-Lex yourself"
    5. does_not_say_i_dont_have     - No "I don't have access to" cop-outs
    6. responds_in_query_language   - Response language matches query language
    7. actionable_followup          - Response offers a concrete next step

Aggregate metrics:
    - Pass rate: % of queries where all criteria pass
    - Per-criterion pass rate
    - Citation count (avg citations per response)
    - Response time (avg, p95)
    - BQS (Brubru Quality Score): weighted composite
"""

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import requests


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
GOLDEN_ANSWERS_PATH = PROJECT_ROOT / "data" / "golden_answers" / "golden_answers.json"

DEFAULT_BACKEND = "http://localhost:8000"
CHAT_ENDPOINT = "/api/chat/message"
REQUEST_TIMEOUT = 200  # seconds (context building can be slow)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class CriterionResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class QueryResult:
    id: str
    query: str
    language: str
    pattern: str
    passed: bool = False
    criteria_results: list = field(default_factory=list)
    criteria_passed: int = 0
    criteria_total: int = 0
    citation_count: int = 0
    response_time_ms: float = 0.0
    model: str = ""
    response_text: str = ""
    error: str = ""


@dataclass
class EvalReport:
    timestamp: str = ""
    backend_url: str = ""
    total_queries: int = 0
    queries_passed: int = 0
    pass_rate: float = 0.0
    avg_response_time_ms: float = 0.0
    p95_response_time_ms: float = 0.0
    avg_citations: float = 0.0
    bqs: float = 0.0
    per_criterion: dict = field(default_factory=dict)
    per_pattern: dict = field(default_factory=dict)
    per_language: dict = field(default_factory=dict)
    results: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Criterion checkers
# ---------------------------------------------------------------------------
CELEX_PATTERN = re.compile(r"\b[0-9]{5}[A-Z][0-9]{4}\b|3\d{4}[A-Z]\d{4}")
COM_PATTERN = re.compile(r"COM\s*\(\d{4}\)\s*\d+", re.IGNORECASE)
PROCEDURE_PATTERN = re.compile(r"\d{4}/\d{4}\((?:COD|NLE|APP|CNS|INI|INL|RSP|RPS|BUD)\)")

DEFLECTION_PATTERNS = [
    r"search\s+EUR-Lex",
    r"check\s+EUR-Lex",
    r"visit\s+EUR-Lex",
    r"consult\s+EUR-Lex\s+yourself",
    r"I\s+recommend\s+(you\s+)?check(ing)?\s+EUR-Lex",
    r"you\s+(can|should|may)\s+(search|check|visit|consult)\s+EUR-Lex",
]
DEFLECTION_RE = re.compile("|".join(DEFLECTION_PATTERNS), re.IGNORECASE)

DONT_HAVE_PATTERNS = [
    r"I\s+don'?t\s+have\s+access\s+to",
    r"I\s+don'?t\s+have\s+the\s+(specific\s+)?text",
    r"I\s+cannot\s+access",
    r"I\s+am\s+unable\s+to\s+access",
    r"I\s+do\s+not\s+have\s+access",
]
DONT_HAVE_RE = re.compile("|".join(DONT_HAVE_PATTERNS), re.IGNORECASE)

# British English markers (if these appear, good; American spellings are bad)
AMERICAN_SPELLINGS = {
    "analyze": "analyse",
    "behavior": "behaviour",
    "color": "colour",
    "favor": "favour",
    "honor": "honour",
    "humor": "humour",
    "labor": "labour",
    "neighbor": "neighbour",
    "organization": "organisation",
    "recognize": "recognise",
    "summarize": "summarise",
    "optimize": "optimise",
    "harmonize": "harmonise",
    "authorize": "authorise",
    "customize": "customise",
    "digitalize": "digitalise",
}

# Language detection heuristics (lightweight, no dependency)
LANGUAGE_MARKERS = {
    "EN": ["the", "and", "of", "is", "for", "in", "to", "with", "this", "that"],
    "FR": ["le", "la", "les", "des", "une", "est", "dans", "pour", "avec", "cette"],
    "ES": ["el", "la", "los", "las", "una", "del", "por", "con", "esta", "para"],
    "CA": ["el", "la", "els", "les", "una", "del", "per", "amb", "aquesta", "dels"],
    "IT": ["il", "la", "le", "dei", "una", "del", "per", "con", "questa", "nella"],
    "NL": ["de", "het", "een", "van", "voor", "met", "die", "dat", "deze", "wordt"],
}


def detect_language(text: str) -> str:
    """Simple word-frequency language detection."""
    words = re.findall(r"\b\w+\b", text.lower())
    if not words:
        return "EN"

    scores = {}
    for lang, markers in LANGUAGE_MARKERS.items():
        score = sum(1 for w in words if w in markers)
        scores[lang] = score / len(words) if words else 0

    # CA vs ES disambiguation: look for Catalan-specific words
    if scores.get("CA", 0) > 0 and scores.get("ES", 0) > 0:
        catalan_unique = ["amb", "aquesta", "dels", "pel", "als", "tambe", "pero", "regulacio"]
        spanish_unique = ["con", "esta", "por", "tambien", "pero", "regulacion"]
        ca_hits = sum(1 for w in words if w in catalan_unique)
        es_hits = sum(1 for w in words if w in spanish_unique)
        if ca_hits > es_hits:
            scores["CA"] += 0.05
        elif es_hits > ca_hits:
            scores["ES"] += 0.05

    # IT vs ES disambiguation: many shared words (la, una, del, con).
    # Look for tokens that exist in one language but not the other.
    if scores.get("IT", 0) > 0 and scores.get("ES", 0) > 0:
        italian_unique = ["il", "lo", "gli", "dei", "degli", "delle", "della",
                          "nella", "nel", "sulla", "sono", "sono", "anche",
                          "questa", "questo", "quelli", "tutti", "tutto", "pero",
                          "perche", "molto", "cosi", "ogni", "sempre"]
        spanish_unique_vs_it = ["el", "los", "las", "por", "esta", "para",
                                "tambien", "porque", "mucho", "asi", "cada",
                                "siempre", "todos", "todas"]
        it_hits = sum(1 for w in words if w in italian_unique)
        es_hits = sum(1 for w in words if w in spanish_unique_vs_it)
        if it_hits > es_hits:
            scores["IT"] += 0.05
        elif es_hits > it_hits:
            scores["ES"] += 0.05

    best = max(scores, key=scores.get)
    return best if scores[best] > 0.02 else "EN"


def extract_doc_refs_from_quick_facts(quick_facts: str) -> list:
    """Extract CELEX, COM, procedure refs from the guide's QUICK FACTS."""
    refs = []
    refs.extend(CELEX_PATTERN.findall(quick_facts))
    refs.extend(COM_PATTERN.findall(quick_facts))
    refs.extend(PROCEDURE_PATTERN.findall(quick_facts))
    return refs


def check_mentions_celex_or_com(response: str, _ga: dict) -> CriterionResult:
    """Response must contain at least one CELEX number, COM reference, or procedure ref."""
    celex = CELEX_PATTERN.findall(response)
    com = COM_PATTERN.findall(response)
    proc = PROCEDURE_PATTERN.findall(response)
    all_refs = celex + com + proc
    if all_refs:
        return CriterionResult("mentions_celex_or_com", True, f"Found: {', '.join(all_refs[:5])}")
    return CriterionResult("mentions_celex_or_com", False, "No CELEX, COM, or procedure ref found")


def check_includes_doc_refs_from_guide(response: str, ga: dict) -> CriterionResult:
    """Response should include at least one document reference from the guide's QUICK FACTS."""
    quick_facts = ga.get("quick_facts_excerpt", "")
    if not quick_facts:
        return CriterionResult("includes_doc_refs_from_guide", True, "No QUICK FACTS to check against")

    guide_refs = extract_doc_refs_from_quick_facts(quick_facts)
    if not guide_refs:
        # If the guide itself has no extractable refs, pass
        return CriterionResult("includes_doc_refs_from_guide", True, "Guide has no extractable refs")

    found = []
    for ref in guide_refs:
        # Build a whitespace-tolerant regex. Python 3.12's re.escape escapes
        # spaces with a literal backslash, so we can't just re.sub whitespace
        # after escaping -- we have to split first.
        parts = re.split(r"\s+", ref)
        normalised = r"\s*".join(re.escape(p) for p in parts)
        if re.search(normalised, response, re.IGNORECASE):
            found.append(ref)

    if found:
        return CriterionResult(
            "includes_doc_refs_from_guide", True,
            f"Found {len(found)}/{len(guide_refs)}: {', '.join(found[:3])}"
        )
    return CriterionResult(
        "includes_doc_refs_from_guide", False,
        f"None of {len(guide_refs)} guide refs found in response"
    )


def check_british_english(response: str, ga: dict) -> CriterionResult:
    """
    Response should use British English spellings.

    Gate: only apply this check to English-language queries. Words like
    "favor" are legitimate Spanish / Portuguese vocabulary and must not be
    flagged as American English when the response is in ES/CA/IT/FR/NL.
    """
    if ga.get("language", "EN") != "EN":
        return CriterionResult(
            "british_english", True,
            f"Skipped (response language: {ga.get('language')})",
        )

    american_found = []
    words = re.findall(r"\b\w+\b", response.lower())
    for american, british in AMERICAN_SPELLINGS.items():
        if american in words and british not in words:
            american_found.append(f"{american} (should be {british})")

    if not american_found:
        return CriterionResult("british_english", True)
    return CriterionResult(
        "british_english", False,
        f"American spellings: {'; '.join(american_found[:3])}"
    )


def check_does_not_say_search_eurlex(response: str, _ga: dict) -> CriterionResult:
    """Response must not deflect to 'search EUR-Lex yourself'."""
    match = DEFLECTION_RE.search(response)
    if match:
        return CriterionResult("does_not_say_search_eurlex", False, f"Deflection found: '{match.group()}'")
    return CriterionResult("does_not_say_search_eurlex", True)


def check_does_not_say_i_dont_have(response: str, _ga: dict) -> CriterionResult:
    """Response must not say 'I don't have access to the text'."""
    match = DONT_HAVE_RE.search(response)
    if match:
        return CriterionResult("does_not_say_i_dont_have", False, f"Cop-out found: '{match.group()}'")
    return CriterionResult("does_not_say_i_dont_have", True)


def check_responds_in_query_language(response: str, ga: dict) -> CriterionResult:
    """Response language should match query language."""
    expected = ga.get("language", "EN")
    if expected == "EN":
        # For English queries, just check it's not in another language
        detected = detect_language(response)
        if detected == "EN":
            return CriterionResult("responds_in_query_language", True)
        return CriterionResult(
            "responds_in_query_language", False,
            f"Expected EN, detected {detected}"
        )

    detected = detect_language(response)
    if detected == expected:
        return CriterionResult("responds_in_query_language", True)

    # For CA/ES ambiguity, be lenient
    if expected in ("CA", "ES") and detected in ("CA", "ES"):
        return CriterionResult(
            "responds_in_query_language", True,
            f"CA/ES ambiguity (detected {detected}, expected {expected})"
        )

    return CriterionResult(
        "responds_in_query_language", False,
        f"Expected {expected}, detected {detected}"
    )


def check_actionable_followup(response: str, _ga: dict) -> CriterionResult:
    """Response should offer a concrete next step or follow-up."""
    followup_signals = [
        r"would you like",
        r"shall I",
        r"I can (also|help|provide|draft|analyse|explain)",
        r"you (can|could|might|may) (also|want to)",
        r"for (more|further) (detail|information|analysis)",
        r"next step",
        r"if you('d| would) like",
        r"do you want",
        r"feel free to ask",
        r"let me know if",
    ]
    for pattern in followup_signals:
        if re.search(pattern, response, re.IGNORECASE):
            return CriterionResult("actionable_followup", True)

    # Also pass if the response ends with a question
    sentences = re.split(r"[.!?]\s+", response.strip())
    if sentences and sentences[-1].strip().endswith("?"):
        return CriterionResult("actionable_followup", True, "Ends with question")

    return CriterionResult("actionable_followup", False, "No follow-up or next step offered")


CRITERION_CHECKERS = {
    "mentions_celex_or_com": check_mentions_celex_or_com,
    "includes_doc_refs_from_guide": check_includes_doc_refs_from_guide,
    "british_english": check_british_english,
    "does_not_say_search_eurlex": check_does_not_say_search_eurlex,
    "does_not_say_i_dont_have": check_does_not_say_i_dont_have,
    "responds_in_query_language": check_responds_in_query_language,
    "actionable_followup": check_actionable_followup,
}


# ---------------------------------------------------------------------------
# Query runner
# ---------------------------------------------------------------------------
def run_query(backend_url: str, ga: dict, verbose: bool = False) -> QueryResult:
    """Send a golden answer query to the backend and evaluate the response."""
    result = QueryResult(
        id=ga["id"],
        query=ga["query"],
        language=ga.get("language", "EN"),
        pattern=ga.get("pattern", "unknown"),
    )

    payload = {
        "message": ga["query"],
        "user_id": None,
        "chat_id": None,
        "pre_user_id": None,
        "use_context": True,
        "stream": False,
    }

    try:
        start = time.time()
        resp = requests.post(
            f"{backend_url}{CHAT_ENDPOINT}",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        elapsed_ms = (time.time() - start) * 1000
        result.response_time_ms = round(elapsed_ms, 1)

        if resp.status_code != 200:
            result.error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            return result

        data = resp.json()
        response_text = data.get("message", "")
        result.response_text = response_text
        result.model = data.get("model", "unknown")
        result.citation_count = len(data.get("citations", []))

    except requests.exceptions.Timeout:
        result.error = f"Timeout after {REQUEST_TIMEOUT}s"
        return result
    except requests.exceptions.ConnectionError:
        result.error = f"Connection refused: {backend_url}"
        return result
    except Exception as e:
        result.error = str(e)
        return result

    # Run criterion checks
    criteria = ga.get("quality_criteria", list(CRITERION_CHECKERS.keys()))
    for criterion_name in criteria:
        checker = CRITERION_CHECKERS.get(criterion_name)
        if checker:
            cr = checker(response_text, ga)
            result.criteria_results.append(cr)
        else:
            result.criteria_results.append(
                CriterionResult(criterion_name, False, f"Unknown criterion: {criterion_name}")
            )

    result.criteria_total = len(result.criteria_results)
    result.criteria_passed = sum(1 for cr in result.criteria_results if cr.passed)
    result.passed = result.criteria_passed == result.criteria_total

    return result


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------
def compute_bqs(report: EvalReport) -> float:
    """
    Brubru Quality Score (BQS) = weighted composite.

    BQS = (0.30 x Eval Pass Rate)
        + (0.25 x Citation Accuracy proxy)
        + (0.15 x Language Consistency)
        + (0.10 x Guide Coverage proxy)
        + (0.10 x (1 - Deflection Rate))
        + (0.10 x Response Time score)

    Note: Some metrics (guide coverage, knowledge freshness) require
    production data. For the eval script, we approximate with available signals.
    """
    if not report.results:
        return 0.0

    total = len(report.results)
    successful = [r for r in report.results if not r.error]
    if not successful:
        return 0.0

    n = len(successful)

    # Eval pass rate (all criteria pass)
    eval_pass_rate = sum(1 for r in successful if r.passed) / n

    # Citation accuracy proxy: % of responses that mention CELEX/COM
    celex_pass = sum(
        1 for r in successful
        if any(cr.name == "mentions_celex_or_com" and cr.passed for cr in r.criteria_results)
    ) / n

    # Language consistency
    lang_pass = sum(
        1 for r in successful
        if any(cr.name == "responds_in_query_language" and cr.passed for cr in r.criteria_results)
    ) / n

    # Guide coverage proxy: % that include doc refs from guide
    guide_pass = sum(
        1 for r in successful
        if any(cr.name == "includes_doc_refs_from_guide" and cr.passed for cr in r.criteria_results)
    ) / n

    # Deflection rate
    deflection_count = sum(
        1 for r in successful
        if any(cr.name == "does_not_say_search_eurlex" and not cr.passed for cr in r.criteria_results)
    )
    deflection_rate = deflection_count / n

    # Response time score: 1.0 if avg < 30s, 0.5 if < 60s, 0.0 if > 60s
    avg_time = sum(r.response_time_ms for r in successful) / n
    if avg_time < 30000:
        time_score = 1.0
    elif avg_time < 60000:
        time_score = 0.5
    else:
        time_score = 0.0

    bqs = (
        0.30 * eval_pass_rate
        + 0.25 * celex_pass
        + 0.15 * lang_pass
        + 0.10 * guide_pass
        + 0.10 * (1 - deflection_rate)
        + 0.10 * time_score
    )

    return round(bqs, 4)


def build_report(results: list, backend_url: str) -> EvalReport:
    """Aggregate individual query results into a report."""
    report = EvalReport(
        timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
        backend_url=backend_url,
        total_queries=len(results),
        results=results,
    )

    successful = [r for r in results if not r.error]
    if not successful:
        return report

    report.queries_passed = sum(1 for r in successful if r.passed)
    report.pass_rate = round(report.queries_passed / len(successful) * 100, 1)

    times = [r.response_time_ms for r in successful]
    report.avg_response_time_ms = round(sum(times) / len(times), 1)
    sorted_times = sorted(times)
    p95_idx = int(len(sorted_times) * 0.95)
    report.p95_response_time_ms = round(sorted_times[min(p95_idx, len(sorted_times) - 1)], 1)

    report.avg_citations = round(sum(r.citation_count for r in successful) / len(successful), 1)

    # Per-criterion pass rates
    criterion_counts = {}
    for r in successful:
        for cr in r.criteria_results:
            if cr.name not in criterion_counts:
                criterion_counts[cr.name] = {"passed": 0, "total": 0}
            criterion_counts[cr.name]["total"] += 1
            if cr.passed:
                criterion_counts[cr.name]["passed"] += 1

    report.per_criterion = {
        name: round(counts["passed"] / counts["total"] * 100, 1) if counts["total"] > 0 else 0
        for name, counts in criterion_counts.items()
    }

    # Per-pattern pass rates
    pattern_counts = {}
    for r in successful:
        if r.pattern not in pattern_counts:
            pattern_counts[r.pattern] = {"passed": 0, "total": 0}
        pattern_counts[r.pattern]["total"] += 1
        if r.passed:
            pattern_counts[r.pattern]["passed"] += 1

    report.per_pattern = {
        name: {"passed": counts["passed"], "total": counts["total"],
               "rate": round(counts["passed"] / counts["total"] * 100, 1)}
        for name, counts in pattern_counts.items()
    }

    # Per-language pass rates
    lang_counts = {}
    for r in successful:
        if r.language not in lang_counts:
            lang_counts[r.language] = {"passed": 0, "total": 0}
        lang_counts[r.language]["total"] += 1
        if r.passed:
            lang_counts[r.language]["passed"] += 1

    report.per_language = {
        name: {"passed": counts["passed"], "total": counts["total"],
               "rate": round(counts["passed"] / counts["total"] * 100, 1)}
        for name, counts in lang_counts.items()
    }

    report.bqs = compute_bqs(report)

    return report


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------
def print_report(report: EvalReport, verbose: bool = False):
    """Print human-readable report to terminal."""
    print()
    print("=" * 70)
    print("  BRUBRU QUALITY EVALUATION REPORT")
    print(f"  {report.timestamp}")
    print(f"  Backend: {report.backend_url}")
    print("=" * 70)
    print()

    # BQS
    bqs_pct = round(report.bqs * 100, 1)
    if report.bqs >= 0.80:
        verdict = "HEALTHY"
    elif report.bqs >= 0.65:
        verdict = "NEEDS WORK"
    else:
        verdict = "CRITICAL"
    print(f"  BQS (Brubru Quality Score): {bqs_pct}% [{verdict}]")
    print()

    # Summary
    errors = sum(1 for r in report.results if r.error)
    print(f"  Queries:     {report.total_queries}")
    print(f"  Passed:      {report.queries_passed}")
    print(f"  Failed:      {report.total_queries - report.queries_passed - errors}")
    print(f"  Errors:      {errors}")
    print(f"  Pass rate:   {report.pass_rate}%")
    print(f"  Avg time:    {report.avg_response_time_ms:.0f}ms")
    print(f"  P95 time:    {report.p95_response_time_ms:.0f}ms")
    print(f"  Avg cites:   {report.avg_citations}")
    print()

    # Per-criterion
    print("  Per-Criterion Pass Rates:")
    print("  " + "-" * 55)
    for name, rate in sorted(report.per_criterion.items(), key=lambda x: x[1]):
        bar = "#" * int(rate / 5) + "." * (20 - int(rate / 5))
        status = "OK" if rate >= 85 else "!!" if rate < 70 else ".."
        print(f"  [{status}] {name:<40} {rate:>5.1f}% [{bar}]")
    print()

    # Per-pattern
    if report.per_pattern:
        print("  Per-Pattern Pass Rates:")
        print("  " + "-" * 55)
        for name, data in sorted(report.per_pattern.items(), key=lambda x: x[1]["rate"]):
            print(f"       {name:<25} {data['passed']}/{data['total']} ({data['rate']}%)")
        print()

    # Per-language
    if report.per_language:
        print("  Per-Language Pass Rates:")
        print("  " + "-" * 55)
        for name, data in sorted(report.per_language.items(), key=lambda x: x[1]["rate"]):
            print(f"       {name:<5} {data['passed']}/{data['total']} ({data['rate']}%)")
        print()

    # Individual results
    print("  Individual Results:")
    print("  " + "-" * 55)
    for r in report.results:
        if r.error:
            print(f"  [ERR] {r.id} {r.query[:45]:<45}")
            print(f"        Error: {r.error[:60]}")
        elif r.passed:
            print(f"  [OK]  {r.id} {r.query[:45]:<45} {r.response_time_ms:.0f}ms {r.citation_count} cites")
        else:
            failed = [cr.name for cr in r.criteria_results if not cr.passed]
            print(f"  [!!]  {r.id} {r.query[:45]:<45} {r.response_time_ms:.0f}ms")
            for cr in r.criteria_results:
                if not cr.passed:
                    print(f"        FAIL: {cr.name} - {cr.detail[:55]}")

        if verbose and r.response_text:
            print(f"        Response ({len(r.response_text)} chars):")
            # Show first 300 chars
            preview = r.response_text[:300].replace("\n", " ")
            print(f"        {preview}...")
            print()

    print()
    print("=" * 70)


def save_json_report(report: EvalReport, path: Optional[str] = None):
    """Save machine-readable JSON report."""
    if path is None:
        path = PROJECT_ROOT / "data" / "golden_answers" / "eval_results.json"

    output = {
        "timestamp": report.timestamp,
        "backend_url": report.backend_url,
        "bqs": report.bqs,
        "total_queries": report.total_queries,
        "queries_passed": report.queries_passed,
        "pass_rate": report.pass_rate,
        "avg_response_time_ms": report.avg_response_time_ms,
        "p95_response_time_ms": report.p95_response_time_ms,
        "avg_citations": report.avg_citations,
        "per_criterion": report.per_criterion,
        "per_pattern": report.per_pattern,
        "per_language": report.per_language,
        "results": [
            {
                "id": r.id,
                "query": r.query,
                "language": r.language,
                "pattern": r.pattern,
                "passed": r.passed,
                "criteria_passed": r.criteria_passed,
                "criteria_total": r.criteria_total,
                "citation_count": r.citation_count,
                "response_time_ms": r.response_time_ms,
                "model": r.model,
                "error": r.error,
                "criteria_details": [
                    {"name": cr.name, "passed": cr.passed, "detail": cr.detail}
                    for cr in r.criteria_results
                ],
            }
            for r in report.results
        ],
    }

    with open(path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  JSON report saved to: {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Brubru Quality Evaluation Suite")
    parser.add_argument("--backend", default=DEFAULT_BACKEND, help="Backend URL")
    parser.add_argument("--pattern", help="Filter by query pattern (e.g. explain_topic)")
    parser.add_argument("--language", help="Filter by language (e.g. CA, FR)")
    parser.add_argument("--id", help="Run a single golden answer by ID (e.g. GA-001)")
    parser.add_argument("--json", action="store_true", help="Save JSON report")
    parser.add_argument("--verbose", action="store_true", help="Show response text")
    parser.add_argument("--dry-run", action="store_true", help="Load and validate golden answers without querying")
    args = parser.parse_args()

    # Load golden answers
    if not GOLDEN_ANSWERS_PATH.exists():
        print(f"[ERROR] Golden answers not found: {GOLDEN_ANSWERS_PATH}")
        sys.exit(1)

    with open(GOLDEN_ANSWERS_PATH) as f:
        golden_answers = json.load(f)

    print(f"\n  Loaded {len(golden_answers)} golden answers from {GOLDEN_ANSWERS_PATH.name}")

    # Apply filters
    if args.pattern:
        golden_answers = [ga for ga in golden_answers if ga.get("pattern") == args.pattern]
        print(f"  Filtered by pattern '{args.pattern}': {len(golden_answers)} queries")

    if args.language:
        golden_answers = [ga for ga in golden_answers if ga.get("language") == args.language.upper()]
        print(f"  Filtered by language '{args.language.upper()}': {len(golden_answers)} queries")

    if args.id:
        golden_answers = [ga for ga in golden_answers if ga.get("id") == args.id]
        print(f"  Filtered by ID '{args.id}': {len(golden_answers)} queries")

    if not golden_answers:
        print("  [WARN] No golden answers match the filter. Exiting.")
        sys.exit(0)

    if args.dry_run:
        print(f"\n  [DRY RUN] {len(golden_answers)} queries validated. No requests sent.")
        for ga in golden_answers:
            criteria = ga.get("quality_criteria", [])
            unknown = [c for c in criteria if c not in CRITERION_CHECKERS]
            status = "OK" if not unknown else f"Unknown criteria: {unknown}"
            print(f"    {ga['id']} [{ga['language']}] {ga['pattern']:<20} {status}")
        sys.exit(0)

    # Check backend is reachable
    print(f"\n  Checking backend at {args.backend}...")
    try:
        health = requests.get(f"{args.backend}/docs", timeout=5)
        if health.status_code == 200:
            print("  [OK] Backend is reachable")
        else:
            print(f"  [WARN] Backend returned {health.status_code} (may still work)")
    except requests.exceptions.ConnectionError:
        print(f"  [ERROR] Cannot reach {args.backend}. Is the backend running?")
        print("  Start it with: cd backend && python -m uvicorn main:app --reload")
        sys.exit(1)

    # Run queries
    print(f"\n  Running {len(golden_answers)} queries against {args.backend}...")
    print("  (This may take several minutes due to context building)\n")

    results = []
    for i, ga in enumerate(golden_answers, 1):
        print(f"  [{i}/{len(golden_answers)}] {ga['id']}: {ga['query'][:50]}...", end="", flush=True)
        result = run_query(args.backend, ga, verbose=args.verbose)
        results.append(result)

        if result.error:
            print(f" ERR ({result.error[:40]})")
        elif result.passed:
            print(f" PASS ({result.response_time_ms:.0f}ms, {result.citation_count} cites)")
        else:
            failed = sum(1 for cr in result.criteria_results if not cr.passed)
            print(f" FAIL ({failed} criteria, {result.response_time_ms:.0f}ms)")

    # Build and print report
    report = build_report(results, args.backend)
    print_report(report, verbose=args.verbose)

    if args.json:
        save_json_report(report)

    # Exit code: 0 if pass rate >= 85%, 1 otherwise
    if report.pass_rate >= 85.0:
        print("  [OK] Quality gate PASSED (pass rate >= 85%)")
        sys.exit(0)
    else:
        print(f"  [!!] Quality gate FAILED (pass rate {report.pass_rate}% < 85%)")
        sys.exit(1)


if __name__ == "__main__":
    main()
