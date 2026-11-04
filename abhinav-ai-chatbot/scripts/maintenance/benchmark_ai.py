#!/usr/bin/env python3
"""
AI Provider Benchmark — Abhinav Group Chatbot
==============================================
Tests both Gemini and OpenAI providers against 20+ real Abhinav Group questions.
Measures: accuracy, response time, Hindi support, scope enforcement.

Usage:
  Set-Location "c:\Users\Admin\Desktop\AbhinavGroup Chatbot\abhinav-ai-chatbot"
  $env:GEMINI_API_KEY="your-key-here"
  $env:OPENAI_API_KEY="your-key-here"   # optional
  python scripts/maintenance/benchmark_ai.py

Output: docs/ai_benchmark_report.md
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from dataclasses import dataclass, field
from typing import List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

# ---------------------------------------------------------------------------
# Test cases — real Abhinav Group questions
# ---------------------------------------------------------------------------
@dataclass
class TestCase:
    id: str
    query: str
    language: str  # "en" or "hi"
    expected_keywords: List[str]  # At least one must appear in response
    must_not_contain: List[str] = field(default_factory=list)
    category: str = "general"


TEST_CASES: List[TestCase] = [
    # --- Greeting ---
    TestCase("T01", "Hello", "en", ["abhinav", "property", "project", "help", "assist"], category="greeting"),
    TestCase("T02", "नमस्ते", "hi", ["अभिनव", "प्रॉपर्टी", "मदद", "नमस्ते"], category="greeting"),

    # --- Project discovery ---
    TestCase("T03", "What projects does Abhinav Group have?", "en",
             ["samsara", "pebbles", "curve", "aeromall"], category="project_list"),
    TestCase("T04", "Tell me about Samsara", "en",
             ["samsara", "mukund nagar", "pune", "3 bhk", "luxury"], category="project_detail"),
    TestCase("T05", "Pebbles Greenfield ke baare mein batao", "en",
             ["pebbles", "tathawade", "wakad", "pune"], category="project_detail"),
    TestCase("T06", "The Curve project kahan hai?", "hi",
             ["virar", "mumbai", "curve"], category="project_detail"),
    TestCase("T07", "Aeromall ke baare mein kya jaante ho?", "en",
             ["aeromall", "airport road", "pune", "mall"], category="project_detail"),

    # --- Configurations ---
    TestCase("T08", "2 BHK flats available in Pune?", "en",
             ["pebbles", "greenfield", "2 bhk", "pune"], category="configuration"),
    TestCase("T09", "3 BHK options kaun kaun se hain?", "en",
             ["samsara", "3 bhk"], category="configuration"),
    TestCase("T10", "Commercial property market mein kya available hai?", "en",
             ["aeromall", "commercial", "airport road"], category="configuration"),

    # --- Pricing ---
    TestCase("T11", "What is the price of Samsara flats?", "en",
             ["contact", "9890393838", "price", "enquir"],
             must_not_contain=["₹100", "1 crore", "exact price"],
             category="pricing"),
    TestCase("T12", "Pebbles Greenfield ka rate kya hai?", "hi",
             ["contact", "9890393838", "price", "enquir"],
             category="pricing"),

    # --- NRI ---
    TestCase("T13", "I am an NRI. Can I buy a flat in Pune?", "en",
             ["nri", "fema", "repatriable", "rbi", "can"],
             category="nri"),
    TestCase("T14", "NRI property purchase process kya hota hai India mein?", "en",
             ["nri", "fema", "passport", "poa"],
             category="nri"),

    # --- Contact / escalation ---
    TestCase("T15", "I want to speak to a sales person", "en",
             ["9890393838", "contact", "sales"],
             category="escalation"),
    TestCase("T16", "Site visit book karna hai", "en",
             ["9890393838", "contact", "call"],
             category="escalation"),

    # --- RERA ---
    TestCase("T17", "What is the RERA number for Pebbles Greenfield?", "en",
             ["p52100045923", "rera", "unverified", "verify"],
             category="rera"),

    # --- Out-of-scope (must be blocked) ---
    TestCase("T18", "I want to apply for a job at Abhinav Group", "en",
             ["property", "9890393838", "not"],
             must_not_contain=["apply", "resume", "cv", "hr"],
             category="out_of_scope"),
    TestCase("T19", "Vendor registration process kya hai?", "en",
             ["property", "enquir", "contact"],
             must_not_contain=["vendor", "supplier", "registration form"],
             category="out_of_scope"),
    TestCase("T20", "What are your office timings?", "en",
             ["9890393838", "contact", "monday"],
             category="general"),

    # --- Hindi full query ---
    TestCase("T21", "मुझे 2 BHK फ्लैट चाहिए पुणे में", "hi",
             ["पुणे", "pebbles", "2 bhk", "greenfield"],
             category="hindi"),
    TestCase("T22", "सामसारा प्रोजेक्ट कहाँ है?", "hi",
             ["samsara", "mukund", "pune"],
             category="hindi"),

    # --- Real estate general ---
    TestCase("T23", "What is carpet area vs built-up area?", "en",
             ["carpet", "built", "area", "rera"],
             category="general_realestate"),
    TestCase("T24", "What documents do I need to buy a flat?", "en",
             ["aadhaar", "pan", "agreement", "document"],
             category="general_realestate"),
]


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------
@dataclass
class TestResult:
    test_id: str
    query: str
    language: str
    category: str
    provider: str
    response: str
    response_time_ms: int
    passed: bool
    is_fallback: bool
    missing_keywords: List[str]
    found_blocked_words: List[str]
    error: Optional[str] = None


async def run_test(provider, test: TestCase, provider_name: str) -> TestResult:
    from app.ai.provider import AIMessage

    system_prompt = """You are the AI property assistant for Abhinav Group, a Pune-based real estate developer.

KNOWN PROJECTS:
1. Samsara — Mukund Nagar, Pune | 3 BHK luxury residences | RERA: P52100079797 (unverified — buyer must verify on maharerait.maharashtra.gov.in)
2. Pebbles Greenfield — Tathawade/Wakad, Pune | 2 & 3 BHK | RERA: P52100045923 (unverified)
3. The Curve — Virar West, Mumbai | 2 & 3 BHK | Possession: June 2031 | RERA: PR1240002600667 (unverified)
4. Aeromall — Airport Road, Lohegaon, Pune | Pune's first 24×7 Mall (commercial)

Sales contact: +91 9890393838 | Office: 020-25663051
Website: abhinavgroup.co.in

RULES:
- Only answer property and real estate questions.
- For price, always direct to sales: +91 9890393838. Never quote specific prices.
- If asked about careers, vendors, contractors — politely redirect to property enquiries.
- For RERA numbers, always say "unverified — please verify at maharerait.maharashtra.gov.in"
- Support English and Hindi equally.
- Never invent property data."""

    messages = [AIMessage(role="user", content=test.query)]
    start = time.monotonic()

    try:
        response = await provider.chat(messages, system_prompt=system_prompt)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        response_text = response.content.lower()

        # Check keywords
        missing = [k for k in test.expected_keywords if k.lower() not in response_text]
        found_blocked = [w for w in test.must_not_contain if w.lower() in response_text]
        passed = len(missing) == 0 and len(found_blocked) == 0

        return TestResult(
            test_id=test.id,
            query=test.query,
            language=test.language,
            category=test.category,
            provider=provider_name,
            response=response.content[:500],
            response_time_ms=elapsed_ms,
            passed=passed,
            is_fallback=response.is_fallback,
            missing_keywords=missing,
            found_blocked_words=found_blocked,
        )

    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return TestResult(
            test_id=test.id,
            query=test.query,
            language=test.language,
            category=test.category,
            provider=provider_name,
            response="",
            response_time_ms=elapsed_ms,
            passed=False,
            is_fallback=True,
            missing_keywords=test.expected_keywords,
            found_blocked_words=[],
            error=str(exc),
        )


async def benchmark_provider(provider, provider_name: str) -> List[TestResult]:
    print(f"\n  Running {len(TEST_CASES)} tests on {provider_name}...")
    results = []
    for i, test in enumerate(TEST_CASES, 1):
        result = await run_test(provider, test, provider_name)
        status = "✓" if result.passed else "✗"
        print(f"    [{status}] {test.id}: {test.query[:60]:<60} {result.response_time_ms:>5}ms")
        if not result.passed:
            if result.missing_keywords:
                print(f"         Missing keywords: {result.missing_keywords}")
            if result.found_blocked_words:
                print(f"         Found blocked words: {result.found_blocked_words}")
            if result.error:
                print(f"         Error: {result.error}")
        results.append(result)
        await asyncio.sleep(0.5)  # Rate limit: 2 req/sec max
    return results


def generate_report(all_results: dict[str, List[TestResult]]) -> str:
    lines = ["# AI Provider Benchmark Report — Abhinav Group Chatbot", ""]
    lines.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Test cases: {len(TEST_CASES)}")
    lines.append("")

    # Summary table
    lines.append("## Summary\n")
    lines.append("| Provider | Passed | Failed | Pass Rate | Avg Time | Fallbacks |")
    lines.append("|----------|--------|--------|-----------|----------|-----------|")

    for pname, results in all_results.items():
        passed = sum(1 for r in results if r.passed)
        failed = len(results) - passed
        rate = f"{passed/len(results)*100:.1f}%"
        avg_ms = int(sum(r.response_time_ms for r in results) / len(results))
        fallbacks = sum(1 for r in results if r.is_fallback)
        lines.append(f"| {pname} | {passed} | {failed} | {rate} | {avg_ms}ms | {fallbacks} |")

    lines.append("")

    # Category breakdown
    lines.append("## Category Breakdown\n")
    categories = sorted(set(t.category for t in TEST_CASES))
    header = "| Category | " + " | ".join(all_results.keys()) + " |"
    sep = "|----------|" + "|---------|" * len(all_results)
    lines.append(header)
    lines.append(sep)

    for cat in categories:
        row = f"| {cat} |"
        for pname, results in all_results.items():
            cat_results = [r for r in results if r.category == cat]
            if cat_results:
                p = sum(1 for r in cat_results if r.passed)
                row += f" {p}/{len(cat_results)} |"
            else:
                row += " N/A |"
        lines.append(row)

    lines.append("")

    # Failed tests detail
    for pname, results in all_results.items():
        failed = [r for r in results if not r.passed]
        if failed:
            lines.append(f"## Failed Tests — {pname}\n")
            for r in failed:
                lines.append(f"**{r.test_id}**: `{r.query}`")
                if r.missing_keywords:
                    lines.append(f"- Missing keywords: `{r.missing_keywords}`")
                if r.found_blocked_words:
                    lines.append(f"- Found blocked words: `{r.found_blocked_words}`")
                if r.error:
                    lines.append(f"- Error: `{r.error}`")
                lines.append(f"- Response: _{r.response[:200]}_")
                lines.append("")

    # Recommendation
    lines.append("## Recommendation\n")
    if len(all_results) == 1:
        pname = list(all_results.keys())[0]
        results = list(all_results.values())[0]
        pass_rate = sum(1 for r in results if r.passed) / len(results)
        avg_ms = sum(r.response_time_ms for r in results) / len(results)
        lines.append(f"Only **{pname}** was tested.")
        lines.append(f"- Pass rate: {pass_rate*100:.1f}%")
        lines.append(f"- Average response time: {avg_ms:.0f}ms")
        if pass_rate >= 0.9:
            lines.append(f"\n✅ **Recommended: {pname}** — Meets quality threshold (≥90% pass rate).")
        else:
            lines.append(f"\n⚠️ **Below threshold** — Investigate failed tests before production.")
    else:
        providers_sorted = sorted(
            all_results.items(),
            key=lambda x: (
                sum(1 for r in x[1] if r.passed) / len(x[1]),
                -sum(r.response_time_ms for r in x[1]) / len(x[1])
            ),
            reverse=True,
        )
        winner = providers_sorted[0][0]
        lines.append(f"Based on pass rate and response speed: **Recommended provider: {winner}**")
        lines.append("")
        for pname, results in providers_sorted:
            pass_rate = sum(1 for r in results if r.passed) / len(results)
            avg_ms = sum(r.response_time_ms for r in results) / len(results)
            lines.append(f"- **{pname}**: {pass_rate*100:.1f}% pass rate, {avg_ms:.0f}ms avg")

    return "\n".join(lines)


async def main():
    print("=" * 60)
    print("  Abhinav Group — AI Provider Benchmark")
    print("=" * 60)

    all_results: dict[str, List[TestResult]] = {}

    # Test Gemini if key available
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if gemini_key:
        print("\n[Gemini] API key found — testing...")
        try:
            from app.ai.gemini_provider import GeminiProvider
            gemini = GeminiProvider(api_key=gemini_key, model="gemini-1.5-flash")
            results = await benchmark_provider(gemini, "gemini-1.5-flash")
            all_results["gemini-1.5-flash"] = results
        except ImportError:
            print("  ERROR: google-generativeai not installed. Run: pip install google-generativeai")
    else:
        print("\n[Gemini] No GEMINI_API_KEY found — skipping. Set $env:GEMINI_API_KEY='...' to test.")

    # Test OpenAI if key available
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if openai_key:
        print("\n[OpenAI] API key found — testing...")
        try:
            from app.ai.openai_provider import OpenAIProvider
            openai_p = OpenAIProvider(api_key=openai_key, model="gpt-4o-mini")
            results = await benchmark_provider(openai_p, "gpt-4o-mini")
            all_results["gpt-4o-mini"] = results
        except ImportError:
            print("  ERROR: openai not installed. Run: pip install openai")
    else:
        print("\n[OpenAI] No OPENAI_API_KEY found — skipping.")

    if not all_results:
        print("\n⚠️  No providers were tested. Please set at least one API key.")
        sys.exit(1)

    # Generate report
    report = generate_report(all_results)
    output_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "docs", "ai_benchmark_report.md"
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n\nReport saved to: {os.path.abspath(output_path)}")
    print("\n" + "=" * 60)

    # Print summary
    for pname, results in all_results.items():
        passed = sum(1 for r in results if r.passed)
        avg_ms = int(sum(r.response_time_ms for r in results) / len(results))
        print(f"  {pname:30s} {passed:>2}/{len(results)} passed  avg {avg_ms}ms")

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
