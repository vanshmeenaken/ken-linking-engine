"""PRD-aligned selection and reporting for report link opportunities."""
from __future__ import annotations

from collections import defaultdict

REPORT_LINK_MIN = 10
REPORT_LINK_MAX = 25
REPORT_OPPORTUNITY_MIN = 10
REPORT_OPPORTUNITY_MAX = 30

LINK_RANGES = {
    "report": (REPORT_LINK_MIN, REPORT_LINK_MAX),
    "article": (5, 15),
    "case_study": (5, 12),
    "industry_page": (30, 999),
    "country_page": (20, 999),
}

CATEGORY_ORDER = (
    "regional_report",
    "adjacent_report",
    "hub",
    "supporting_content",
    "evidence",
    "other",
)


def recommendation_category(
    relationship_type: str,
    source_type: str,
    target_type: str,
) -> str:
    """Map a recommendation to a dashboard/planning category."""
    if source_type == "report" and target_type == "report":
        if relationship_type == "adjacent_market":
            return "adjacent_report"
        return "regional_report"
    if relationship_type == "country_region":
        return "hub"
    if relationship_type == "case_study_support":
        return "evidence"
    if relationship_type == "report_article_support":
        return "supporting_content"
    return "other"


def _diverse_order(recommendations: list) -> list:
    """Keep the strongest item first, then introduce available categories."""
    ranked = sorted(recommendations, key=lambda rec: -rec.link_score)
    if len(ranked) < 2:
        return ranked

    ordered = [ranked.pop(0)]
    represented = {ordered[0].plan_category}
    category_heads = []
    for category in CATEGORY_ORDER:
        if category in represented:
            continue
        candidate = next(
            (rec for rec in ranked if rec.plan_category == category), None
        )
        if candidate is not None:
            category_heads.append(candidate)
    category_heads.sort(key=lambda rec: -rec.link_score)
    for candidate in category_heads:
        ordered.append(candidate)
        ranked.remove(candidate)
    ordered.extend(ranked)
    return ordered


def select_balanced_recommendations(
    recommendations: list,
    page_facts: dict[str, dict],
    approved_keys: set[tuple[str, str]],
    reserved_approved_by_source: dict[str, int] | None = None,
    reserved_touch_by_report: dict[str, int] | None = None,
) -> list:
    """Select quality candidates without exceeding page or workflow limits.

    Existing approved decisions are selected first and never displaced by a
    newly generated candidate. The function does not pad a plan to its minimum:
    when too few candidates pass the relevance gates, the stored report plan
    records that shortage explicitly.
    """
    reserved_approved_by_source = reserved_approved_by_source or {}
    touch_count = defaultdict(int, reserved_touch_by_report or {})
    grouped: dict[str, list] = defaultdict(list)
    for recommendation in recommendations:
        grouped[recommendation.source_node_id].append(recommendation)

    selected = []
    for source_id, group in grouped.items():
        facts = page_facts[source_id]
        _, maximum = LINK_RANGES.get(facts["content_type"], (0, 999))
        capacity = max(
            0,
            maximum
            - int(facts.get("internal_links_out") or 0)
            - reserved_approved_by_source.get(source_id, 0),
        )
        approved = [
            rec for rec in group
            if (rec.source_node_id, rec.target_node_id) in approved_keys
        ]
        approved.sort(key=lambda rec: -rec.link_score)
        others = [rec for rec in group if rec not in approved]
        ordered = approved + _diverse_order(others)

        source_selected = []
        for recommendation in ordered:
            is_approved = (
                recommendation.source_node_id,
                recommendation.target_node_id,
            ) in approved_keys
            if not is_approved and len(source_selected) >= capacity:
                continue

            endpoints = []
            for node_id in (
                recommendation.source_node_id,
                recommendation.target_node_id,
            ):
                if page_facts[node_id]["content_type"] == "report":
                    endpoints.append(node_id)
            if not is_approved and any(
                touch_count[node_id] >= REPORT_OPPORTUNITY_MAX
                for node_id in endpoints
            ):
                continue

            source_selected.append(recommendation)
            for node_id in endpoints:
                touch_count[node_id] += 1

        for rank, recommendation in enumerate(source_selected, 1):
            recommendation.source_plan_rank = rank
        selected.extend(source_selected)

    return sorted(selected, key=lambda rec: -rec.link_score)


def refresh_report_link_plans(conn, now: str) -> int:
    """Rebuild one honest link-plan summary row for every active report."""
    reports = conn.execute(
        """SELECT node_id, url, COALESCE(internal_links_out, 0) AS links_out
           FROM content_nodes
           WHERE status='active' AND content_type='report'"""
    ).fetchall()
    available_types = {
        row[0] for row in conn.execute(
            "SELECT DISTINCT content_type FROM content_nodes WHERE status='active'"
        )
    }
    missing_types = [
        label for content_type, label in (
            ("industry_page", "industry hubs"),
            ("country_page", "country/region hubs"),
            ("service_page", "service pages"),
        )
        if content_type not in available_types
    ]

    conn.execute(
        """DELETE FROM report_link_plans
           WHERE report_node_id NOT IN (
               SELECT node_id FROM content_nodes
               WHERE status='active' AND content_type='report'
           )"""
    )
    for report in reports:
        node_id = report["node_id"]
        outgoing = conn.execute(
            """SELECT status, plan_category, COUNT(*) AS n
               FROM link_recommendations
               WHERE source_node_id=? AND status IN ('pending', 'approved')
               GROUP BY status, plan_category""",
            (node_id,),
        ).fetchall()
        incoming = conn.execute(
            """SELECT status, plan_category, COUNT(*) AS n
               FROM link_recommendations
               WHERE target_node_id=? AND status IN ('pending', 'approved')
               GROUP BY status, plan_category""",
            (node_id,),
        ).fetchall()

        outgoing_count = sum(row["n"] for row in outgoing)
        incoming_count = sum(row["n"] for row in incoming)
        approved_count = sum(
            row["n"] for row in outgoing if row["status"] == "approved"
        )
        pending_count = sum(
            row["n"] for row in outgoing if row["status"] == "pending"
        )
        all_opportunities = [*outgoing, *incoming]
        category_counts = defaultdict(int)
        for row in all_opportunities:
            category_counts[row["plan_category"] or "other"] += row["n"]

        existing = int(report["links_out"] or 0)
        projected = existing + outgoing_count
        gap = max(0, REPORT_LINK_MIN - projected)
        capacity = max(0, REPORT_LINK_MAX - projected)
        total_opportunities = outgoing_count + incoming_count

        if existing > REPORT_LINK_MAX:
            plan_status = "existing_over_limit"
        elif projected > REPORT_LINK_MAX:
            plan_status = "planned_over_limit"
        elif projected >= REPORT_LINK_MIN:
            plan_status = "link_range_met"
        else:
            plan_status = "needs_more_relevant_links"

        if total_opportunities > REPORT_OPPORTUNITY_MAX:
            opportunity_status = "over_opportunity_limit"
        elif total_opportunities >= REPORT_OPPORTUNITY_MIN:
            opportunity_status = "target_met"
        else:
            opportunity_status = "needs_candidates"

        reasons = []
        if gap:
            reasons.append(
                f"{gap} more qualified outgoing link(s) are needed to reach 10"
            )
        if total_opportunities < REPORT_OPPORTUNITY_MIN:
            reasons.append(
                f"only {total_opportunities} of 10-30 workflow opportunities are available"
            )
        if missing_types:
            reasons.append("inventory has no " + ", ".join(missing_types))
        gap_reason = "; ".join(reasons) or None

        values = (
            node_id, report["url"], existing, REPORT_LINK_MIN, REPORT_LINK_MAX,
            outgoing_count, approved_count, pending_count, incoming_count,
            total_opportunities, projected, gap, capacity,
            category_counts["regional_report"],
            category_counts["adjacent_report"],
            category_counts["supporting_content"] + category_counts["evidence"],
            category_counts["hub"], plan_status, opportunity_status,
            gap_reason, now, now,
        )
        conn.execute(
            """INSERT INTO report_link_plans
               (report_node_id, report_url, existing_outgoing_links,
                minimum_outgoing_links, maximum_outgoing_links,
                recommended_outgoing_links, approved_outgoing_links,
                pending_outgoing_links, incoming_opportunities,
                total_opportunities, projected_outgoing_links, remaining_gap,
                remaining_capacity, regional_report_opportunities,
                adjacent_report_opportunities, supporting_content_opportunities,
                hub_opportunities, plan_status, opportunity_status, gap_reason,
                created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(report_node_id) DO UPDATE SET
                   report_url=excluded.report_url,
                   existing_outgoing_links=excluded.existing_outgoing_links,
                   recommended_outgoing_links=excluded.recommended_outgoing_links,
                   approved_outgoing_links=excluded.approved_outgoing_links,
                   pending_outgoing_links=excluded.pending_outgoing_links,
                   incoming_opportunities=excluded.incoming_opportunities,
                   total_opportunities=excluded.total_opportunities,
                   projected_outgoing_links=excluded.projected_outgoing_links,
                   remaining_gap=excluded.remaining_gap,
                   remaining_capacity=excluded.remaining_capacity,
                   regional_report_opportunities=excluded.regional_report_opportunities,
                   adjacent_report_opportunities=excluded.adjacent_report_opportunities,
                   supporting_content_opportunities=excluded.supporting_content_opportunities,
                   hub_opportunities=excluded.hub_opportunities,
                   plan_status=excluded.plan_status,
                   opportunity_status=excluded.opportunity_status,
                   gap_reason=excluded.gap_reason,
                   updated_at=excluded.updated_at""",
            values,
        )
    return len(reports)
