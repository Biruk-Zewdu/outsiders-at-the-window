"""Outsiders at the Window — direct tests of insider treatment (replaces the
co-timing network). Three experiments, all from the ledger's per-transaction fields:

  E1  acceptance vs rejection by origin   -> e1_rejection_by_origin.png + table
  E2  rates controlled for house size      -> e2_rate_vs_size.png
  E3  the biggest names at the window      -> e3_top_houses_<crisis>.csv + counts

Rejection note: the rejection columns are populated only when a rejection occurred,
and only on discount rows, so a blank means zero rejected. Rates use the `rate`
field (97% filled). All descriptive; see notes/curation_log.md for caveats.
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

EM = ["Émigré: German & Central European", "Émigré: Greek & Levantine",
      "Émigré: Indian / Parsi", "Émigré: American"]
BR_NATIVE = ["British: private / merchant (native)", "British: discount house",
             "British: clearing / joint-stock bank"]
CRISES = ["1857", "1866", "1914"]
SHORT = {"Émigré: German & Central European": "German/C.Eur", "Émigré: Greek & Levantine": "Greek/Lev",
         "Émigré: Indian / Parsi": "Indian/Parsi", "Émigré: American": "American",
         "British: private / merchant (native)": "Br private", "British: discount house": "Br discount",
         "British: clearing / joint-stock bank": "Br clearing", "Colonial / Imperial bank": "Colonial",
         "Foreign bank (1914 wartime)": "Foreign 1914"}


def load():
    t = pd.read_parquet(DATA / "transactions_tagged.parquet")
    t["crisis"] = t["crisis"].astype(str)
    t["value"] = t["total_amount"].fillna(t["value_discounted"]).fillna(t["amount_advanced_total"])
    t["is_emigre"] = t["origin_group"].isin(EM)
    return t


# ---------------- E1 ----------------
def e1_rejection(t):
    d = t[t["transaction_type"] == "discount"].copy()
    d["rej"] = d["value_bills_rejected"].fillna(0)

    def rate(df):
        vb = df["value_brought"].sum()
        return 100 * df["rej"].sum() / vb if vb else np.nan

    rows = []
    cats = {"Émigré houses": lambda df: df[df.is_emigre],
            "All borrowers (window)": lambda df: df,
            "Old English private banks": lambda df: df[df.origin_group == "British: private / merchant (native)"]}
    for cr in CRISES:
        sub = d[d.crisis == cr]
        for lab, f in cats.items():
            rows.append({"crisis": cr, "group": lab, "rejection_rate_pct": round(rate(f(sub)), 2),
                         "value_brought": f(sub)["value_brought"].sum()})
    tab = pd.DataFrame(rows)
    tab.to_csv(TAB / "e1_rejection_by_origin.csv", index=False)

    fig, ax = plt.subplots(figsize=(9, 5.5))
    x = np.arange(len(CRISES)); w = 0.26
    colors = {"Émigré houses": "#b2182b", "All borrowers (window)": "#999999",
              "Old English private banks": "#2166ac"}
    for i, lab in enumerate(cats):
        vals = [tab[(tab.crisis == c) & (tab.group == lab)]["rejection_rate_pct"].iloc[0] for c in CRISES]
        ax.bar(x + (i - 1) * w, vals, w, label=lab, color=colors[lab])
    ax.set_xticks(x); ax.set_xticklabels(CRISES)
    ax.set_ylabel("Share of bills rejected, by value (%)")
    ax.set_title("Did the Bank turn émigré paper away more often?\n"
                 "émigré rejection sits at or below the window average; only the old English\n"
                 "private banks were refused less", fontsize=12)
    ax.legend(frameon=False, fontsize=9)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout(); fig.savefig(FIG / "e1_rejection_by_origin.png", dpi=170); plt.close(fig)
    print("E1 rejection by value:")
    print(tab.pivot(index="group", columns="crisis", values="rejection_rate_pct").to_string())


# ---------------- E2 ----------------
def e2_rate_vs_size(t):
    cl = t[t.origin_group != "Unclassified (long tail)"].copy()
    house = (cl.groupby(["canonical_house", "origin_group", "crisis"])
               .agg(value=("value", "sum"), rate=("rate", "mean"), n=("value", "size")).reset_index())
    house = house[house["value"] > 0]
    house["cat"] = np.where(house.origin_group.isin(EM), "Émigré",
                            np.where(house.origin_group.isin(BR_NATIVE), "British", "Other"))
    col = {"Émigré": "#b2182b", "British": "#2166ac", "Other": "#cccccc"}

    fig, axes = plt.subplots(1, 3, figsize=(11.5, 4.3), sharey=True)
    for ax, cr in zip(axes, CRISES):
        g = house[house.crisis == cr]
        for cat in ["Other", "British", "Émigré"]:
            s = g[g.cat == cat]
            ax.scatter(np.log10(s["value"]), s["rate"], s=22 + 3 * s["n"], c=col[cat],
                       alpha=0.75, edgecolors="white", linewidths=0.4, label=cat)
        ax.set_title(cr); ax.set_xlabel("house size: log10 of total crisis lending (£)")
        ax.grid(alpha=0.2)
    axes[0].set_ylabel("mean rate paid (% p.a.)")
    axes[0].legend(frameon=False, fontsize=8, loc="upper right")
    fig.suptitle("No penalty for being foreign: émigré houses (red) pay no more than British houses (blue) of the same size",
                 fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(FIG / "e2_rate_vs_size.png", dpi=170); plt.close(fig)

    # size-tier summary table (large = top half by value within crisis)
    rows = []
    for cr in CRISES:
        g = house[house.crisis == cr].copy()
        med = g["value"].median()
        for tier, mask in [("larger", g["value"] >= med), ("smaller", g["value"] < med)]:
            gg = g[mask]
            for cat in ["Émigré", "British"]:
                sub = gg[gg.cat == cat]
                rows.append({"crisis": cr, "tier": tier, "group": cat,
                             "mean_rate": round(sub["rate"].mean(), 2), "n_houses": len(sub)})
    pd.DataFrame(rows).to_csv(TAB / "e2_rate_by_size_tier.csv", index=False)
    print("\nE2 mean rate by size tier (émigré vs British):")
    print(pd.DataFrame(rows).pivot_table(index=["crisis", "tier"], columns="group", values="mean_rate").to_string())


# ---------------- E3 ----------------
def e3_top_houses(t):
    print("\nE3 biggest names:")
    for cr in CRISES:
        g = (t[t.crisis == cr].groupby(["canonical_house", "origin_group"])["value"].sum()
             .reset_index().sort_values("value", ascending=False))
        g = g[g.canonical_house != "(unclassified)"].head(20).reset_index(drop=True)
        g["rank"] = g.index + 1
        g["emigre"] = g.origin_group.isin(EM)
        g["origin_short"] = g.origin_group.map(SHORT)
        g[["rank", "canonical_house", "origin_short", "value", "emigre"]].to_csv(
            TAB / f"e3_top_houses_{cr}.csv", index=False)
        print(f"  {cr}: émigré in top-20 = {int(g['emigre'].sum())}/20")


def main():
    t = load()
    e1_rejection(t)
    e2_rate_vs_size(t)
    e3_top_houses(t)
    print("\nWrote e1_*, e2_*, e3_* tables -> outputs/tables/ ; 2 figures -> outputs/figures/")


if __name__ == "__main__":
    main()
