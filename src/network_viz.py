"""Outsiders at the Window — Stage 3b: readable network visualisations.

Replaces the earlier unreadable node-link dumps with reader-facing figures:

  net1_1914_intermediation_sankey.png  Sankey: country -> London house -> Bank
  net2_group_cotiming_heatmap.png      origin-group x origin-group co-timing affinity
  net2_affiliation_clean.png           cleaned co-timing graph (top nodes labelled)

Also exports GraphML for hand-polishing in Gephi:
  outputs/net1_intermediation.graphml, outputs/net2_affiliation.graphml

No extra dependencies — pure matplotlib + networkx.
"""
from __future__ import annotations
import re
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
import numpy as np
import pandas as pd
import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.path import Path as MPath
import matplotlib.patheffects as pe

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "outputs"
FIG = OUT / "figures"

ORIGIN_COLORS = {
    "Émigré: German & Central European": "#b2182b",
    "Émigré: Greek & Levantine": "#ef8a62",
    "Émigré: Indian / Parsi": "#f4a582",
    "Émigré: American": "#d6604d",
    "British: private / merchant (native)": "#2166ac",
    "British: discount house": "#4393c3",
    "British: clearing / joint-stock bank": "#92c5de",
    "Colonial / Imperial bank": "#1b7837",
    "Foreign bank (1914 wartime)": "#762a83",
}

# beneficiary name -> geographic origin (approximate; big flows are confident)
REGION_RULES = [
    ("France", ["lyonnais", "soc gen", "societe", "ste gee", "credit indue", "credit mobil",
                "credit mohler", "de pury", "de clermont", "le lacheut", "lefevre", "fishchel"]),
    ("Russia", ["russ", "rusec asiatic"]),
    ("Germany & C. Europe", ["deutsche", "dresdner", "disconto", "erlanger", "waecht", "waechl",
                             "besslet", "beasler", "brinkmann", "schneider", "brandies goldschmidt",
                             "westman", "auerbach", "averlock", "k.k", "laender", "lander", "stern & co",
                             "f.stern", "becker", "sanders rehders", "rofner", "schloesse"]),
    ("Ottoman & Near East", ["ottoman", "turkey", "romania", "egypt"]),
    ("South America", ["chil", "nitrate", "b.a.g.s", "antofagasta", "bolivia", "uruguay",
                       "banco de", "la guaira", "jaltal"]),
    ("Asia & East", ["taiwan", "chartered bk of sc", "asiatic", "manganese", "indian"]),
    ("Africa", ["african", "africa"]),
    ("North America", ["new york", " ny", "guaranty", "natl park"]),
    ("UK domestic / provincial", ["bradford", "sheffield", "district bank", "munster", "mumster",
                                  "leinster", "provincial bk of ireland", "lothbury", "southwark",
                                  "fenchurch", "old broad", "leadenhall", "wood st", "cannon st",
                                  "regent st", "finchley", "westminister", "barbican", "cornhill",
                                  "biggerstaff", "cory bros", "clyde", "dalgety", "guinness mahon"]),
]


def load():
    t = pd.read_parquet(DATA / "transactions_tagged.parquet")
    t["crisis"] = t["crisis"].astype(str)
    t["value"] = t["total_amount"].fillna(t["value_discounted"]).fillna(t["amount_advanced_total"])
    t["date"] = pd.to_datetime(t["date"].astype("int64"), unit="us")
    t["day"] = t["date"].dt.date
    return t


def region_of(name: str) -> str:
    n = str(name).lower()
    for region, keys in REGION_RULES:
        if any(k in n for k in keys):
            return region
    return "Other / unidentified"


# ---------- generic Sankey helpers ----------
def _stack(items, total_h=1.0, gap_frac=0.012):
    """items: list of (label, value). Return dict label -> (y0, y1) top-down."""
    vals = [v for _, v in items]
    n = len(items)
    gap = gap_frac * total_h
    scale = (total_h - gap * (n - 1)) / sum(vals)
    pos, y = {}, total_h
    for lab, v in items:
        h = v * scale
        pos[lab] = (y - h, y)
        y -= h + gap
    return pos, scale


def _ribbon(ax, xl, yl0, yl1, xr, yr0, yr1, color, alpha=0.62):
    cx = (xl + xr) / 2
    verts = [(xl, yl1), (cx, yl1), (cx, yr1), (xr, yr1),
             (xr, yr0), (cx, yr0), (cx, yl0), (xl, yl0), (xl, yl1)]
    codes = [MPath.MOVETO, MPath.CURVE4, MPath.CURVE4, MPath.CURVE4,
             MPath.LINETO, MPath.CURVE4, MPath.CURVE4, MPath.CURVE4, MPath.CLOSEPOLY]
    ax.add_patch(patches.PathPatch(MPath(verts, codes), facecolor=color, edgecolor="none", alpha=alpha))


def sankey_intermediation(t):
    oaf = t[t["on_account_for"].notna() & (t["on_account_for"].astype(str).str.strip() != "")].copy()
    oaf["region"] = oaf["on_account_for"].astype(str).map(region_of)
    oaf["presenter"] = oaf["canonical_house"].where(oaf["canonical_house"] != "(unclassified)",
                                                     oaf["counterparty_clean"])
    # top 8 presenters, rest -> "Other houses"
    top_pres = oaf.groupby("presenter")["value"].sum().nlargest(8).index.tolist()
    oaf["house"] = oaf["presenter"].where(oaf["presenter"].isin(top_pres), "Other houses")

    flows = oaf.groupby(["region", "house"])["value"].sum().reset_index()
    region_tot = flows.groupby("region")["value"].sum().sort_values(ascending=False)
    house_tot = flows.groupby("house")["value"].sum().sort_values(ascending=False)
    # keep "Other houses" / "Other / unidentified" at the bottom of their columns
    regions = [r for r in region_tot.index if r != "Other / unidentified"] + \
              (["Other / unidentified"] if "Other / unidentified" in region_tot.index else [])
    houses = [h for h in house_tot.index if h != "Other houses"] + \
             (["Other houses"] if "Other houses" in house_tot.index else [])
    boe_tot = flows["value"].sum()

    rpos, _ = _stack([(r, region_tot[r]) for r in regions])
    hpos, _ = _stack([(h, house_tot[h]) for h in houses])
    bpos, _ = _stack([("Bank of England", boe_tot)])

    cmap = plt.cm.tab10
    rcolor = {r: cmap(i % 10) for i, r in enumerate(regions)}

    fig, ax = plt.subplots(figsize=(15, 10))
    x0, x1, x2 = 0.10, 0.55, 0.97
    bw = 0.012  # node bar width

    # running offsets
    r_off = {r: rpos[r][1] for r in regions}                 # country right edge, top-down
    h_in = {h: hpos[h][1] for h in houses}                   # house left edge
    h_out = {h: hpos[h][1] for h in houses}                  # house right edge
    b_off = bpos["Bank of England"][1]

    # stage 1: region -> house (iterate house-major so house-left stacks by region order)
    for h in houses:
        sub = flows[flows["house"] == h].set_index("region").reindex(regions).dropna()
        for r, row in sub.iterrows():
            v = row["value"]; sc_r = (rpos[r][1]-rpos[r][0])/region_tot[r]; sc_h=(hpos[h][1]-hpos[h][0])/house_tot[h]
            ly1 = r_off[r]; ly0 = ly1 - v*sc_r; r_off[r] = ly0
            ry1 = h_in[h]; ry0 = ry1 - v*sc_h; h_in[h] = ry0
            _ribbon(ax, x0+bw, ly0, ly1, x1, ry0, ry1, rcolor[r])
    # stage 2: house -> BoE (same region order so colours carry through)
    for h in houses:
        sub = flows[flows["house"] == h].set_index("region").reindex(regions).dropna()
        for r, row in sub.iterrows():
            v = row["value"]; sc_h=(hpos[h][1]-hpos[h][0])/house_tot[h]; sc_b=(bpos["Bank of England"][1]-bpos["Bank of England"][0])/boe_tot
            ly1 = h_out[h]; ly0 = ly1 - v*sc_h; h_out[h] = ly0
            ry1 = b_off; ry0 = ry1 - v*sc_b; b_off = ry0
            _ribbon(ax, x1+bw, ly0, ly1, x2, ry0, ry1, rcolor[r], alpha=0.5)

    # draw nodes + labels
    def bar(x, y0, y1, color="#333"):
        ax.add_patch(patches.Rectangle((x, y0), bw, y1-y0, color=color, zorder=3))
    for r in regions:
        y0, y1 = rpos[r]; bar(x0, y0, y1, rcolor[r])
        ax.text(x0-0.008, (y0+y1)/2, f"{r}  £{region_tot[r]/1e6:.2f}m", ha="right", va="center", fontsize=9)
    for h in houses:
        y0, y1 = hpos[h]; bar(x1, y0, y1)
        ax.text(x1+bw+0.006, (y0+y1)/2, f"{h}  £{house_tot[h]/1e6:.2f}m", ha="left", va="center", fontsize=8.5)
    y0, y1 = bpos["Bank of England"]; bar(x2, y0, y1, "#000")
    ax.text(x2+bw+0.004, (y0+y1)/2, f"Bank of England\n£{boe_tot/1e6:.1f}m", ha="left", va="center", fontsize=10, fontweight="bold")

    ax.text(x0, 1.035, "WHERE THE MONEY WAS FOR", fontsize=8, color="#666", ha="left")
    ax.text(x1, 1.035, "LONDON PRESENTING HOUSE", fontsize=8, color="#666", ha="left")
    ax.set_xlim(-0.02, 1.18); ax.set_ylim(-0.02, 1.08); ax.axis("off")
    ax.set_title("1914: how the world reached the Bank of England\n"
                 "overseas banks discounted through London houses — 76% of intermediated value was for foreign account",
                 fontsize=13, loc="left")
    fig.tight_layout(); fig.savefig(FIG / "net1_1914_intermediation_sankey.png", dpi=170, bbox_inches="tight")
    plt.close(fig)
    print("sankey: regions", len(regions), "houses", len(houses), "| total £%.1fm" % (boe_tot/1e6))

    # GraphML (directed, for Gephi)
    G = nx.DiGraph()
    for _, row in flows.iterrows():
        G.add_node(row["region"], kind="region")
        G.add_node(row["house"], kind="london_house")
        G.add_edge(row["region"], row["house"], weight=float(row["value"]))
    for h in houses:
        G.add_edge(h, "Bank of England", weight=float(house_tot[h]))
    G.nodes["Bank of England"]["kind"] = "apex"
    nx.write_graphml(G, OUT / "net1_intermediation.graphml")


# ---------- NET 2: co-timing graph (rebuild) ----------
def build_cotiming(t, min_shared=2, min_cos=0.30):
    cl = t[t["origin_group"] != "Unclassified (long tail)"].copy()
    shared = Counter(); days_of = defaultdict(set)
    val = cl.groupby("canonical_house")["value"].sum().to_dict()
    grp = cl.groupby("canonical_house")["origin_group"].agg(lambda s: s.mode().iloc[0]).to_dict()
    for day, d in cl.groupby("day"):
        hs = sorted(d["canonical_house"].unique())
        for h in hs:
            days_of[h].add(day)
        for a, b in combinations(hs, 2):
            shared[(a, b)] += 1
    G = nx.Graph()
    for h in val:
        G.add_node(h, value=float(val[h]), origin_group=grp[h])
    for (a, b), c in shared.items():
        if c >= min_shared:
            cos = c / np.sqrt(len(days_of[a]) * len(days_of[b]))
            if cos >= min_cos:
                G.add_edge(a, b, weight=round(float(cos), 3))
    G.remove_nodes_from([n for n in list(G.nodes()) if G.degree(n) == 0])
    return G


def heatmap_groups(G):
    groups = sorted({G.nodes[n]["origin_group"] for n in G.nodes()})
    idx = {g: i for i, g in enumerate(groups)}
    members = defaultdict(list)
    for n in G.nodes():
        members[G.nodes[n]["origin_group"]].append(n)
    W = np.zeros((len(groups), len(groups)))
    for u, v, d in G.edges(data=True):
        gu, gv = G.nodes[u]["origin_group"], G.nodes[v]["origin_group"]
        W[idx[gu], idx[gv]] += d["weight"]; W[idx[gv], idx[gu]] += d["weight"]
    # normalise by number of possible pairs between groups -> mean co-timing affinity
    A = np.zeros_like(W)
    for gi in groups:
        for gj in groups:
            i, j = idx[gi], idx[gj]
            ni, nj = len(members[gi]), len(members[gj])
            denom = ni * (ni - 1) / 2 if gi == gj else ni * nj
            A[i, j] = W[i, j] / denom if denom else 0
    assort = nx.attribute_assortativity_coefficient(G, "origin_group")

    short = [g.replace("Émigré: ", "É:").replace("British: ", "Br:").replace(" & Central European", " C.Eur")
              .replace(" & Levantine", "/Lev").replace(" / joint-stock bank", " clearing")
              .replace(" / merchant (native)", " merch").replace(" house", "").replace("Colonial / Imperial bank", "Colonial")
              .replace("Foreign bank (1914 wartime)", "Foreign'14").replace(" / Parsi", "/Parsi") for g in groups]
    fig, ax = plt.subplots(figsize=(9.5, 8))
    im = ax.imshow(A, cmap="Purples")
    ax.set_xticks(range(len(groups))); ax.set_xticklabels(short, rotation=40, ha="right", fontsize=9)
    ax.set_yticks(range(len(groups))); ax.set_yticklabels(short, fontsize=9)
    mx = A.max()
    for i in range(len(groups)):
        for j in range(len(groups)):
            if A[i, j] > 0:
                ax.text(j, i, f"{A[i,j]:.2f}", ha="center", va="center", fontsize=8,
                        color="white" if A[i, j] > mx*0.6 else "#333")
    fig.colorbar(im, ax=ax, shrink=0.7, label="mean co-timing affinity (cosine / possible pair)")
    ax.set_title(f"Do the outsiders cluster? Origin-group co-timing at the window\n"
                 f"diagonal = within-group; origin assortativity = {assort:+.3f} (≈0 ⇒ no ethnic homophily)",
                 fontsize=12)
    fig.tight_layout(); fig.savefig(FIG / "net2_group_cotiming_heatmap.png", dpi=170)
    plt.close(fig)
    print(f"heatmap: {len(groups)} groups | origin assortativity {assort:+.3f}")


def clean_nodelink(G):
    lcc = max(nx.connected_components(G), key=len)
    H = G.subgraph(lcc).copy()
    wdeg = dict(H.degree(weight="weight"))
    pos = nx.spring_layout(H, weight="weight", k=1.9, iterations=600, seed=11)
    vmax = max(nx.get_node_attributes(H, "value").values())
    sizes = [120 + 2600 * (H.nodes[n]["value"] / vmax) for n in H.nodes()]
    colors = [ORIGIN_COLORS.get(H.nodes[n]["origin_group"], "#ccc") for n in H.nodes()]
    ew = np.array([d["weight"] for *_, d in H.edges(data=True)])
    fig, ax = plt.subplots(figsize=(16, 12))
    nx.draw_networkx_edges(H, pos, width=0.2 + 2.2*(ew/ew.max()), edge_color="#d4d4d4", alpha=0.45, ax=ax)
    nx.draw_networkx_nodes(H, pos, node_size=sizes, node_color=colors, edgecolors="white", linewidths=1.0, ax=ax)
    # label the 10 most central, nudged above the node with a leader dot, to reduce pile-up
    top = sorted(wdeg, key=wdeg.get, reverse=True)[:10]
    ys = sorted(pos[n][1] for n in pos)
    dy = (ys[-1] - ys[0]) * 0.035
    for n in top:
        x, y = pos[n]
        txt = ax.annotate(n, (x, y), xytext=(x, y + dy), fontsize=9.5, ha="center", va="bottom", zorder=6,
                          arrowprops=dict(arrowstyle="-", color="#888", lw=0.5))
        txt.set_path_effects([pe.withStroke(linewidth=3.5, foreground="white")])
    present = [g for g in ORIGIN_COLORS if g in nx.get_node_attributes(H, "origin_group").values()]
    handles = [plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=ORIGIN_COLORS[g], markersize=11, label=g)
               for g in present]
    ax.legend(handles=handles, loc="lower left", fontsize=9, frameon=False)
    ax.set_title("Who comes to the Bank's window together (co-timing), coloured by ORIGIN\n"
                 "node size = total lending · only the 10 most central houses are labelled · "
                 "émigré (reds) sit among British (blues), not apart", fontsize=13)
    ax.axis("off"); fig.tight_layout(); fig.savefig(FIG / "net2_affiliation_clean.png", dpi=170)
    plt.close(fig)
    nx.write_graphml(G, OUT / "net2_affiliation.graphml")
    print(f"clean node-link: {H.number_of_nodes()} nodes (giant component) / {H.number_of_edges()} edges")


SHORT = {
    "Émigré: German & Central European": "É: German/C.Eur",
    "Émigré: Greek & Levantine": "É: Greek/Lev",
    "Émigré: Indian / Parsi": "É: Indian/Parsi",
    "Émigré: American": "É: American",
    "British: private / merchant (native)": "Br: merchant",
    "British: discount house": "Br: discount",
    "British: clearing / joint-stock bank": "Br: clearing",
    "Colonial / Imperial bank": "Colonial",
    "Foreign bank (1914 wartime)": "Foreign 1914",
}


def mixing_bar(G, min_n=8):
    """Option A: for each origin large enough to test (>= min_n houses), observed
    same-origin partner share vs the share expected under random mixing. Groups with
    too few houses have an unreliable random baseline and are listed, not plotted."""
    grp = nx.get_node_attributes(G, "origin_group")
    all_groups = [g for g in ORIGIN_COLORS if g in set(grp.values())]
    N = G.number_of_nodes()
    counts = {g: sum(1 for n in G if grp[n] == g) for g in all_groups}
    obs, exp = {}, {}
    for g in all_groups:
        nodes_g = [n for n in G if grp[n] == g]
        fr = [sum(1 for u in G.neighbors(v) if grp[u] == g) / G.degree(v)
              for v in nodes_g if G.degree(v)]
        obs[g] = float(np.mean(fr)) if fr else 0.0
        exp[g] = (len(nodes_g) - 1) / (N - 1) if N > 1 else 0.0
    assort = nx.attribute_assortativity_coefficient(G, "origin_group")

    groups = [g for g in all_groups if counts[g] >= min_n]
    small = [g for g in all_groups if counts[g] < min_n]
    x = np.arange(len(groups))
    fig, ax = plt.subplots(figsize=(10.5, 6.2))
    ax.bar(x, [obs[g] * 100 for g in groups], color=[ORIGIN_COLORS[g] for g in groups], width=0.6, zorder=2)
    for i, g in enumerate(groups):
        ax.plot([i - 0.33, i + 0.33], [exp[g] * 100, exp[g] * 100], color="black", lw=2.4, zorder=3)
        ax.text(i, obs[g] * 100 + 0.8, f"n={counts[g]}", ha="center", va="bottom", fontsize=8.5, color="#555")
    ax.set_xticks(x); ax.set_xticklabels([SHORT[g] for g in groups], rotation=25, ha="right", fontsize=9.5)
    ax.set_ylabel("Share of same-day partners that share the house's own origin (%)")
    ax.set_title("Do houses of the same origin stick together?\n"
                 f"coloured bar = observed; black line = expected if mixing were random; "
                 f"origin assortativity {assort:+.3f}", fontsize=12)
    handles = [plt.Rectangle((0, 0), 1, 1, color="#888"), plt.Line2D([0], [0], color="black", lw=2.4)]
    ax.legend(handles, ["observed same-origin share", "expected if random"], frameon=False, fontsize=9.5)
    ax.set_ylim(0, max(obs[g] for g in groups) * 100 * 1.22 + 1)
    ax.grid(axis="y", alpha=0.25)
    note = "Too few houses to test (n < %d), not shown: " % min_n + \
           "; ".join(f"{SHORT[g]} (n={counts[g]})" for g in small)
    ax.text(0.0, -0.30, note, transform=ax.transAxes, fontsize=8.5, color="#444")
    fig.tight_layout(); fig.savefig(FIG / "net2_mixing_bar.png", dpi=170, bbox_inches="tight"); plt.close(fig)
    print(f"mixing bar: {len(groups)} testable groups, {len(small)} small omitted | assortativity {assort:+.3f}")


def ordered_matrix(G):
    """Option C (appendix): the co-timing network as a matrix, rows/cols ordered by
    origin. Clustering would show as dark blocks on the diagonal; here there are none."""
    grp = nx.get_node_attributes(G, "origin_group")
    groups = [g for g in ORIGIN_COLORS if g in set(grp.values())]
    order = sorted(G.nodes(), key=lambda n: (groups.index(grp[n]), n))
    idx = {n: i for i, n in enumerate(order)}
    n = len(order)
    M = np.zeros((n, n))
    for u, v, d in G.edges(data=True):
        M[idx[u], idx[v]] = d["weight"]; M[idx[v], idx[u]] = d["weight"]

    fig, ax = plt.subplots(figsize=(11, 10))
    vmax = np.percentile(M[M > 0], 95) if (M > 0).any() else 1
    ax.imshow(M, cmap="Greys", vmax=vmax)
    # group boundaries and labels
    sizes = [sum(1 for nd in order if grp[nd] == g) for g in groups]
    bounds = np.cumsum([0] + sizes)
    for b in bounds[1:-1]:
        ax.axhline(b - 0.5, color="#cc2222", lw=0.7); ax.axvline(b - 0.5, color="#cc2222", lw=0.7)
    centers = [(bounds[i] + bounds[i + 1]) / 2 - 0.5 for i in range(len(groups))]
    ax.set_xticks(centers); ax.set_xticklabels([SHORT[g] for g in groups], rotation=40, ha="right", fontsize=8)
    ax.set_yticks(centers); ax.set_yticklabels([SHORT[g] for g in groups], fontsize=8)
    for tick, g in zip(ax.get_xticklabels(), groups):
        tick.set_color(ORIGIN_COLORS[g])
    for tick, g in zip(ax.get_yticklabels(), groups):
        tick.set_color(ORIGIN_COLORS[g])
    ax.set_title("The co-timing network as an ordered matrix\n"
                 "rows and columns are houses grouped by origin; darker = more shared days",
                 fontsize=11)
    fig.tight_layout(); fig.savefig(FIG / "net2_cotiming_matrix.png", dpi=170); plt.close(fig)
    print("ordered matrix:", n, "houses")


def main():
    t = load()
    sankey_intermediation(t)
    G2 = build_cotiming(t)
    heatmap_groups(G2)
    clean_nodelink(G2)
    mixing_bar(G2)
    ordered_matrix(G2)
    print("\nWrote: net1_1914_intermediation_sankey.png, net2_group_cotiming_heatmap.png, "
          "net2_affiliation_clean.png + 2 .graphml in outputs/")


if __name__ == "__main__":
    main()
