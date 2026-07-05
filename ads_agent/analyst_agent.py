"""Phase 2 analyst agent: answers read-only questions about campaign performance.

Uses OpenAI's function-calling loop when OPENAI_API_KEY is set -- the model
decides which of the four tools in ads_agent/analyst_tools.py to call, reads
the results, and writes a final answer. Without a key, falls back to simple
keyword routing so the demo still works (same "no key = demo mode" pattern as
ads_agent/planner.py's deterministic planner).

This agent can only *read*. It is never given a write tool, which is what
makes Phase 2 "zero risk" per GOOGLE_ADS_AGENT_PLAN.md -- Phase 3 is where
write tools and a human-approval gate get added.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from ads_agent.analyst_tools import TOOL_FUNCTIONS, TOOL_SCHEMAS, get_budget_pacing, get_performance, get_search_terms, list_campaigns
from ads_agent.audit import write_audit_event


SYSTEM_PROMPT = """You are a Google Ads performance analyst.
Answer the user's question about their campaigns using only the provided tools.
Rules:
- Call tools to get real numbers before answering; never guess metrics.
- You are read-only: you cannot create, pause, enable, or change any budget.
  If asked to make a change, explain that Phase 3 (not yet built) will add that,
  and that a human must approve every write.
- Keep answers concise: 3-6 sentences, lead with the number that answers the question.
"""


@dataclass
class AnalystAnswer:
    question: str
    answer: str
    tools_used: list[str] = field(default_factory=list)


def ask_analyst(question: str) -> AnalystAnswer:
    """Answer a natural-language question using OpenAI tool-calling, else a fallback."""

    if os.getenv("OPENAI_API_KEY"):
        try:
            return _ask_with_openai(question)
        except Exception as exc:  # pragma: no cover - safety fallback for live APIs
            fallback = _ask_with_keywords(question)
            fallback.answer += f" (OpenAI fallback used: {exc})"
            return fallback

    return _ask_with_keywords(question)


def _ask_with_openai(question: str) -> AnalystAnswer:
    from openai import OpenAI

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    client = OpenAI()
    tools_used: list[str] = []

    input_messages: list[dict[str, object]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    # Function-calling loop: keep letting the model call tools until it
    # returns a plain text answer instead of another tool call. Capped at 5
    # rounds so a misbehaving model can't loop forever.
    for _ in range(5):
        response = client.responses.create(model=model, input=input_messages, tools=TOOL_SCHEMAS)

        tool_calls = [item for item in response.output if item.type == "function_call"]
        if not tool_calls:
            write_audit_event(
                "analyst_question_answered",
                {"question": question, "tools_used": tools_used},
            )
            return AnalystAnswer(question=question, answer=response.output_text, tools_used=tools_used)

        # Responses API convention: output items (including function_call
        # items) get appended directly to input, not nested inside a
        # {"role": "assistant", "content": ...} wrapper.
        input_messages.extend(response.output)
        for call in tool_calls:
            tools_used.append(call.name)
            args = json.loads(call.arguments or "{}")
            result = TOOL_FUNCTIONS[call.name](**args)
            input_messages.append(
                {
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": json.dumps(result),
                }
            )

    raise RuntimeError("Analyst agent did not converge to an answer after 5 tool-call rounds.")


def _ask_with_keywords(question: str) -> AnalystAnswer:
    """Deterministic fallback: route by keyword so the demo works with no API key."""

    q = question.lower()

    if "search term" in q or "keyword" in q:
        return _answer_search_terms(question)

    if "budget" in q or "pacing" in q or "spend" in q:
        return _answer_budget_pacing(question)

    if "cpa" in q or "cost" in q or "performance" in q or "why" in q:
        return _answer_performance(question)

    campaigns = list_campaigns()
    names = ", ".join(f"{c['name']} ({c['status']})" for c in campaigns)
    answer = (
        f"Account has {len(campaigns)} campaigns: {names}. "
        "Ask about CPA, search terms, or budget pacing for more detail."
    )
    return AnalystAnswer(question=question, answer=answer, tools_used=["list_campaigns"])


def _answer_search_terms(question: str) -> AnalystAnswer:
    terms = get_search_terms()
    zero_conversion_terms = [term for term in terms if term["conversions"] == 0]
    worst = max(zero_conversion_terms, key=lambda term: term["cost"], default=None)
    scored_terms = [term for term in terms if term["cpa"] is not None]
    best = min(scored_terms, key=lambda term: term["cpa"])

    answer = f'{len(terms)} search terms reviewed. Best CPA: "{best["term"]}" at ${best["cpa"]:.2f}.'
    if worst:
        answer += (
            f' Watch "{worst["term"]}": ${worst["cost"]:.2f} spent with 0 conversions -- '
            "a negative-keyword candidate."
        )
    return AnalystAnswer(question=question, answer=answer, tools_used=["get_search_terms"])


def _answer_budget_pacing(question: str) -> AnalystAnswer:
    pacing = get_budget_pacing()
    lines = [
        f"{p['campaign_name']}: {p['pacing_pct']}% paced "
        f"(${p['spend_so_far']} of ${p['expected_spend_at_budget']} expected so far)"
        for p in pacing
    ]
    return AnalystAnswer(question=question, answer=" | ".join(lines), tools_used=["get_budget_pacing"])


def _answer_performance(question: str) -> AnalystAnswer:
    perf = get_performance()
    search_campaign_id = "1000000001"
    search_rows = [row for row in perf if row["campaign_id"] == search_campaign_id]
    first_week = [row["cpa"] for row in search_rows[:7] if row["cpa"]]
    last_week = [row["cpa"] for row in search_rows[7:] if row["cpa"]]
    avg_first = sum(first_week) / len(first_week) if first_week else 0.0
    avg_last = sum(last_week) / len(last_week) if last_week else 0.0
    change_pct = ((avg_last - avg_first) / avg_first * 100) if avg_first else 0.0

    answer = (
        f"Search CPA moved from ${avg_first:.2f} (first week) to ${avg_last:.2f} "
        f"(most recent week), a {change_pct:+.1f}% change. Rising cost-per-click "
        "combined with a softer conversion rate is driving it -- check search terms "
        "for waste."
    )
    return AnalystAnswer(question=question, answer=answer, tools_used=["get_performance"])
