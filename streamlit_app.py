"""Local Streamlit UI for the MMM-powered Google Ads agent."""

from __future__ import annotations

import json
import os
import re

import streamlit as st
from dotenv import load_dotenv
from pydantic import ValidationError

from ads_agent.analyst_agent import ask_analyst
from ads_agent.analyst_tools import list_campaigns
from ads_agent.audit import write_audit_event
from ads_agent.google_ads_client import get_ads_client
from ads_agent.guardrails import GuardrailError
from ads_agent.meta_ads_client import get_meta_ads_client
from ads_agent.meta_planner import generate_meta_campaign_plan
from ads_agent.meta_schemas import MetaCampaignPlan
from ads_agent.operator_agent import propose_change
from ads_agent.planner import generate_campaign_plan
from ads_agent.schemas import CampaignPlan, ChangeAction


load_dotenv()


def _max_daily_budget() -> float:
    return float(os.getenv("MAX_DAILY_BUDGET_USD", "1000"))


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
        st.write(edited_plan.executive_summary)
        st.markdown("**MMM budget logic**")
        st.write(edited_plan.mmm_summary)

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
                client = get_ads_client()
                if ticket.action == ChangeAction.UPDATE_BUDGET:
                    current = next(c for c in list_campaigns() if c["id"] == ticket.campaign_id)
                    new_budget = float(re.sub(r"[^0-9.]", "", ticket.proposed_value))
                    result = client.update_campaign_budget(
                        campaign_id=ticket.campaign_id,
                        campaign_name=ticket.campaign_name,
                        current_daily_budget=current["daily_budget"],
                        new_daily_budget=new_budget,
                        max_daily_budget=_max_daily_budget(),
                    )
                elif ticket.action == ChangeAction.PAUSE_CAMPAIGN:
                    result = client.pause_campaign(
                        campaign_id=ticket.campaign_id, campaign_name=ticket.campaign_name
                    )
                else:
                    result = client.add_negative_keyword(
                        campaign_id=ticket.campaign_id,
                        campaign_name=ticket.campaign_name,
                        keyword_text=ticket.proposed_value,
                    )
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
        st.write(edited_meta_plan.executive_summary)
        st.markdown("**MMM budget logic**")
        st.write(edited_meta_plan.mmm_summary)

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
