"""Local Streamlit UI for the MMM-powered Google Ads agent."""

from __future__ import annotations

import json
import os

import streamlit as st
from dotenv import load_dotenv
from pydantic import ValidationError

from ads_agent.analyst_agent import ask_analyst
from ads_agent.apply_change import apply_change_ticket
from ads_agent.audit import write_audit_event
from ads_agent.google_ads_client import get_ads_client
from ads_agent.guardrails import GuardrailError
from ads_agent.meta_ads_client import get_meta_ads_client
from ads_agent.meta_planner import generate_meta_campaign_plan
from ads_agent.meta_schemas import MetaCampaignPlan
from ads_agent.operator_agent import monitor_and_propose, propose_change
from ads_agent.planner import generate_campaign_plan
from ads_agent.schemas import CampaignPlan
from ads_agent.simulation_state import advance_simulated_day, get_simulated_day, reset_simulation


load_dotenv()


def _max_daily_budget() -> float:
    return float(os.getenv("MAX_DAILY_BUDGET_USD", "1000"))


def _display_text(text: str) -> None:
    """st.write() renders markdown, and markdown treats a pair of "$" as
    inline LaTeX -- LLM-generated summaries routinely contain two dollar
    amounts (e.g. "$50.00/day... $307,995/week"), which get silently parsed
    as a math expression instead of displayed as text. Escaping "$" avoids
    that without giving up markdown for any other formatting the text uses.
    """

    st.write(text.replace("$", "\\$"))


def _plan_to_json(plan: CampaignPlan) -> str:
    return plan.model_dump_json(indent=2)


def _plan_from_json(raw: str) -> CampaignPlan:
    return CampaignPlan.model_validate_json(raw)


def _meta_plan_to_json(plan: MetaCampaignPlan) -> str:
    return plan.model_dump_json(indent=2)


def _meta_plan_from_json(raw: str) -> MetaCampaignPlan:
    return MetaCampaignPlan.model_validate_json(raw)


st.set_page_config(page_title="MMM Google Ads Agent", layout="wide")
st.title("MMM Google Ads Agent")

st.caption(
    "Portfolio demo: MMM sets the digital budget envelope; the agent drafts "
    "Search and PMax campaigns with human approval before any action."
)

with st.sidebar:
    st.header("Safety")
    st.write(f"Max daily budget cap: `${_max_daily_budget():,.0f}`")
    st.write(f"Google Ads mutate enabled: `{os.getenv('GOOGLE_ADS_MUTATE_ENABLED', 'false')}`")
    st.write("Default mode is mock. Real campaigns are never enabled at creation.")

col_a, col_b = st.columns(2)
with col_a:
    business_name = st.text_input("Business name", value="Anonymized Retailer")
    total_daily_budget = st.number_input(
        "Total Google Ads daily budget",
        min_value=1.0,
        max_value=_max_daily_budget(),
        value=100.0,
        step=10.0,
    )
    landing_page_url = st.text_input("Landing page URL", value="https://example.com")

with col_b:
    product_category = st.text_input("Product category", value="retail products")
    offer = st.text_input("Offer or campaign angle", value="seasonal value offers")
    geo_target = st.text_input("Geo target", value="United States")
    language = st.text_input("Language", value="English")

if "plan_json" not in st.session_state:
    st.session_state.plan_json = ""

if st.button("Generate plan", type="primary"):
    try:
        plan = generate_campaign_plan(
            business_name=business_name,
            total_daily_budget=float(total_daily_budget),
            landing_page_url=landing_page_url,
            product_category=product_category,
            offer=offer,
            geo_target=geo_target,
            language=language,
        )
        st.session_state.plan_json = _plan_to_json(plan)
        write_audit_event("plan_generated", plan.model_dump())
        st.success("Campaign plan generated.")
    except (ValidationError, ValueError) as exc:
        st.error(f"Could not generate a valid campaign plan: {exc}")

if st.session_state.plan_json:
    st.subheader("Agent rationale and editable campaign plan")
    edited_json = st.text_area(
        "Edit the JSON before approval",
        value=st.session_state.plan_json,
        height=520,
    )

    try:
        edited_plan = _plan_from_json(edited_json)
        st.session_state.plan_json = edited_json

        st.markdown("**Executive summary**")
        _display_text(edited_plan.executive_summary)
        st.markdown("**MMM budget logic**")
        _display_text(edited_plan.mmm_summary)

        rows = [
            {
                "campaign": campaign.name,
                "type": campaign.campaign_type.value,
                "budget": campaign.daily_budget,
                "status": campaign.status.value,
                "bid_strategy": campaign.bid_strategy,
                "editable": ", ".join(campaign.editable_parameters),
            }
            for campaign in edited_plan.campaigns
        ]
        st.dataframe(rows, use_container_width=True)

        col_create, col_enable = st.columns(2)
        with col_create:
            if st.button("Create paused campaigns"):
                try:
                    result = get_ads_client().create_paused_campaigns(
                        edited_plan,
                        max_daily_budget=_max_daily_budget(),
                    )
                    st.success(result.message)
                    st.json(result.operations)
                except (GuardrailError, RuntimeError, NotImplementedError) as exc:
                    st.error(str(exc))

        with col_enable:
            if st.button("Enable after approval"):
                try:
                    result = get_ads_client().enable_campaigns(edited_plan)
                    st.warning(result.message)
                    st.json(result.operations)
                except (GuardrailError, RuntimeError, NotImplementedError) as exc:
                    st.error(str(exc))

        with st.expander("Raw validated plan"):
            st.json(json.loads(edited_plan.model_dump_json()))

    except ValidationError as exc:
        st.error(f"Edited JSON is not valid yet: {exc}")

st.divider()
st.subheader("Ask the analyst (Phase 2, read-only)")
st.caption(
    "Ask a question about campaign performance. The agent decides which read-only "
    "tool to call (list campaigns, performance, search terms, or budget pacing) -- "
    "it has no ability to change anything. Backed by mock data until Google's Basic "
    "access review is approved."
)

example_questions = [
    "Why did CPA rise last week?",
    "How is budget pacing looking?",
    "Which search terms are wasting spend?",
]
example_cols = st.columns(len(example_questions))
if "analyst_question" not in st.session_state:
    st.session_state.analyst_question = ""
for col, example in zip(example_cols, example_questions):
    if col.button(example):
        st.session_state.analyst_question = example

question = st.text_input("Your question", key="analyst_question")

if st.button("Ask", type="primary") and question.strip():
    with st.spinner("Analyst is checking the numbers..."):
        result = ask_analyst(question)
    st.markdown(f"**Tools used:** {', '.join(result.tools_used) or 'none'}")
    st.text(result.answer)

st.divider()
st.subheader("Operator (Phase 3, write with approval gate)")
st.caption(
    "Propose a change in plain English. The agent only ever drafts a change "
    "ticket -- nothing is applied until you click Approve below. Budget caps, "
    "a daily rate limit, and an action allowlist are enforced in code, not "
    "the prompt, so the agent can't talk its way past them."
)

operator_examples = [
    "Cut the search campaign budget, it's overspending",
    "Pause the PMax campaign",
    "Add a negative keyword for the wasteful search term",
]
operator_example_cols = st.columns(len(operator_examples))
if "operator_request" not in st.session_state:
    st.session_state.operator_request = ""
for col, example in zip(operator_example_cols, operator_examples):
    if col.button(example, key=f"operator_example_{example}"):
        st.session_state.operator_request = example

operator_request = st.text_input("Your request", key="operator_request")

if "change_ticket" not in st.session_state:
    st.session_state.change_ticket = None

if st.button("Propose change", type="primary") and operator_request.strip():
    with st.spinner("Drafting a change ticket..."):
        st.session_state.change_ticket = propose_change(operator_request)

if st.session_state.change_ticket:
    ticket = st.session_state.change_ticket
    st.markdown("**Proposed change -- not yet applied**")
    st.json(ticket.model_dump())

    col_approve, col_reject = st.columns(2)
    with col_approve:
        if st.button("Approve and apply", type="primary"):
            try:
                result = apply_change_ticket(ticket, _max_daily_budget())
                st.success(result.message)
                st.json(result.operations)
                st.session_state.change_ticket = None
            except (GuardrailError, RuntimeError, NotImplementedError, StopIteration) as exc:
                st.error(str(exc))

    with col_reject:
        if st.button("Reject"):
            st.session_state.change_ticket = None
            st.info("Change rejected -- nothing was applied.")

st.divider()
st.subheader("Simulated optimizer loop (Phase 5, synthetic data only)")
st.caption(
    "No real ad spend involved -- this advances an independent simulated-day "
    "clock (ads_agent/simulation_state.py) through a scripted 14-scenario "
    "ladder (a healthy baseline, real problems like a CPA spike or a wasteful "
    "keyword, restraint traps like a near-miss ratio or normal Google Ads "
    "overdelivery, and data-integrity edge cases like missing data or a "
    "prompt-injection attempt), calling the operator agent proactively each "
    "day the same way a scheduled Cloud Scheduler run eventually would "
    "against a real account. It still only *proposes* -- the same "
    "Approve/Reject gate as Phase 3 above, nothing auto-applies. See "
    "`ads_agent/evals.py` for the eval harness that scores these decisions."
)

st.write(f"Simulated day: **{get_simulated_day()}**")
sim_col_advance, sim_col_reset = st.columns(2)
with sim_col_advance:
    if st.button("Advance 1 day"):
        advance_simulated_day()
        st.session_state.sim_change_ticket = None
        st.session_state.sim_summary = None
        st.rerun()  # otherwise the "Simulated day" line above already rendered
        # this pass, using the pre-increment value -- Streamlit reruns
        # top-to-bottom, so without this the display lags one click behind.
with sim_col_reset:
    if st.button("Reset simulation"):
        reset_simulation()
        st.session_state.sim_change_ticket = None
        st.session_state.sim_summary = None
        st.rerun()

if "sim_change_ticket" not in st.session_state:
    st.session_state.sim_change_ticket = None
if "sim_summary" not in st.session_state:
    st.session_state.sim_summary = None

if st.button("Check account (run monitor_and_propose)", type="primary"):
    with st.spinner("Checking synthetic account state..."):
        monitoring_result = monitor_and_propose()
    st.session_state.sim_summary = monitoring_result.summary
    st.session_state.sim_change_ticket = monitoring_result.ticket

if st.session_state.sim_summary:
    escaped_sim_summary = st.session_state.sim_summary.replace("$", "\\$")
    st.markdown(f"**Monitoring summary:** {escaped_sim_summary}")

if st.session_state.sim_change_ticket:
    sim_ticket = st.session_state.sim_change_ticket
    st.markdown("**Proposed change -- not yet applied**")
    st.json(sim_ticket.model_dump())

    sim_col_approve, sim_col_reject = st.columns(2)
    with sim_col_approve:
        if st.button("Approve and apply", key="sim_approve", type="primary"):
            try:
                result = apply_change_ticket(sim_ticket, _max_daily_budget())
                st.success(result.message)
                st.json(result.operations)
                st.session_state.sim_change_ticket = None
            except (GuardrailError, RuntimeError, NotImplementedError, StopIteration) as exc:
                st.error(str(exc))
    with sim_col_reject:
        if st.button("Reject", key="sim_reject"):
            st.session_state.sim_change_ticket = None
            st.info("Change rejected -- nothing was applied.")

st.divider()
st.subheader("Meta Ads (Phase 6)")
st.caption(
    "Activates the MMM's `social` channel recommendation ($307,995/week, +75% vs. "
    "current -- the strongest growth signal of any channel), which the Google Ads "
    "flow above never touches. Same paused-only, human-approval pattern as Google "
    "Ads. Campaign, Ad Set, and Ad Creative creation are live-verified against a "
    "real Meta ad account; final Ad-object creation is code-complete but blocked "
    "on a payment-method/region requirement outside this codebase's control (see "
    "META_ADS_AGENT_PLAN.md). Defaults to mock mode everywhere this UI runs."
)

with st.sidebar:
    st.write(f"Meta Ads mutate enabled: `{os.getenv('META_ADS_MUTATE_ENABLED', 'false')}`")

meta_col_a, meta_col_b = st.columns(2)
with meta_col_a:
    meta_business_name = st.text_input("Business name (Meta)", value=business_name, key="meta_business_name")
    meta_total_daily_budget = st.number_input(
        "Total Meta Ads daily budget",
        min_value=1.0,
        max_value=_max_daily_budget(),
        value=50.0,
        step=10.0,
    )
    meta_landing_page_url = st.text_input(
        "Landing page URL (Meta)", value=landing_page_url, key="meta_landing_page_url"
    )

with meta_col_b:
    meta_product_category = st.text_input(
        "Product category (Meta)", value=product_category, key="meta_product_category"
    )
    meta_offer = st.text_input("Offer or campaign angle (Meta)", value=offer, key="meta_offer")
    meta_geo_target = st.text_input("Geo target (Meta)", value=geo_target, key="meta_geo_target")

if "meta_plan_json" not in st.session_state:
    st.session_state.meta_plan_json = ""

if st.button("Generate Meta plan", type="primary"):
    try:
        meta_plan = generate_meta_campaign_plan(
            business_name=meta_business_name,
            total_daily_budget=float(meta_total_daily_budget),
            landing_page_url=meta_landing_page_url,
            product_category=meta_product_category,
            offer=meta_offer,
            geo_target=meta_geo_target,
        )
        st.session_state.meta_plan_json = _meta_plan_to_json(meta_plan)
        write_audit_event("meta_plan_generated", meta_plan.model_dump())
        st.success("Meta campaign plan generated.")
    except (ValidationError, ValueError) as exc:
        st.error(f"Could not generate a valid Meta campaign plan: {exc}")

if st.session_state.meta_plan_json:
    st.subheader("Agent rationale and editable Meta campaign plan")
    edited_meta_json = st.text_area(
        "Edit the Meta plan JSON before approval",
        value=st.session_state.meta_plan_json,
        height=420,
    )

    try:
        edited_meta_plan = _meta_plan_from_json(edited_meta_json)
        st.session_state.meta_plan_json = edited_meta_json

        st.markdown("**Executive summary**")
        _display_text(edited_meta_plan.executive_summary)
        st.markdown("**MMM budget logic**")
        _display_text(edited_meta_plan.mmm_summary)

        meta_rows = [
            {
                "campaign": campaign.name,
                "objective": campaign.objective.value,
                "budget": campaign.daily_budget,
                "status": campaign.status.value,
                "editable": ", ".join(campaign.editable_parameters),
            }
            for campaign in edited_meta_plan.campaigns
        ]
        st.dataframe(meta_rows, use_container_width=True)

        meta_col_create, meta_col_enable = st.columns(2)
        with meta_col_create:
            if st.button("Create paused Meta campaigns"):
                try:
                    result = get_meta_ads_client().create_paused_campaigns(
                        edited_meta_plan,
                        max_daily_budget=_max_daily_budget(),
                    )
                    st.success(result.message)
                    st.json(result.operations)
                except (GuardrailError, RuntimeError, NotImplementedError) as exc:
                    st.error(str(exc))

        with meta_col_enable:
            if st.button("Enable Meta campaigns after approval"):
                try:
                    result = get_meta_ads_client().enable_campaigns(edited_meta_plan)
                    st.warning(result.message)
                    st.json(result.operations)
                except (GuardrailError, RuntimeError, NotImplementedError) as exc:
                    st.error(str(exc))

        with st.expander("Raw validated Meta plan"):
            st.json(json.loads(edited_meta_plan.model_dump_json()))

    except ValidationError as exc:
        st.error(f"Edited Meta plan JSON is not valid yet: {exc}")
