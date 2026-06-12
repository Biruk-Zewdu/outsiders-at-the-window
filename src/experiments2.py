"""Two further tests added in the primary-source pass.

  E4  Did the Bank turn on the émigré houses once the war began? Split the 1914
      ledger at the declaration of war (4 Aug 1914) and compare the Bank's treatment
      of émigré houses, before and after, against the whole window. This is the
      tightest form of the paper's claim: the political reversal (Parliament, the
      Gazette) has no counterpart in the Bank's own behaviour in the same months.
      -> e4_wartime_treatment.png, e4_wartime_treatment.csv

  E5  Make "no penalty for being foreign" rigorous. Within each crisis, regress the
      rate a house paid on its size (log10 value) and an émigré dummy, and report the
      émigré coefficient with a confidence interval. If it sits on zero, origin adds
      nothing to price once size is controlled.
      -> e5_rate_regression.csv

Dates in the ledger are stored as microsecond integers mis-read as 1969; recover with
pd.to_datetime(int64, unit='us') as the other scripts do.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats
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
WAR = pd.Timestamp("1914-08-04")          # Britain declares war on Germany


def load():
    t = pd.read_parquet(DATA / "transactions_tagged.parquet")
    t["crisis"] = t["crisis"].astype(str)
    t["date"] = pd.to_datetime(t["date"].astype("int64"), unit="us")
    t["value"] = t["total_amount"].fillna(t["value_discounted"]).fillna(t["amount_advanced_total"])
    t["is_emigre"] = t["origin_group"].isin(EM)
    return t


def rej_rate(df):
    d = df[df["transaction_type"] == "discount"]
    vb = d["value_brought"].sum()
    return 100 * d["value_bills_rejected"].fillna(0).sum() / vb if vb else np.nan


# ---------------- E4 ----------------
def e4_wartime(t):
    n = t[t.crisis == "1914"].copy()
    n["month"] = n.date.dt.to_period("M").astype(str)
    n["era"] = np.where(n.date < WAR, "pre-war", "war")

    # monthly émigré share (drop Dec: only two émigré tickets, window winding down)
    months = ["1914-07", "1914-08", "1914-09", "1914-10", "1914-11"]
    share = []
    for m in months:
        g = n[n.month == m]
        share.append(100 * g[g.is_emigre]["value"].sum() / g["value"].sum())

    # pre/war treatment, émigré vs whole window
    rows = []
    for era in ["pre-war", "war"]:
        g = n[n.era == era]
        em = g[g.is_emigre]
        rows.append({"era": era, "group": "Émigré houses", "mean_rate": round(em["rate"].mean(), 2),
                     "rejection_pct": round(rej_rate(em), 2), "n": len(em),
                     "value": round(em["value"].sum())})
        rows.append({"era": era, "group": "All borrowers", "mean_rate": round(g["rate"].mean(), 2),
                     "rejection_pct": round(rej_rate(g), 2), "n": len(g),
                     "value": round(g["value"].sum())})
    tab = pd.DataFrame(rows)
    tab.to_csv(TAB / "e4_wartime_treatment.csv", index=False)

    fig, (axA, axB) = plt.subplots(1, 2, figsize=(11, 4.4))
    # Panel A: monthly émigré share, war line
    xs = np.arange(len(months))
    axA.bar(xs, share, color="#b2182b", width=0.6)
    axA.axvline(0.9, color="black", ls="--", lw=1)
    axA.text(0.95, max(share) * 0.96, "Britain declares\nwar, 4 Aug", fontsize=8, va="top")
    axA.set_xticks(xs); axA.set_xticklabels([m[5:] + "\n1914" for m in months])
    axA.set_ylabel("Émigré share of window lending (%)")
    axA.set_title("They kept coming, all through the war months")
    for x, v in zip(xs, share):
        axA.text(x, v + 0.3, f"{v:.0f}%", ha="center", fontsize=8)
    axA.grid(axis="y", alpha=0.25)

    # Panel B: rejection, pre vs war, émigré vs window
    eras = ["pre-war", "war"]
    em_rej = [tab[(tab.era == e) & (tab.group == "Émigré houses")]["rejection_pct"].iloc[0] for e in eras]
    all_rej = [tab[(tab.era == e) & (tab.group == "All borrowers")]["rejection_pct"].iloc[0] for e in eras]
    x = np.arange(2); w = 0.35
    axB.bar(x - w / 2, em_rej, w, label="Émigré houses", color="#b2182b")
    axB.bar(x + w / 2, all_rej, w, label="All borrowers", color="#999999")
    axB.set_xticks(x); axB.set_xticklabels(["before war\n(Jul–3 Aug)", "war\n(4 Aug–Dec)"])
    axB.set_ylabel("Share of bills rejected (%)")
    axB.set_title("When the Bank tightened, it tightened on everyone")
    axB.legend(frameon=False, fontsize=8)
    for xi, v in zip([x[0] - w / 2, x[1] - w / 2], em_rej):
        axB.text(xi, v + 0.07, f"{v:.1f}", ha="center", fontsize=8)
    for xi, v in zip([x[0] + w / 2, x[1] + w / 2], all_rej):
        axB.text(xi, v + 0.07, f"{v:.1f}", ha="center", fontsize=8)
    axB.grid(axis="y", alpha=0.25)

    fig.suptitle("After war was declared, the Bank did not turn on the émigré houses",
                 fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(FIG / "e4_wartime_treatment.png", dpi=170); plt.close(fig)
    print("E4 wartime treatment (émigré vs window):")
    print(tab.to_string(index=False))
    print(f"  monthly émigré share Jul–Nov: {[round(s) for s in share]}")


# ---------------- E5 ----------------
def e5_regression(t):
    cl = t[t.origin_group.isin(EM + BR_NATIVE)].copy()
    house = (cl.groupby(["canonical_house", "origin_group", "crisis"])
               .agg(value=("value", "sum"), rate=("rate", "mean")).reset_index())
    house = house[(house["value"] > 0) & house["rate"].notna()]
    house["emigre"] = house.origin_group.isin(EM).astype(float)
    house["logval"] = np.log10(house["value"])

    rows = []
    for cr in ["1857", "1866", "1914"]:
        g = house[house.crisis == cr]
        y = g["rate"].values
        X = np.column_stack([np.ones(len(g)), g["logval"].values, g["emigre"].values])
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        resid = y - X @ beta
        dof = len(g) - X.shape[1]
        sigma2 = (resid @ resid) / dof
        cov = sigma2 * np.linalg.inv(X.T @ X)
        se = np.sqrt(np.diag(cov))
        b_em, se_em = beta[2], se[2]
        tval = b_em / se_em
        p = 2 * stats.t.sf(abs(tval), dof)
        ci = stats.t.ppf(0.975, dof) * se_em
        rows.append({"crisis": cr, "n_houses": len(g),
                     "emigre_coef_on_rate": round(b_em, 3), "std_error": round(se_em, 3),
                     "ci95_low": round(b_em - ci, 3), "ci95_high": round(b_em + ci, 3),
                     "p_value": round(p, 3), "size_coef": round(beta[1], 3)})
    out = pd.DataFrame(rows)
    out.to_csv(TAB / "e5_rate_regression.csv", index=False)
    print("\nE5 rate ~ log10(size) + émigré dummy  (coefficient on émigré, % points):")
    print(out.to_string(index=False))


def main():
    t = load()
    e4_wartime(t)
    e5_regression(t)
    print("\nWrote e4_*, e5_* -> outputs/ ; figure -> e4_wartime_treatment.png")


if __name__ == "__main__":
    main()
