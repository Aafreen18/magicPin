"""Context-grounded deterministic message composition for magicpin's Vera challenge."""
from __future__ import annotations

import re
from typing import Any


def get(data: dict | None, *path: str, default=None):
    cur: Any = data or {}
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def _first(*values, default=""):
    return next((v for v in values if v is not None and v != ""), default)


def _human(value):
    return str(value).replace("_", " ").strip() if value is not None else ""


def _percent(value):
    try:
        n = float(value)
        return f"{n * 100:+.0f}%" if abs(n) <= 1 else f"{n:+.0f}%"
    except (TypeError, ValueError):
        return str(value or "")


def _owner_name(merchant):
    ident = merchant.get("identity", {}) or {}
    owner = _first(ident.get("owner_first_name"), ident.get("first_name"))
    if owner:
        return owner
    name = ident.get("name") or "your business"
    return name


def _digest_item(category, payload):
    items = category.get("digest", []) or []
    ids = [payload.get(k) for k in ("top_item_id", "digest_item_id", "item_id", "alert_id")]
    for item_id in ids:
        if item_id:
            item = next((x for x in items if x.get("id") == item_id), None)
            if item:
                return item
    kind = payload.get("item_kind")
    if kind:
        return next((x for x in items if x.get("kind") == kind), None)
    return None


def _active_offer(merchant):
    return next((o for o in (merchant.get("offers", []) or [])
                 if str(o.get("status", "")).lower() in {"active", "live"}), None)


def _merchant_message(category, merchant, trigger):
    ident = merchant.get("identity", {}) or {}
    perf = merchant.get("performance", {}) or {}
    aggregate = merchant.get("customer_aggregate", {}) or {}
    payload = trigger.get("payload", {}) or {}
    kind = trigger.get("kind", "unknown")
    slug = category.get("slug") or merchant.get("category_slug", "business")
    owner = _owner_name(merchant)
    business = ident.get("name") or "your business"
    city = ident.get("city")
    locality = ident.get("locality")
    place = ", ".join(x for x in (locality, city) if x)
    offers = [o.get("title") for o in (merchant.get("offers", []) or [])
              if str(o.get("status", "")).lower() in {"active", "live"} and o.get("title")]
    offer = offers[0] if offers else None
    item = _digest_item(category, payload)

    if kind in {"research_digest", "regulation_change", "cde_opportunity", "category_trend", "trend_movement"}:
        if item:
            title = item.get("title") or "A new category update"
            summary = item.get("summary")
            source = item.get("source")
            actionable = item.get("actionable")
            if kind == "regulation_change":
                deadline = payload.get("deadline_iso") or item.get("effective_date")
                timing = f" Effective {deadline}." if deadline else ""
                body = f"{owner}, {title}.{timing}"
            elif kind == "cde_opportunity":
                date = item.get("date")
                credits = payload.get("credits", item.get("credits"))
                fee = payload.get("fee") or item.get("fee")
                details = "; ".join(x for x in [f"{credits} credits" if credits else None, _human(fee) if fee else None] if x)
                body = f"{owner}, {title}{f' on {date}' if date else ''}{f' ({details})' if details else ''}."
            else:
                body = f"{owner}, {title}."
            if summary and summary.lower() not in title.lower():
                body += f" {summary}"
            if source:
                body += f" Source: {source}."
            if actionable:
                body += f" {actionable}."
            if kind == "research_digest" and aggregate.get("high_risk_adult_count"):
                body += f" This may be relevant to your {aggregate['high_risk_adult_count']} high-risk adult patients."
            body += " Want me to prepare a short practical summary?"
        else:
            signals = category.get("trend_signals", []) or []
            query = payload.get("query") or payload.get("trend")
            signal = next((x for x in signals if query and query.lower() in str(x.get("query", "")).lower()), None)
            if signal:
                growth = signal.get("delta_yoy")
                change = _percent(growth) if growth is not None else ""
                body = f"{owner}, searches for {signal.get('query')} {f'are up {change} year over year' if change else 'are trending'}"
                if signal.get("segment_age"):
                    body += f" among {signal['segment_age']} customers"
                body += ". Want me to tailor your profile copy to this demand?"
            else:
                body = f"{owner}, there’s a {kind.replace('_', ' ')} update for {slug}, but its source detail isn’t in the supplied context. Want me to check the available details?"
        return body, "open_ended", f"Uses the matching digest, trend signal, source, and merchant context for {kind}."

    if kind in {"perf_dip", "perf_spike", "seasonal_perf_dip"}:
        metric = _human(payload.get("metric") or "views")
        delta_raw = payload.get("delta_pct")
        if delta_raw is None:
            delta_raw = get(perf, "delta_7d", f"{metric}_pct", default=None)
        delta = _percent(delta_raw) if delta_raw is not None else None
        window = payload.get("window") or "7d"
        current = perf.get(metric.replace(" ", "_"))
        peer = category.get("peer_stats", {}) or {}
        peer_field = {"views": "avg_views_30d", "calls": "avg_calls_30d", "directions": "avg_directions_30d"}.get(metric)
        peer_value = peer.get(peer_field) if peer_field else None
        if kind == "perf_spike":
            fact = f"{metric} are up {delta} over {window}" if delta else f"{metric} reached {current}" if current is not None else f"there’s a positive {metric} signal"
            driver = payload.get("likely_driver")
            body = f"{owner}, {fact}{f', with {driver} listed as a likely driver' if driver else ''}. Want to see what to repeat?"
        else:
            try:
                numeric_delta = float(delta_raw) if delta_raw is not None else None
            except (TypeError, ValueError):
                numeric_delta = None
            fact = f"{metric} are down {abs(numeric_delta)*100:.0f}% over {window}" if numeric_delta is not None and abs(numeric_delta) <= 1 else f"{metric} are down {delta}" if delta else f"{metric} changed in the latest snapshot"
            if current is not None:
                fact += f"; your current {metric} count is {current}"
            if peer_value is not None:
                fact += f"; category benchmark is {peer_value}"
            season = payload.get("season_note")
            if payload.get("is_expected_seasonal") and season:
                fact += f" ({_human(season)})"
            body = f"{owner}, {fact}. Want me to identify one profile change to investigate?"
        return body, "open_ended", "Connects the performance movement to actual merchant and category benchmark data when present."

    if kind == "renewal_due":
        sub = merchant.get("subscription", {}) or {}
        days = _first(payload.get("days_remaining"), sub.get("days_remaining"), default="")
        plan = _first(payload.get("plan"), sub.get("plan"), default="plan")
        amount = payload.get("renewal_amount")
        price = f" at ₹{amount:,}" if isinstance(amount, (int, float)) else ""
        return f"{owner}, your {plan} plan has {days} days remaining{price}. Want me to show the renewal options?", "binary_yes_no", "Uses the provided plan, remaining days, and renewal amount."

    if kind in {"festival_upcoming", "ipl_match_today", "local_news_event", "weather_heatwave", "local_event"}:
        event = _first(payload.get("festival"), payload.get("match"), payload.get("headline"), payload.get("event"), payload.get("condition"), default=_human(kind))
        when = _first(payload.get("date"), payload.get("match_time_iso"), payload.get("when"))
        event_place = payload.get("city") or place
        details = "; ".join(x for x in [when, event_place] if x)
        if slug == "restaurants":
            idea = f"a post featuring {offer}" if offer else "a timely menu or group-order post"
        elif slug == "salons":
            idea = f"a post featuring {offer}" if offer else "a timely service post"
        else:
            idea = "a timely Google Business Profile post"
        return f"{owner}, {event}{f' ({details})' if details else ''} is the timely hook. Want me to draft {idea}?", "binary_yes_no", "Uses the event timing and the merchant’s category and active offer where available."

    if kind == "competitor_opened":
        competitor = payload.get("competitor_name") or "A nearby competitor"
        distance = payload.get("distance_km")
        competitor_offer = payload.get("their_offer")
        fact = f"{competitor}{f' opened {distance} km away' if distance is not None else ' opened nearby'}"
        if competitor_offer:
            fact += f" with {competitor_offer}"
        own = f" Your current offer is {offer}." if offer else ""
        return f"{owner}, {fact}.{own} Want me to compare the positioning without assuming you should cut your price?", "open_ended", "Compares the supplied competitor fact with this merchant’s active offer without inventing a discount."

    if kind == "review_theme_emerged":
        theme = _human(payload.get("theme") or "customer feedback")
        count = payload.get("occurrences_30d")
        quote = payload.get("common_quote")
        review = f"{count} reviews in 30 days mention {theme}" if count is not None else f"A review theme has emerged around {theme}"
        if payload.get("trend"):
            review += f"; trend is {_human(payload['trend'])}"
        if quote:
            review += f". One customer wrote: ‘{quote}’"
        return f"{owner}, {review}. Want me to draft a measured owner response?", "binary_yes_no", "Uses the review count, theme, trend, and sample quote from the trigger."

    if kind == "milestone_reached":
        metric = _human(payload.get("metric") or "milestone")
        value = payload.get("value_now", payload.get("milestone_value"))
        if value is None:
            value = "a new milestone"
        imminent = payload.get("is_imminent")
        return f"{owner}, {business} has reached {value} {metric}{'—almost at the next milestone' if imminent else ''}. Want a short thank-you draft for customers?", "binary_yes_no", "Celebrates the metric and value supplied in the trigger."

    if kind in {"dormant_with_vera", "curious_ask_due"}:
        days = payload.get("days_since_last_merchant_message")
        service_options = [x.get("title") for x in category.get("offer_catalog", [])[:3] if x.get("title")]
        subject = f"which of these is getting the most enquiries: {', '.join(service_options)}" if service_options else "which service has been most in demand this week"
        opening = f"It’s been {days} days since we last spoke. " if days is not None else ""
        last_topic = payload.get("last_topic")
        context_note = f" Last time we discussed { _human(last_topic)}." if last_topic else ""
        return f"{owner}, {opening}{context_note}Quick question: {subject}? I can use your answer to suggest one relevant update.", "open_ended", "Uses the cadence trigger and category service catalog to ask a low-effort, useful question."

    if kind in {"gbp_unverified", "profile_incomplete", "stale_posts"}:
        missing = payload.get("missing_fields") or payload.get("missing")
        if isinstance(missing, list) and missing:
            fact = f"missing {', '.join(map(str, missing))}"
        elif payload.get("verified") is False or kind == "gbp_unverified":
            fact = f"marked unverified; the listed path is {_human(payload.get('verification_path') or 'Google verification')}"
        else:
            stale = next((s for s in (merchant.get("signals", []) or []) if "stale_posts" in str(s)), None)
            fact = f"has a content gap ({stale})" if stale else "has a profile update due"
        return f"{owner}, {business}’s Google profile is {fact}. Want me to prepare the next update?", "binary_yes_no", "Uses the profile state or signal present in the trigger or merchant context."

    if kind in {"winback_eligible", "subscription_expired"}:
        days = payload.get("days_since_expiry")
        added = payload.get("lapsed_customers_added_since_expiry")
        pieces = []
        if days is not None:
            pieces.append(f"your plan expired {days} days ago")
        if added is not None:
            pieces.append(f"{added} more customers are now marked lapsed")
        if not pieces:
            pieces.append("your account is eligible for a check-in")
        return f"{owner}, {', and '.join(pieces)}. Want me to review the current options with you?", "binary_yes_no", "Bases the win-back prompt on the expiry and customer activity facts supplied."

    if kind == "active_planning_intent":
        topic = _human(payload.get("intent_topic") or "your plan")
        prior = payload.get("merchant_last_message")
        return f"{owner}, picking up your plan for {topic}. I’ll draft a first version using the details we have{f' (your note: “{prior}”)' if prior else ''}. Reply CONFIRM and I’ll show it here for review.", "binary_confirm_cancel", "Recognizes stated intent and moves directly to a concrete draft/action."

    if kind == "supply_alert":
        molecule = payload.get("molecule")
        batches = payload.get("affected_batches") or []
        manufacturer = payload.get("manufacturer")
        alert = f"{molecule} recall alert" if molecule else "a medicine supply alert"
        details = []
        if manufacturer:
            details.append(f"manufacturer {manufacturer}")
        if batches:
            details.append(f"affected batches {', '.join(map(str, batches))}")
        detail_text = f" ({'; '.join(details)})" if details else ""
        return f"{owner}, there’s a {alert}{detail_text}. Please verify the listed batches against the official notice before taking action. Want me to format a stock-check checklist?", "binary_yes_no", "Relays only the supplied alert identifiers and asks for verification, without giving patient treatment advice."

    if kind == "category_seasonal":
        trends = payload.get("trends") or []
        trend_text = ", ".join(map(str, trends[:4])) if trends else _human(payload.get("season") or "seasonal demand")
        season_key = _human(payload.get("season") or "").lower().split("_")[0]
        beat = next((b.get("note") for b in (category.get("seasonal_beats", []) or [])
                     if season_key and season_key in str(b.get("month_range", "")).lower()), None)
        if not beat and category.get("seasonal_beats"):
            beat = category["seasonal_beats"][0].get("note")
        action = "review shelf availability" if slug == "pharmacies" else "plan a category-relevant post"
        body = f"{owner}, the { _human(payload.get('season') or 'seasonal')} snapshot lists {trend_text}."
        if beat:
            body += f" Category note: {beat}."
        return f"{body} Want me to help you {action}?", "open_ended", "Combines trigger demand signals with the relevant category seasonal beat when available."

    # Data-driven fallback: use profile gaps, relative benchmarks, and existing offers.
    signals = [str(s) for s in (merchant.get("signals", []) or [])]
    if any("ctr_below_peer" in s for s in signals):
        ctr = perf.get("ctr")
        peer_ctr = (category.get("peer_stats", {}) or {}).get("avg_ctr")
        fact = f"your listing CTR is {float(ctr)*100:.1f}%" if isinstance(ctr, (int,float)) else "your listing CTR is below the peer signal"
        if isinstance(peer_ctr, (int,float)):
            fact += f" versus the category benchmark of {peer_ctr*100:.1f}%"
        offer_text = f" Your active offer is {offer}." if offer else ""
        return f"{owner}, {fact}.{offer_text} Want me to check which profile detail to improve first?", "open_ended", "Fallback uses merchant performance, peer benchmarks, and active offer where present."
    if offer:
        return f"{owner}, I see {offer} is active. Want me to suggest one category-fit way to feature it this week?", "open_ended", "Fallback anchors on the merchant’s active offer rather than inventing a promotion."
    return f"{owner}, I have a {kind.replace('_', ' ')} update, but the supplied context doesn’t include enough detail to make a specific recommendation. Want me to check what information is available?", "open_ended", "Fallback avoids inventing details absent from the context."


CONSENT_SCOPES = {
    "recall_due": ("recall_reminders",),
    "appointment_tomorrow": ("appointment_reminders",),
    "wedding_package_followup": ("bridal_package_followup",),
    "trial_followup": ("kids_program_updates", "program_updates"),
    "customer_lapsed_hard": ("winback_offers", "renewal_reminders"),
    "customer_lapsed_soft": ("promotional_offers", "recall_reminders"),
    "chronic_refill_due": ("refill_reminders",),
    "customer_research_digest": ("health_content", "seasonal_health_content"),
    "patient_content_share": ("health_content", "seasonal_health_content"),
    "patient_content_due": ("health_content", "seasonal_health_content"),
}


def _customer_message(category, merchant, trigger, customer):
    if not customer:
        return "", "none", "Customer context is missing; suppressing customer outreach."
    payload = trigger.get("payload", {}) or {}
    kind = trigger.get("kind", "unknown")
    consent = customer.get("consent", {}) or {}
    scopes = set(consent.get("scope", []) or [])
    required = CONSENT_SCOPES.get(kind)
    if required and not scopes.intersection(required):
        return "", "none", f"No matching consent scope ({' or '.join(required)}); suppressing customer outreach."
    preferences = customer.get("preferences", {}) or {}
    if preferences.get("reminder_opt_in") is False or preferences.get("channel") in {"none_recorded", "none"}:
        return "", "none", "Customer preferences show no active reminder channel or opt-in; suppressing outreach."

    cident = customer.get("identity", {}) or {}
    relationship = customer.get("relationship", {}) or {}
    merchant_ident = merchant.get("identity", {}) or {}
    name = cident.get("name") or "there"
    business = merchant_ident.get("name") or "the business"
    lang = (cident.get("language_pref") or "").lower()
    hi = lang.startswith("hi")
    start = f"Hi {name}, "
    closing = "Aapko kaunsa time suit karega?" if hi else "Would either time work, or is another time better?"

    if kind == "recall_due":
        service = _human(payload.get("service_due") or "follow-up")
        due = payload.get("due_date")
        last = relationship.get("last_visit") or payload.get("last_service_date")
        slots = [s.get("label") for s in (payload.get("available_slots") or []) if s.get("label")]
        line = f"{start}{business} here. Your {service} is due{f' by {due}' if due else ''}"
        if last:
            line += f"; your last visit was {last}"
        if slots:
            line += f". We have {' or '.join(slots[:2])} available"
        line += f". {closing}"
        return line, "open_ended", "Uses the customer's visit history, due date, and available slots; consent is required."

    if kind == "appointment_tomorrow":
        when = _first(payload.get("appointment_time"), payload.get("slot_label"), payload.get("date"), default="tomorrow")
        service = _human(payload.get("service") or "appointment")
        return f"{start}{business} here. This is a reminder for your {service} {when}. Please reply YES to confirm or tell us if you need to reschedule.", "binary_yes_no", "Appointment reminder uses the scheduled service and time from the trigger."

    if kind == "wedding_package_followup":
        date = payload.get("wedding_date") or preferences.get("wedding_date")
        step = _human(payload.get("next_step_window_open") or "next preparation step")
        date_line = f" Your wedding date is {date}." if date else ""
        return f"{start}{business} here. Following up on your bridal plan.{date_line} Your {step} window is open. Would you like us to share the available options?", "binary_yes_no", "Uses the customer’s bridal follow-up state and dates from context."

    if kind == "trial_followup":
        options = payload.get("next_session_options") or []
        label = next((s.get("label") for s in options if s.get("label")), None)
        service = relationship.get("services_received", [])
        trial = _human(service[-1]) if service else "trial session"
        when = f" The next option is {label}." if label else ""
        return f"{start}{business} here. Hope the {trial} went well.{when} Would you like us to confirm the next session?", "binary_yes_no", "Follows up on the recorded trial and supplied session option."

    if kind == "customer_lapsed_hard":
        days = payload.get("days_since_last_visit")
        focus = _human(payload.get("previous_focus"))
        detail = f" It’s been {days} days since your last visit." if days is not None else ""
        focus_detail = f" We can help you revisit your {focus} plan." if focus else ""
        return f"{start}{business} here.{detail}{focus_detail} If you’d like to return, reply and we’ll help find a suitable time. No pressure.", "open_ended", "Low-pressure win-back message based on visit gap and prior focus; matching consent is required."

    if kind == "customer_lapsed_soft":
        days = payload.get("days_since_last_visit")
        detail = f" It’s been {days} days since your last visit." if days is not None else ""
        return f"{start}{business} here.{detail} Would you like help finding a time for your next visit?", "open_ended", "Low-pressure customer check-in uses the supplied visit gap and consent."

    if kind == "chronic_refill_due":
        stock_date = payload.get("stock_runs_out_iso")
        when = f" before {stock_date}" if stock_date else ""
        return f"{start}{business} here. Your refill reminder is due{when}. Reply if you’d like us to check availability and delivery details with the pharmacist.", "open_ended", "Privacy-conscious refill reminder avoids listing medicines or giving treatment advice; requires refill consent."

    if kind in {"customer_research_digest", "patient_content_share", "patient_content_due"}:
        library = category.get("patient_content_library", []) or []
        requested_id = payload.get("content_id") or payload.get("item_id")
        content = next((x for x in library if requested_id and x.get("id") == requested_id), None)
        content = content or (library[0] if library else None)
        if content:
            title = content.get("title") or "a short health information note"
            return f"{start}{business} here. We have a short information note: “{title}”. Would you like us to share it?", "binary_yes_no", "Offers existing category library content only with matching customer consent."

    return "", "none", f"No customer-message handler for {kind}; suppressing instead of sending generic outreach."


def _sanitize(category, body):
    voice = category.get("voice", {}) or {}
    taboos = voice.get("vocab_taboo", []) or voice.get("taboos", []) or []
    for term in taboos:
        if not term or term.lower() not in body.lower():
            continue
        # Remove the sentence containing the taboo instead of making unsupported claims.
        parts = re.split(r"(?<=[.!?])\s+", body)
        parts = [part for part in parts if term.lower() not in part.lower()]
        body = " ".join(parts).strip()
    return body


def compose(category: dict, merchant: dict, trigger: dict, customer: dict | None = None) -> dict:
    """Return body, CTA, sender, suppression key, and rationale for a trigger."""
    category = category or {}
    merchant = merchant or {}
    trigger = trigger or {}
    customer_scope = trigger.get("scope") == "customer" or customer is not None
    if customer_scope:
        body, cta, rationale = _customer_message(category, merchant, trigger, customer)
        send_as = "merchant_on_behalf"
    else:
        body, cta, rationale = _merchant_message(category, merchant, trigger)
        send_as = "vera"
    body = _sanitize(category, body)
    return {
        "body": body,
        "cta": cta,
        "send_as": send_as,
        "suppression_key": trigger.get("suppression_key") or trigger.get("id", ""),
        "rationale": rationale,
    }
