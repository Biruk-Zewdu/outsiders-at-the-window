"""Extra network experiments for Outsiders at the Window.

This script keeps only the two experiments now used in the paper:

X2. Enclave null test: do emigre houses cluster with each other more than chance?
X3. Wartime network shock: did the 1914 lending network change after 4 August?

It writes tables, figures, and a short interpretation note under outputs/ and notes/.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TAB = ROOT / "outputs" / "tables"
FIG = ROOT / "outputs" / "figures"
NOTE = ROOT / "notes"
TAB.mkdir(parents=True, exist_ok=True)
FIG.mkdir(parents=True, exist_ok=True)
NOTE.mkdir(parents=True, exist_ok=True)

WAR_DATE = pd.Timestamp("1914-08-04")
EARLY_WAR_END = WAR_DATE + pd.Timedelta(days=33)
RNG = np.random.default_rng(1914)

EMIGRE_GROUPS = {
    "Emigre: German & Central European",
    "Emigre: Greek & Levantine",
    "Emigre: Indian / Parsi",
    "Emigre: American",
    "Émigré: German & Central European",
    "Émigré: Greek & Levantine",
    "Émigré: Indian / Parsi",
    "Émigré: American",
}


def clean_ascii_label(s: str) -> str:
    return str(s).replace("Émigré", "Emigre")


def is_emigre_group(group: str) -> bool:
    return clean_ascii_label(group) in EMIGRE_GROUPS


def mode_or_blank(s: pd.Series) -> str:
    s = s.dropna()
    if s.empty:
        return ""
    m = s.mode()
    return str(m.iloc[0] if not m.empty else s.iloc[0])


def load() -> pd.DataFrame:
    t = pd.read_parquet(DATA / "transactions_tagged.parquet")
    t["crisis"] = t["crisis"].astype(str)
    t["date"] = pd.to_datetime(t["date"].astype("int64"), unit="us")
    t["day"] = t["date"].dt.date
    t["value"] = (
        t["total_amount"]
        .fillna(t["value_discounted"])
        .fillna(t["amount_advanced_total"])
    )
    t["origin_group_clean"] = t["origin_group"].map(clean_ascii_label)
    t["is_emigre"] = t["origin_group_clean"].map(is_emigre_group)
    return t


def rejection_rate(df: pd.DataFrame) -> float:
    d = df[df["transaction_type"].eq("discount")]
    brought = d["value_brought"].sum()
    if not brought:
        return np.nan
    return 100 * d["value_bills_rejected"].fillna(0).sum() / brought


def build_copresence_graph(df: pd.DataFrame, min_shared: int = 2, min_cos: float = 0.30) -> nx.Graph:
    cl = df[df["origin_group_clean"].ne("Unclassified (long tail)")].copy()
    shared = Counter()
    days_of = defaultdict(set)
    value = cl.groupby("canonical_house")["value"].sum().to_dict()
    group = cl.groupby("canonical_house")["origin_group_clean"].agg(mode_or_blank).to_dict()

    for day, d in cl.groupby("day"):
        houses = sorted(h for h in d["canonical_house"].dropna().unique() if h != "(unclassified)")
        for h in houses:
            days_of[h].add(day)
        for a, b in combinations(houses, 2):
            shared[(a, b)] += 1

    g = nx.Graph()
    for h, v in value.items():
        if h == "(unclassified)":
            continue
        g.add_node(h, value=float(v), origin_group=group[h], is_emigre=is_emigre_group(group[h]))

    for (a, b), c in shared.items():
        if c < min_shared:
            continue
        cos = c / np.sqrt(len(days_of[a]) * len(days_of[b]))
        if cos >= min_cos:
            g.add_edge(a, b, weight=float(cos), shared_days=int(c))
    g.remove_nodes_from([n for n in list(g.nodes) if g.degree(n) == 0])
    return g


def weighted_same_label_share(g: nx.Graph, attr: str) -> float:
    total = same = 0.0
    for u, v, d in g.edges(data=True):
        w = float(d.get("weight", 1.0))
        total += w
        if g.nodes[u][attr] == g.nodes[v][attr]:
            same += w
    return same / total if total else np.nan


def binary_edge_mix(g: nx.Graph) -> tuple[float, float, float]:
    total = ee = eo = oo = 0.0
    for u, v, d in g.edges(data=True):
        w = float(d.get("weight", 1.0))
        total += w
        a = bool(g.nodes[u]["is_emigre"])
        b = bool(g.nodes[v]["is_emigre"])
        if a and b:
            ee += w
        elif a or b:
            eo += w
        else:
            oo += w
    if not total:
        return np.nan, np.nan, np.nan
    return ee / total, eo / total, oo / total


def metric_pack(g: nx.Graph) -> dict[str, float]:
    if g.number_of_edges() == 0:
        return {
            "binary_emigre_assortativity": np.nan,
            "same_origin_weight_share": np.nan,
            "emigre_emigre_weight_share": np.nan,
            "emigre_other_weight_share": np.nan,
            "other_other_weight_share": np.nan,
        }
    ee, eo, oo = binary_edge_mix(g)
    return {
        "binary_emigre_assortativity": nx.attribute_assortativity_coefficient(g, "is_emigre"),
        "same_origin_weight_share": weighted_same_label_share(g, "origin_group"),
        "emigre_emigre_weight_share": ee,
        "emigre_other_weight_share": eo,
        "other_other_weight_share": oo,
    }


def shuffled_metric_pack(g: nx.Graph) -> dict[str, float]:
    h = g.copy()
    nodes = list(h.nodes)
    labels = [h.nodes[n]["origin_group"] for n in nodes]
    RNG.shuffle(labels)
    for n, label in zip(nodes, labels):
        h.nodes[n]["origin_group"] = label
        h.nodes[n]["is_emigre"] = is_emigre_group(label)
    return metric_pack(h)


def x2_enclave_null(t: pd.DataFrame, n_iter: int = 1000) -> pd.DataFrame:
    scopes = [("all_crises", t)]
    for crisis in ["1857", "1866", "1914"]:
        scopes.append((crisis, t[t["crisis"].eq(crisis)]))

    rows = []
    edge_rows = []
    for scope, df in scopes:
        g = build_copresence_graph(df)
        observed = metric_pack(g)
        labels = {n: g.nodes[n]["origin_group"] for n in g.nodes}

        for u, v, d in g.edges(data=True):
            edge_rows.append({
                "scope": scope,
                "house_a": u,
                "house_b": v,
                "origin_a": labels[u],
                "origin_b": labels[v],
                "both_emigre": bool(g.nodes[u]["is_emigre"] and g.nodes[v]["is_emigre"]),
                "same_origin_group": labels[u] == labels[v],
                "weight": d.get("weight", 1.0),
                "shared_days": d.get("shared_days", 1),
            })

        null = pd.DataFrame([shuffled_metric_pack(g) for _ in range(n_iter)])
        for metric, obs in observed.items():
            vals = null[metric].dropna().to_numpy()
            mean = float(np.mean(vals))
            sd = float(np.std(vals, ddof=1))
            rows.append({
                "scope": scope,
                "nodes": g.number_of_nodes(),
                "edges": g.number_of_edges(),
                "metric": metric,
                "observed": obs,
                "null_mean": mean,
                "null_sd": sd,
                "z_score": (obs - mean) / sd if sd else np.nan,
                "p_more_enclaved": (np.sum(vals >= obs) + 1) / (len(vals) + 1),
                "p_less_enclaved": (np.sum(vals <= obs) + 1) / (len(vals) + 1),
            })

    out = pd.DataFrame(rows)
    out.to_csv(TAB / "x2_enclave_null_test.csv", index=False)
    pd.DataFrame(edge_rows).to_csv(TAB / "x2_copresence_edges.csv", index=False)

    plot = out[out["metric"].eq("binary_emigre_assortativity")].copy()
    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(plot))
    ax.errorbar(x, plot["null_mean"], yerr=plot["null_sd"], fmt="o", color="#999999", label="shuffled labels")
    ax.scatter(x, plot["observed"], color="#b2182b", zorder=3, label="observed")
    ax.axhline(0, color="#222222", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(plot["scope"], rotation=20, ha="right")
    ax.set_ylabel("emigre assortativity")
    ax.set_title("Do emigre houses cluster together more than chance?")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(FIG / "x2_enclave_null_binary_assortativity.png", dpi=170)
    plt.close(fig)

    return out


def period_label(date: pd.Timestamp) -> str:
    if date < WAR_DATE:
        return "pre_war_34d"
    if date <= EARLY_WAR_END:
        return "early_war_34d"
    return "later_war"


def period_calendar_days(period: str, dates: pd.Series) -> int:
    if period in {"pre_war_34d", "early_war_34d"}:
        return 34
    later = dates[dates.map(period_label).eq("later_war")]
    if later.empty:
        return 0
    return int((later.max().normalize() - later.min().normalize()).days) + 1


def x3_wartime_network_shock(t: pd.DataFrame) -> pd.DataFrame:
    n = t[t["crisis"].eq("1914")].copy()
    n["period"] = n["date"].map(period_label)
    period_order = ["pre_war_34d", "early_war_34d", "later_war"]

    rows = []
    for period in period_order:
        d = n[n["period"].eq(period)].copy()
        active_days = max(1, d["day"].nunique())
        calendar_days = max(1, period_calendar_days(period, n["date"]))

        for group_name, mask in [
            ("Emigre houses", d["is_emigre"]),
            ("All classified houses", d["origin_group_clean"].ne("Unclassified (long tail)")),
            ("Other classified houses", d["origin_group_clean"].ne("Unclassified (long tail)") & ~d["is_emigre"]),
        ]:
            gd = d[mask & d["canonical_house"].ne("(unclassified)")].copy()
            houses = gd["canonical_house"].nunique()
            house_day_edges = gd.groupby(["canonical_house", "day"]).size().shape[0]
            total_value = gd["value"].sum()
            rows.append({
                "period": period,
                "period_calendar_days": calendar_days,
                "active_ledger_days": active_days,
                "group": group_name,
                "houses": houses,
                "house_day_edges": house_day_edges,
                "possible_active_house_day_edges": houses * active_days,
                "network_occupancy_pct": 100 * house_day_edges / (houses * active_days) if houses and active_days else np.nan,
                "transactions": len(gd),
                "transactions_per_calendar_week": len(gd) / calendar_days * 7,
                "value": total_value,
                "value_per_calendar_week": total_value / calendar_days * 7,
                "value_share_of_classified_pct": np.nan,
                "mean_rate": gd["rate"].mean(),
                "rejection_pct": rejection_rate(gd),
            })

        classified_value = d.loc[d["origin_group_clean"].ne("Unclassified (long tail)"), "value"].sum()
        for row in rows:
            if row["period"] == period:
                row["value_share_of_classified_pct"] = (
                    100 * row["value"] / classified_value if classified_value else np.nan
                )

    shock = pd.DataFrame(rows)
    shock.to_csv(TAB / "x3_wartime_house_day_network_shock.csv", index=False)

    em = shock[shock["group"].eq("Emigre houses")].set_index("period").loc[period_order]
    allc = shock[shock["group"].eq("All classified houses")].set_index("period").loc[period_order]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    x = np.arange(len(period_order))
    labels = ["pre-war\n34d", "early-war\n34d", "later\nwar"]

    axes[0].plot(x, em["value_share_of_classified_pct"], marker="o", color="#b2182b")
    axes[0].set_title("Value share")
    axes[0].set_ylabel("Emigre share of classified value (%)")
    axes[1].plot(x, em["network_occupancy_pct"], marker="o", color="#b2182b")
    axes[1].set_title("House-day presence")
    axes[1].set_ylabel("active house-days / possible (%)")
    axes[2].plot(x, em["rejection_pct"], marker="o", color="#b2182b", label="Emigre")
    axes[2].plot(x, allc["rejection_pct"], marker="o", color="#666666", label="All classified")
    axes[2].set_title("Rejection")
    axes[2].set_ylabel("bills rejected by value (%)")
    axes[2].legend(frameon=False)

    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle("Wartime network shock test around 4 Aug 1914", fontsize=12)
    fig.tight_layout()
    fig.savefig(FIG / "x3_wartime_network_shock.png", dpi=170)
    plt.close(fig)

    return shock


def write_interpretation(x2: pd.DataFrame, x3: pd.DataFrame) -> None:
    binary_all = x2[(x2["scope"].eq("all_crises")) & (x2["metric"].eq("binary_emigre_assortativity"))].iloc[0]
    ee_all = x2[(x2["scope"].eq("all_crises")) & (x2["metric"].eq("emigre_emigre_weight_share"))].iloc[0]
    eo_all = x2[(x2["scope"].eq("all_crises")) & (x2["metric"].eq("emigre_other_weight_share"))].iloc[0]

    em_shock = x3[x3["group"].eq("Emigre houses")].set_index("period")
    all_shock = x3[x3["group"].eq("All classified houses")].set_index("period")
    pre_share = em_shock.loc["pre_war_34d", "value_share_of_classified_pct"]
    early_share = em_shock.loc["early_war_34d", "value_share_of_classified_pct"]
    pre_rej = em_shock.loc["pre_war_34d", "rejection_pct"]
    early_rej = em_shock.loc["early_war_34d", "rejection_pct"]
    early_all_rej = all_shock.loc["early_war_34d", "rejection_pct"]
    later_rej = em_shock.loc["later_war", "rejection_pct"]
    later_all_rej = all_shock.loc["later_war", "rejection_pct"]

    text = f"""# Extra network experiments: interpretation

These are the two extra network experiments now used in the paper.

## X2. Enclave null test

The co-presence graph links two houses when they came to the Bank on the same ledger
days more often than a simple overlap rule would expect. I then shuffled the origin
labels 1,000 times across the same graph.

For the all-crisis graph, binary emigre assortativity is **{binary_all['observed']:.3f}**
against a shuffled-label mean of **{binary_all['null_mean']:.3f}**
(z = **{binary_all['z_score']:.2f}**, p-more-enclaved = **{binary_all['p_more_enclaved']:.3f}**).
But emigre-to-emigre ties are only **{ee_all['observed']:.3f}** of weighted edges,
below the shuffled mean of **{ee_all['null_mean']:.3f}**. Emigre-to-other ties are
**{eo_all['observed']:.3f}** of weighted edges.

The useful reading is not that there was no structure at all. There was some sorting.
But it was not a separate emigre enclave.

## X3. Wartime network shock

The shock test compares equal 34-day windows before and after 4 August 1914, then keeps
the later war months as a third period.

The emigre share of classified value moves from **{pre_share:.1f}%** before the war to
**{early_share:.1f}%** in the first 34 war days. Emigre rejection moves from
**{pre_rej:.2f}%** to **{early_rej:.2f}%**, while all classified houses show
**{early_all_rej:.2f}%** rejection in the same early-war window. Later in the war,
emigre rejection is **{later_rej:.2f}%**, almost the same as **{later_all_rej:.2f}%**
for all classified houses.

So the Bank's network tightened after the war began, but not in a way that clearly
singled out the emigre houses.
"""
    (NOTE / "network_experiments_extra_interpretation.md").write_text(text)


def main() -> None:
    t = load()
    x2 = x2_enclave_null(t, n_iter=1000)
    x3 = x3_wartime_network_shock(t)
    write_interpretation(x2, x3)

    print("Wrote:")
    for path in [
        TAB / "x2_enclave_null_test.csv",
        TAB / "x2_copresence_edges.csv",
        TAB / "x3_wartime_house_day_network_shock.csv",
        FIG / "x2_enclave_null_binary_assortativity.png",
        FIG / "x3_wartime_network_shock.png",
        NOTE / "network_experiments_extra_interpretation.md",
    ]:
        print(f"  {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
