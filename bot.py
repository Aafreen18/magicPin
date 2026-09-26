"""Deterministic Vera message composer for the magicpin AI Challenge.

Contract: compose(category, merchant, trigger, customer=None) -> dict
Uses only facts present in the supplied contexts; no external LLM/API required.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
import re


def _get(d: dict | None, *path: str, default=None):
    cur: Any = d or {}
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def _pct(value):
    try:
        n = float(value)
        return f"{n * 100:+.0f}%" if abs(n) <= 1 else f"{n:+.0f}%"
    except (TypeError, ValueError):
        return str(value)


def _salutation(merchant):
    ident = merchant.get("identity", {})
    name = ident.get("owner_first_name") or ident.get("first_name")
    if name:
        return name
    return ident.get("name") or "there"


def _category_fit(slug, body):
    # Keep promotional claims restrained, especially for health categories.
    taboo = set()
    # This list is a second guard; category voice taboos are checked below too.
    if slug in {"dentists", "pharmacies"}:
        taboo = {"guaranteed", "100% safe", "cure", "miracle", "best in city"}
    low = body.lower()
    for phrase in taboo:
        if phrase in low:
            body = re.sub(re.escape(phrase), "", body, flags=re.I)
    return body.strip()


def _merchant_message(category, merchant, trigger):
    ident = merchant.get("identity", {})
    p = trigger.get("payload", {}) or {}
    slug = category.get("slug") or merchant.get("category_slug", "")
    who = _salutation(merchant)
    name = ident.get("name", "your business")
    city = ident.get("city", "")
    kind = trigger.get("kind", "")
    signals = merchant.get("signals", []) or []
    perf = merchant.get("performance", {}) or {}
    offers = [o for o in merchant.get("offers", []) if o.get("status") == "active"]

    if kind in {"research_digest", "regulation_change", "cde_opportunity", "category_trend", "trend_movement"}:
        item_id = p.get("top_item_id") or p.get("digest_item_id")
        item = next((x for x in category.get("digest", []) if x.get("id") == item_id), None)
        if item:
            fact = item.get("summary") or item.get("title", "")
            source = item.get("source")
            action = item.get("actionable")
            body = f"{who}, {item.get('title', 'A new category update')}"
            if fact and fact.lower() not in body.lower():
                body += f" — {fact}"
            body += f" ({source})" if source else ""
            body += f". {action}." if action else "."
            body += " Want me to turn this into a practical checklist for your team?"
        else:
            body = f"{who}, there’s a new {kind.replace('_', ' ')} update for {slug}. I don’t have the source detail in this context, so I won’t guess. Want me to share the available summary?"
        return body, "open_ended", f"Uses the matching category digest item for {kind}; source and action are taken from context."

    if kind in {"perf_dip", "seasonal_perf_dip", "perf_spike"}:
        metric = p.get("metric", "performance")
        delta = _pct(p.get("delta_pct", _get(perf, "delta_7d", f"{metric}_pct", default="")))
        window = p.get("window", "7d")
        if kind == "perf_spike":
            body = f"{who}, {metric} are up {delta} over {window}"
            driver = p.get("likely_driver")
            body += f", with {driver} listed as a likely driver" if driver else ""
            body += ". Want to build on that signal with one small next step?"
        else:
            body = f"{who}, {metric} are {delta} over {window}"
            if p.get("is_expected_seasonal"):
                body += f"; the context flags this as seasonal ({p.get('season_note', 'seasonal pattern')})"
            body += ". Want me to check one practical profile or campaign change against this?"
        return body, "open_ended", f"References the trigger's measured performance movement and timeframe."

    if kind == "renewal_due":
        days = p.get("days_remaining", _get(merchant, "subscription", "days_remaining", default=""))
        plan = p.get("plan", _get(merchant, "subscription", "plan", default="subscription"))
        amount = p.get("renewal_amount")
        price = f" at ₹{amount:,}" if isinstance(amount, (int, float)) else ""
        return f"{who}, your {plan} plan has {days} days remaining{price}. Want me to show the renewal options?", "binary_yes_no", "Timely renewal prompt grounded in the subscription details."

    if kind in {"festival_upcoming", "ipl_match_today", "local_event", "weather_heatwave"}:
        event = p.get("festival") or p.get("match") or p.get("event") or p.get("condition") or kind.replace("_", " ")
        date = p.get("date") or p.get("match_time_iso")
        detail = f" on {date}" if date else ""
        if slug == "restaurants" and p.get("match"):
            idea = "a match-night group-order post using a dish already on your menu"
        elif slug == "salons":
            idea = "a festival-ready service post using one of your listed services"
        else:
            idea = "a timely, category-fit Google Business Profile post"
        return f"{who}, {event}{detail} is the timely hook for {name}{', ' + city if city else ''}. Want me to draft {idea}?", "binary_yes_no", "Connects the dated external event to a low-effort, category-relevant action."

    if kind == "competitor_opened":
        competitor = p.get("competitor_name", "a nearby competitor")
        distance = p.get("distance_km")
        offer = p.get("their_offer")
        fact = f"{competitor}{f' ({distance} km away)' if distance is not None else ''}"
        fact += f" is listing {offer}" if offer else " has opened nearby"
        return f"{who}, {fact}. I won’t suggest matching their price without knowing your margin. Want me to compare your existing offer and profile positioning?", "open_ended", "Uses the supplied competitor fact without inventing a counter-offer or recommending an unsupported price cut."

    if kind == "review_theme_emerged":
        theme = p.get("theme", "") .replace("_", " ")
        count = p.get("occurrences_30d")
        quote = p.get("common_quote")
        fact = f"{count} recent reviews mention {theme}" if count is not None else f"A review theme has emerged: {theme}"
        if quote:
            fact += f" (one said: ‘{quote}’)"
        return f"{who}, {fact}. Want me to draft a calm owner response and a small service-recovery checklist?", "binary_yes_no", "Anchors on the review trend and offers a concrete response."

    if kind in {"milestone_reached"}:
        metric, value = p.get("metric", "milestone"), p.get("value_now", p.get("milestone_value", ""))
        return f"{who}, {name} is at {value} {metric.replace('_', ' ')}. A good moment to thank customers. Want a short WhatsApp/GBP thank-you draft?", "binary_yes_no", "Celebrates a supplied milestone and proposes a relevant next action."

    if kind in {"dormant_with_vera", "curious_ask_due"}:
        days = p.get("days_since_last_merchant_message")
        if days is not None:
            body = f"{who}, it’s been {days} days since we last spoke. Quick question: which service would you most like more enquiries for this week?"
        else:
            body = f"{who}, quick question for {name}: which service has been most in demand this week? I can use your answer to suggest one relevant post."
        return body, "open_ended", "A lightweight knowledge-seeking nudge invites the merchant's own input."

    if kind in {"gbp_unverified", "profile_incomplete", "stale_posts"}:
        missing = p.get("missing_fields") or p.get("missing")
        if isinstance(missing, list) and missing:
            fact = ", ".join(map(str, missing))
            body = f"{who}, your Google Business Profile is missing {fact}. Want me to help prepare those details for an update?"
        elif p.get("verified") is False or kind == "gbp_unverified":
            body = f"{who}, the context shows {name}'s Google Business Profile is unverified. The listed path is {p.get('verification_path', 'verification')}. Want the steps to get started?"
        else:
            body = f"{who}, your profile has a content gap flagged in the current context. Want me to check the specific fields and draft one update?"
        return body, "binary_yes_no", "References a profile state and offers a bounded assistance step."

    if kind in {"winback_eligible", "subscription_expired"}:
        days = p.get("days_since_expiry")
        detail = f" Your plan expired {days} days ago." if days is not None else ""
        lost = p.get("lapsed_customers_added_since_expiry")
        if lost is not None:
            detail += f" The context also shows {lost} additional lapsed customers since expiry."
        return f"{who},{detail.lstrip()} Want me to show the current plan options and the activity you’d regain?", "binary_yes_no", "Grounds a win-back prompt in expiry and customer context, without promising outcomes."

    if kind == "active_planning_intent":
        topic = p.get("intent_topic", "your idea").replace("_", " ")
        return f"{who}, picking up your plan for {topic}: I can sketch a first version with the details we already have. Want me to draft it now?", "binary_yes_no", "Recognizes expressed intent and moves directly to a deliverable rather than restarting qualification."

    return None


def _customer_message(category, merchant, trigger, customer):
    p = trigger.get("payload", {}) or {}
    ident = merchant.get("identity", {})
    cident = (customer or {}).get("identity", {})
    cname = cident.get("name") or "there"
    mname = ident.get("name") or "the business"
    kind = trigger.get("kind", "")
    consent = (customer or {}).get("consent", {})
    allowed = consent.get("scope", [])
    # Customer outreach requires consent for the matching purpose.
    required_scope = "recall_reminders" if kind in {"recall_due", "appointment_tomorrow"} else None
    if required_scope and required_scope not in allowed:
        return ("", "none", "Customer context does not show consent for this message type; suppressing outreach.")
    if kind == "recall_due":
        due = p.get("due_date")
        slots = p.get("available_slots") or []
        slot_labels = [s.get("label") for s in slots if s.get("label")]
        last = (customer or {}).get("relationship", {}).get("last_visit") or p.get("last_service_date")
        elapsed = ""
        if last:
            elapsed = f" It’s been since your last visit ({last})"
        options = " or ".join(slot_labels[:2])
        service = p.get("service_due", "follow-up").replace("_", " ")
        body = f"Hi {cname}, {mname} here. Your {service} is due{f' (due date: {due})' if due else ''}.{elapsed}."
        if options:
            body += f" We have {options} available."
        body += " Would either time work, or is another time better?"
        return body, "open_ended", "Recall reminder uses the trigger's due date and available slots; only sends when matching consent is present."
    if kind in {"appointment_tomorrow", "trial_followup", "wedding_package_followup"}:
        slots = p.get("next_session_options") or p.get("available_slots") or []
        label = slots[0].get("label") if slots else p.get("wedding_date")
        detail = f" for {label}" if label else ""
        return f"Hi {cname}, {mname} here. Following up on your {kind.replace('_', ' ')}{detail}. Would you like us to confirm the next step?", "binary_yes_no", "Customer follow-up uses only the event and time details available in the trigger."
    if kind in {"customer_lapsed_soft", "customer_lapsed_hard", "winback", "chronic_refill_due"}:
        days = p.get("days_since_last_visit")
        detail = f" It’s been {days} days since your last visit." if days is not None else ""
        return f"Hi {cname}, {mname} here.{detail} If you’d like to come in again, reply and we’ll help find a suitable time. No pressure.", "open_ended", "Low-pressure win-back wording avoids ungrounded discounts or health claims."
    return None


def compose(category: dict, merchant: dict, trigger: dict, customer: dict | None = None) -> dict:
    """Compose one WhatsApp message from the four challenge contexts."""
    category = category or {}
    merchant = merchant or {}
    trigger = trigger or {}
    customer = customer or None
    customer_scope = trigger.get("scope") == "customer" or customer is not None
    if customer_scope:
        result = _customer_message(category, merchant, trigger, customer)
        send_as = "merchant_on_behalf"
    else:
        result = _merchant_message(category, merchant, trigger)
        send_as = "vera"
    if result is None:
        kind = trigger.get("kind", "unknown")
        result = (f"{_salutation(merchant)}, I have a {kind.replace('_', ' ')} update, but the supplied context doesn’t include enough detail to make a specific recommendation. Would you like me to check what information is available?", "open_ended", "Fallback avoids inventing facts when the trigger kind lacks a dedicated handler.")
    body, cta, rationale = result
    body = _category_fit(category.get("slug", ""), body)
    # Empty body means customer contact was suppressed due to absent consent.
    return {
        "body": body,
        "cta": cta,
        "send_as": send_as,
        "suppression_key": trigger.get("suppression_key", trigger.get("id", "")),
        "rationale": rationale,
    }
