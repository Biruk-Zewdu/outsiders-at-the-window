"""Generate site/data.js from the analysis output CSVs, so the webpage's
interactive charts are driven by the same numbers as the paper.

Run after analyze.py / experiments*.py / network_*: python src/build_site_data.py
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAB = ROOT / "outputs" / "tables"
SITE = ROOT / "site"
SITE.mkdir(exist_ok=True)


def rows(name):
    with open(TAB / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


data = {}

# --- Figure 1: share of window lending by origin group, per crisis ---
share = rows("group_share_by_crisis.csv")
data["groupShare"] = [
    {
        "group": r["origin_group"],
        "s1857": num(r["1857_share_%"]),
        "s1866": num(r["1866_share_%"]),
        "s1914": num(r["1914_share_%"]),
    }
    for r in share
]

# émigré share + value totals per crisis
em = [r for r in share if r["origin_group"].startswith("Émigré")]
data["emigre"] = {
    y: {
        "share": round(sum(num(r[f"{y}_share_%"]) or 0 for r in em), 1),
        "value": round(sum(num(r[y]) or 0 for r in em)),
    }
    for y in ("1857", "1866", "1914")
}

# --- rejection rates (E1) ---
data["rejection"] = [
    {
        "crisis": r["crisis"],
        "group": r["group"],
        "pct": num(r["rejection_rate_pct"]),
    }
    for r in rows("e1_rejection_by_origin.csv")
]

# --- rate regression (E5) ---
data["regression"] = [
    {
        "crisis": r["crisis"],
        "n": int(r["n_houses"]),
        "coef": num(r["emigre_coef_on_rate"]),
        "lo": num(r["ci95_low"]),
        "hi": num(r["ci95_high"]),
        "p": num(r["p_value"]),
    }
    for r in rows("e5_rate_regression.csv")
]

# --- top twenty borrowers per crisis (E3) ---
data["top20"] = {
    y: [
        {
            "rank": int(r["rank"]),
            "house": r["canonical_house"],
            "origin": r["origin_short"],
            "value": round(num(r["value"])),
            "emigre": r["emigre"] == "True",
        }
        for r in rows(f"e3_top_houses_{y}.csv")
    ]
    for y in ("1857", "1866", "1914")
}

# --- enclave null test (X2), all-crises weight shares ---
data["enclave"] = {
    r["metric"]: {"observed": num(r["observed"]), "null": num(r["null_mean"])}
    for r in rows("x2_enclave_null_test.csv")
    if r["scope"] == "all_crises"
}

# --- 1914 intermediation (NET1) ---
data["beneficiary"] = [
    {"kind": r["bkind"], "value": round(num(r["value"]))}
    for r in rows("net1_beneficiary_kind_value.csv")
]
data["conduits"] = [
    {"house": r["node"], "value": round(num(r["value_out"]))}
    for r in rows("net1_top_conduits.csv")
][:7]

# --- Hansard lexicon counts ---
data["hansard"] = [
    {"term": r["lexicon_term"], "count": int(r["count"])}
    for r in rows("hansard_lexicon_counts.csv")
    if int(r["count"]) > 0
]

# --- wartime treatment (E4) ---
data["wartime"] = [
    {
        "era": r["era"],
        "group": r["group"],
        "rate": num(r["mean_rate"]),
        "rejection": num(r["rejection_pct"]),
    }
    for r in rows("e4_wartime_treatment.csv")
]

# --- wartime network shock (X3) ---
data["shock"] = [
    {
        "period": r["period"],
        "group": r["group"],
        "occupancy": num(r["network_occupancy_pct"]),
        "valueShare": num(r["value_share_of_classified_pct"]),
        "rejection": num(r["rejection_pct"]),
    }
    for r in rows("x3_wartime_house_day_network_shock.csv")
    if r["group"] in ("Emigre houses", "All classified houses")
]

# --- the full émigré house arc (house explorer) ---
data["arc"] = [
    {
        "house": r["canonical_house"],
        "origin": r["origin"],
        "group": r["origin_group"].replace("Émigré: ", ""),
        "crises": r["crises_present"],
        "n": int(r["n_crises"]),
        "total": round(num(r["total_value"])),
        "v1857": round(num(r["v1857"])),
        "v1866": round(num(r["v1866"])),
        "v1914": round(num(r["v1914"])),
    }
    for r in rows("emigre_house_arc.csv")
]

# --- WWI fate register (fate explorer) ---
data["fate"] = [
    {
        "house": r["house"],
        "origin": r["origin"],
        "group": r["group"],
        "fate": r["wwi_fate"],
        "confidence": r["confidence"],
    }
    for r in rows("wwi_fate.csv")
]

out = "window.DATA = " + json.dumps(data, ensure_ascii=False, indent=1) + ";\n"
(SITE / "data.js").write_text(out, encoding="utf-8")
print(f"wrote site/data.js ({len(out):,} bytes)")
