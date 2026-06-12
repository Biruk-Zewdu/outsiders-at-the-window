"""Outsiders at the Window — Stage 2 analysis.

Consumes data/transactions_tagged.parquet and produces the evidence tables
and figures behind the narrative:

  T1 group_share_by_crisis.csv   — each origin group's share of crisis lending (value, count)
  T2 emigre_house_arc.csv        — every émigré house's footprint across 1857/1866/1914
  T3 rate_by_group.csv           — average discount rate paid, by group and crisis
  T4 wwi_fate.csv                — fate in WWI of the houses present in 1914
  F1 group_share_stacked.png     — composition of crisis lending by origin group
  F2 emigre_persistence.png      — émigré value & share across the three crises
  F3 rate_emigre_vs_native.png   — what émigré vs native houses paid, per crisis

All values in £ (nominal). Caveats (selection, small-n, partial classification)
are documented in notes/curation_log.md.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TAB = ROOT / "outputs" / "tables"
FIG = ROOT / "outputs" / "figures"
TAB.mkdir(parents=True, exist_ok=True)
FIG.mkdir(parents=True, exist_ok=True)

EMIGRE = ["Émigré: German & Central European", "Émigré: Greek & Levantine",
          "Émigré: Indian / Parsi", "Émigré: American"]
CRISES = ["1857", "1866", "1914"]
ORDER = ["Émigré: German & Central European", "Émigré: Greek & Levantine",
         "Émigré: Indian / Parsi", "Émigré: American",
         "British: private / merchant (native)", "British: discount house",
         "British: clearing / joint-stock bank", "Colonial / Imperial bank",
         "Foreign bank (1914 wartime)", "Unclassified (long tail)"]
COLORS = {
    "Émigré: German & Central European": "#b2182b",
    "Émigré: Greek & Levantine": "#ef8a62",
    "Émigré: Indian / Parsi": "#fddbc7",
    "Émigré: American": "#d6604d",
    "British: private / merchant (native)": "#2166ac",
    "British: discount house": "#4393c3",
    "British: clearing / joint-stock bank": "#92c5de",
    "Colonial / Imperial bank": "#1b7837",
    "Foreign bank (1914 wartime)": "#762a83",
    "Unclassified (long tail)": "#bbbbbb",
}


def main():
    t = pd.read_parquet(DATA / "transactions_tagged.parquet")
    t["crisis"] = t["crisis"].astype(str)
    t["is_emigre"] = t["origin_group"].isin(EMIGRE)

    # ---- T1: group share of crisis lending ----
    val = t.pivot_table(index="origin_group", columns="crisis", values="value", aggfunc="sum", fill_value=0)
    cnt = t.pivot_table(index="origin_group", columns="crisis", values="value", aggfunc="size", fill_value=0)
    val = val.reindex(ORDER).fillna(0)
    share = val.div(val.sum(axis=0), axis=1) * 100
    t1 = val.copy()
    for c in CRISES:
        t1[f"{c}_share_%"] = share[c].round(1)
    t1.to_csv(TAB / "group_share_by_crisis.csv")

    emigre_share = share.loc[[g for g in EMIGRE if g in share.index]].sum()
    print("=== Émigré share of crisis lending by value (%) ===")
    print(emigre_share.round(1).to_string())

    # ---- T2: émigré house arc ----
    em = t[t["is_emigre"]]
    arc = em.groupby(["canonical_house", "origin", "origin_group"]).apply(
        lambda d: pd.Series({
            "crises_present": "+".join(sorted(d["crisis"].unique())),
            "n_crises": d["crisis"].nunique(),
            "total_value": d["value"].sum(),
            "n_tx": len(d),
            "mean_rate": d["rate"].mean(),
            "v1857": d.loc[d.crisis == "1857", "value"].sum(),
            "v1866": d.loc[d.crisis == "1866", "value"].sum(),
            "v1914": d.loc[d.crisis == "1914", "value"].sum(),
        }), include_groups=False).reset_index().sort_values("total_value", ascending=False)
    arc.to_csv(TAB / "emigre_house_arc.csv", index=False)
    print(f"\n=== émigré houses identified: {arc['canonical_house'].nunique()} ===")
    print(f"present in all three crises: {(arc['n_crises']==3).sum()}  |  in 1857: {(arc['v1857']>0).sum()}  in 1914: {(arc['v1914']>0).sum()}")

    # ---- T3: rate by group & crisis (the price story) ----
    rate = t.pivot_table(index="origin_group", columns="crisis", values="rate", aggfunc="mean").reindex(ORDER)
    rate.round(2).to_csv(TAB / "rate_by_group.csv")
    em_rate = t[t.is_emigre].groupby("crisis")["rate"].mean()
    nat_rate = t[t.origin_group == "British: private / merchant (native)"].groupby("crisis")["rate"].mean()
    print("\n=== mean discount rate: émigré vs native British merchant ===")
    cmp = pd.DataFrame({"emigre": em_rate, "native_merchant": nat_rate}).round(2)
    print(cmp.to_string())

    # ---- T4: WWI fate of houses present in 1914 ----
    reg = pd.read_csv(DATA / "origin_register.csv")
    houses_1914 = t.loc[t.crisis == "1914", "canonical_house"].unique()
    fate = reg[reg["house"].isin(houses_1914)][["house", "origin", "group", "wwi_fate", "confidence"]]
    fate = fate.sort_values("group")
    fate.to_csv(TAB / "wwi_fate.csv", index=False)

    # ============ FIGURES ============
    # F1: stacked composition of crisis lending
    fig, ax = plt.subplots(figsize=(9, 6))
    bottom = np.zeros(len(CRISES))
    for g in ORDER:
        if g not in share.index:
            continue
        vals = share.loc[g, CRISES].values.astype(float)
        ax.bar(CRISES, vals, bottom=bottom, label=g, color=COLORS.get(g, "#999"), width=0.6)
        bottom += vals
    ax.set_ylabel("Share of crisis-window lending (%)")
    ax.set_title("Who borrowed from the Bank of England in each crisis")
    ax.legend(bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=8, frameon=False)
    ax.set_ylim(0, 100)
    fig.tight_layout()
    fig.savefig(FIG / "group_share_stacked.png", dpi=170)
    plt.close(fig)

    # F2: émigré value + share across crises
    fig, ax1 = plt.subplots(figsize=(8, 5))
    emigre_val = val.loc[[g for g in EMIGRE if g in val.index]].sum()[CRISES] / 1e6
    ax1.bar(CRISES, emigre_val.values, color="#b2182b", alpha=0.85, width=0.55, label="Émigré lending (£m)")
    ax1.set_ylabel("Émigré-house lending (£m)", color="#b2182b")
    ax1.tick_params(axis="y", labelcolor="#b2182b")
    ax2 = ax1.twinx()
    ax2.plot(CRISES, emigre_share[CRISES].values, "o-", color="#222", linewidth=2, label="Émigré share (%)")
    ax2.set_ylabel("Émigré share of crisis lending (%)")
    ax2.set_ylim(0, max(emigre_share.max() * 1.4, 20))
    for i, c in enumerate(CRISES):
        ax2.annotate(f"{emigre_share[c]:.1f}%", (i, emigre_share[c]), textcoords="offset points",
                     xytext=(0, 8), ha="center", fontsize=9)
    ax1.set_title("Émigré houses at the Bank's window, 1857–1914")
    fig.tight_layout()
    fig.savefig(FIG / "emigre_persistence.png", dpi=170)
    plt.close(fig)

    # F3: rate émigré vs native merchant vs discount
    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(CRISES)); w = 0.25
    grp_for_rate = {
        "Émigré houses": t[t.is_emigre],
        "Native British merchant": t[t.origin_group == "British: private / merchant (native)"],
        "British discount house": t[t.origin_group == "British: discount house"],
    }
    cols = ["#b2182b", "#2166ac", "#4393c3"]
    for i, (lab, d) in enumerate(grp_for_rate.items()):
        r = d.groupby("crisis")["rate"].mean().reindex(CRISES)
        ax.bar(x + (i - 1) * w, r.values, w, label=lab, color=cols[i])
    ax.set_xticks(x); ax.set_xticklabels(CRISES)
    ax.set_ylabel("Mean discount/advance rate (% p.a.)")
    ax.set_title("What each kind of house paid at the window")
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(FIG / "rate_emigre_vs_native.png", dpi=170)
    plt.close(fig)

    print("\nWrote 4 tables -> outputs/tables/ and 3 figures -> outputs/figures/")


if __name__ == "__main__":
    main()
