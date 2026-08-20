"""
Group Spend Chart Service
Generate a YTD bar chart for a GROUP of client codes billed as one
commercial relationship (e.g. One NZ = ONE + ONS + ONB), with their
combined monthly-committed line.

GO IN → GET EACH CLIENT'S SERIES → MERGE BY MONTH → RENDER PNG → GET OUT

Sits between the single-client handler (one code) and the Hunch handler
(every code). Same output shape as both, so Brain/Hub handle it identically.

Why merge per-client series rather than pooling raw tracker rows:
_build_series already handles year derivation, Budget History stepping,
and pre-engagement exclusion per client. Doing it per client and then
summing keeps all of that correct — in particular a code that started
mid-year contributes neither spend NOR committed for the months before
it began, so the group's expected doesn't get inflated by a client that
wasn't running yet.
"""

import base64

from flask import jsonify

from utils import airtable
from .build_chart import build_chart_bytes
from .handler import MONTH_NUM, _build_series, _summarise


# ===================
# GROUP DEFINITIONS
# ===================

# 'code' is only used for logo lookup — _load_logo aliases ONB/ONS to ONE,
# so any One NZ code renders the one.nz roundel.
GROUPS = {
    "onenz": {
        "name": "One NZ – All",
        "code": "ONE",
        "codes": ["ONE", "ONS", "ONB"],
    },
    "onenz-bm": {
        "name": "One NZ – Business + Marketing",
        "code": "ONE",
        "codes": ["ONE", "ONB"],
    },
}

# Accepted aliases → group key, so the bot can be loose about phrasing.
GROUP_ALIASES = {
    "onenz": "onenz",
    "one-nz": "onenz",
    "one nz": "onenz",
    "onenz-all": "onenz",
    "one nz everything": "onenz",
    "everything": "onenz",
    "group": "onenz",
    "onenz-bm": "onenz-bm",
    "business-marketing": "onenz-bm",
    "business and marketing": "onenz-bm",
    "bm": "onenz-bm",
    "onb-one": "onenz-bm",
}


def resolve_group(raw):
    """Map a loose group name to a GROUPS entry. Returns (key, cfg) or (None, None)."""
    if not raw:
        return None, None
    key = GROUP_ALIASES.get(str(raw).strip().lower())
    if not key:
        return None, None
    return key, GROUPS[key]


# ===================
# MERGE
# ===================

def _merge_series(per_client: list, group_name: str, group_code: str) -> dict:
    """Sum a list of per-client _build_series dicts into one group series.

    Each input series covers the same 12 FY months in the same order —
    guaranteed by the shared year-end check in the handler below.
    """
    first = per_client[0]
    months = first["series"]
    n = len(months)

    merged = []
    for i in range(n):
        rows = [c["series"][i] for c in per_client]
        # A month is pre-engagement for the GROUP only if it is for every
        # member. Otherwise the group was live and the month counts.
        group_pre = all(r["is_pre_engagement"] for r in rows)
        merged.append({
            "month_short": rows[0]["month_short"],
            "month_full": rows[0]["month_full"],
            "year": rows[0]["year"],
            "is_future": rows[0]["is_future"],
            "is_pre_engagement": group_pre,
            "spend": round(sum(r["spend"] for r in rows), 2),
            # Only count a member's committed in months it was actually engaged.
            "committed": round(
                sum(r["committed"] for r in rows if not r["is_pre_engagement"]), 2
            ),
        })

    counted = [s for s in merged if not s["is_future"] and not s["is_pre_engagement"]]
    total_ytd = sum(s["spend"] for s in counted)
    expected_ytd = sum(s["committed"] for s in counted)

    committed_values = sorted({s["committed"] for s in merged if s["committed"] > 0})

    current_committed = counted[-1]["committed"] if counted else (
        merged[-1]["committed"] if merged else 0
    )

    return {
        "code": group_code,
        "name": group_name,
        "year_end_month": first["year_end_month"],
        "fy_complete": first["fy_complete"],
        "fy_label": first["fy_label"],
        "monthly_committed": current_committed,
        "committed_changed": len(committed_values) > 1,
        "total_ytd": round(total_ytd, 2),
        "expected_ytd": round(expected_ytd, 2),
        "variance": round(total_ytd - expected_ytd, 2),
        "months_so_far": len(counted),
        "series": merged,
        "members": [c["code"] for c in per_client],
    }


# ===================
# MAIN HANDLER
# ===================

def generate_group_spend_chart(data):
    """
    Build a YTD spend chart for a group of client codes.

    Input:
        data: {"group": "onenz" | "onenz-bm", "fy": "current" | "last"}
        or:   {"codes": ["ONE", "ONB"], "name": "One NZ – Business + Marketing"}

    Returns the same envelope as generate_spend_chart, plus "members".
    """
    data = data or {}
    fy_choice = str(data.get("fy", "current")).strip().lower()
    fy_offset = 1 if fy_choice == "last" else 0

    group_key, cfg = resolve_group(data.get("group"))

    if cfg:
        codes = list(cfg["codes"])
        group_name = data.get("name") or cfg["name"]
        group_code = cfg["code"]
    elif data.get("codes"):
        codes = [str(c).strip().upper() for c in data["codes"] if str(c).strip()]
        group_name = data.get("name") or " + ".join(codes)
        group_code = codes[0] if codes else "HUN"
    else:
        return jsonify({
            "success": False,
            "error": (
                "Missing group. Use one of: "
                + ", ".join(sorted(GROUPS.keys()))
                + " — or pass an explicit codes list."
            ),
        }), 400

    if len(codes) < 2:
        return jsonify({
            "success": False,
            "error": "A group needs at least two client codes.",
        }), 400

    print(f"[group_chart] === BUILDING GROUP CHART ===")
    print(f"[group_chart] Group: {group_name} {codes}, FY: {fy_choice}")

    today = airtable.get_nz_today()
    per_client = []
    year_ends = {}

    for code in codes:
        client = airtable.get_client_for_chart(code)
        if not client:
            return jsonify({
                "success": False,
                "error": f"Client {code} not found in Clients table",
            }), 404

        year_ends[code] = client.get("year_end")

        tracker_records = airtable.get_tracker_for_client(code)
        budget_history = airtable.get_budget_history_for_client(code)
        print(f"[group_chart] {code}: {len(tracker_records)} tracker, "
              f"{len(budget_history)} budget history")

        per_client.append(
            _build_series(client, tracker_records, budget_history, today, fy_offset)
        )

    # Every member must share a year end, or the 12-month windows don't line up
    # and summing them would be nonsense.
    distinct_year_ends = {v for v in year_ends.values()}
    if len(distinct_year_ends) > 1:
        detail = ", ".join(f"{k}={v}" for k, v in year_ends.items())
        return jsonify({
            "success": False,
            "error": (
                "Group members have different year ends so their financial "
                f"years don't align ({detail}). Charts can only be combined "
                "across clients sharing a year end."
            ),
        }), 400

    chart_data = _merge_series(per_client, group_name, group_code)

    try:
        png_bytes = build_chart_bytes(chart_data)
    except Exception as e:
        print(f"[group_chart] Render failed: {e}")
        import traceback; traceback.print_exc()
        return jsonify({"success": False, "error": f"Render failed: {e}"}), 500

    image_b64 = base64.b64encode(png_bytes).decode("ascii")
    summary = _summarise(chart_data)

    print(f"[group_chart] Done. {chart_data['name']}: "
          f"${chart_data['total_ytd']:,.0f} vs ${chart_data['expected_ytd']:,.0f}")

    return jsonify({
        "success": True,
        "summary": summary,
        "image_base64": image_b64,
        "group": group_key,
        "client_code": chart_data["code"],
        "client_name": chart_data["name"],
        "members": chart_data["members"],
        "fy_label": chart_data["fy_label"],
        "fy": fy_choice,
        "variance": chart_data["variance"],
    })
