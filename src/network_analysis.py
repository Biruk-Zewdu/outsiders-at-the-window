"""Outsiders at the Window — Stage 3 network analysis.

Two networks, both plotted (the professor's W4 deck favours network plots):

  NET 1 — 1914 intermediation network (directed).
    From the `on_account_for` field: ultimate beneficiary -> presenting London
    house -> Bank of England. Shows London's clearing/discount houses acting as
    conduits through which overseas banks reached the Bank in Aug-Dec 1914.
    Centrality (weighted degree, betweenness) answers "who were the main players".

  NET 2 — affiliation / community network (undirected, all three crises).
    Houses are linked when they appear at the Bank's window on the SAME DAY
    (a two-mode house x day affiliation, projected to house-house). Restricted to
    origin-classified houses. Community detection (greedy modularity) tests whether
    the émigré *diaspora* community is also a *structural* community at the window.

Dates in the source parquet are stored in microseconds but mis-tagged; we recover
them with unit='us' (verified: 1857 Sep-Dec, 1866 Mar-Jun, 1914 Jul-Dec).
"""
from __future__ import annotations
import re
from pathlib import Path
import numpy as np
import pandas as pd
import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TAB = ROOT / "outputs" / "tables"
FIG = ROOT / "outputs" / "figures"
TAB.mkdir(parents=True, exist_ok=True); FIG.mkdir(parents=True, exist_ok=True)

ORIGIN_COLORS = {
    "Émigré: German & Central European": "#b2182b",
    "Émigré: Greek & Levantine": "#ef8a62",
    "Émigré: Indian / Parsi": "#fddbc7",
    "Émigré: American": "#d6604d",
    "British: private / merchant (native)": "#2166ac",
    "British: discount house": "#4393c3",
    "British: clearing / joint-stock bank": "#92c5de",
    "Colonial / Imperial bank": "#1b7837",
    "Foreign bank (1914 wartime)": "#762a83",
    "Unclassified (long tail)": "#cccccc",
}

OVERSEAS = ["lyonnais", "soc gen", "societe", "generale", "russ", "banco", "banca",
            "egypt", "asiatic", "chil", "romania", "ottoman", "erlanger", "nitrate",
            "b.a.g.s", "african", "credit indue", "indue", "warms", "besslet",
            "natl bk of egypt", "rys", "rly", "de credit"]
LONDON_PLACE = ["lothbury", "southwark", "fenchurch", "lombard", "cornhill", "threadneedle",
                "westminster br", "city br"]


def load():
    t = pd.read_parquet(DATA / "transactions_tagged.parquet")
    t["crisis"] = t["crisis"].astype(str)
    t["value"] = t["total_amount"].fillna(t["value_discounted"]).fillna(t["amount_advanced_total"])
    t["date"] = pd.to_datetime(t["date"].astype("int64"), unit="us")  # recover true dates
    t["day"] = t["date"].dt.date
    return t


def beneficiary_kind(name: str) -> str:
    n = str(name).lower()
    if any(k in n for k in OVERSEAS):
        return "overseas bank/firm"
    if any(k in n for k in LONDON_PLACE):
        return "London branch/place"
    if "bank" in n or "bk" in n or "banking" in n:
        return "domestic/provincial bank"
    return "firm / other"


# ============================ NET 1 ============================
def net1_intermediation(t):
    oaf = t[t["on_account_for"].notna() & (t["on_account_for"].astype(str).str.strip() != "")].copy()
    oaf["beneficiary"] = oaf["on_account_for"].astype(str).str.strip()
    oaf["presenter"] = oaf["canonical_house"].where(oaf["canonical_house"] != "(unclassified)",
                                                     oaf["counterparty_clean"])
    BOE = "Bank of England"

    G = nx.DiGraph()
    # beneficiary -> presenter
    bp = oaf.groupby(["beneficiary", "presenter"])["value"].agg(["sum", "size"]).reset_index()
    for _, r in bp.iterrows():
        G.add_edge(r["beneficiary"], r["presenter"], weight=float(r["sum"]), n=int(r["size"]))
    # presenter -> BoE
    pv = oaf.groupby("presenter")["value"].sum()
    for pres, v in pv.items():
        G.add_edge(pres, BOE, weight=float(v), n=int((oaf["presenter"] == pres).sum()))

    presenters = set(oaf["presenter"]); benes = set(oaf["beneficiary"]) - presenters
    for node in G.nodes():
        if node == BOE:
            G.nodes[node].update(role="apex", layer=2, kind="apex")
        elif node in presenters:
            G.nodes[node].update(role="presenter", layer=1, kind="London house")
        else:
            G.nodes[node].update(role="beneficiary", layer=0, kind=beneficiary_kind(node))

    # node table with centrality
    wdeg_in = dict(G.in_degree(weight="weight"))
    wdeg_out = dict(G.out_degree(weight="weight"))
    btw = nx.betweenness_centrality(G, weight="weight")
    nodes = pd.DataFrame([{
        "node": n, "role": G.nodes[n]["role"], "kind": G.nodes[n]["kind"],
        "value_in": wdeg_in.get(n, 0), "value_out": wdeg_out.get(n, 0),
        "betweenness": round(btw.get(n, 0), 4),
        "degree": G.degree(n),
    } for n in G.nodes()]).sort_values(["role", "value_out"], ascending=[True, False])
    nodes.to_csv(TAB / "net1_intermediation_nodes.csv", index=False)

    edges = nx.to_pandas_edgelist(G).rename(columns={"source": "from", "target": "to"})
    edges.sort_values("weight", ascending=False).to_csv(TAB / "net1_intermediation_edges.csv", index=False)

    # top conduits (presenters) by value funnelled to the BoE
    top_pres = nodes[nodes.role == "presenter"].nlargest(12, "value_out")[["node", "value_out", "betweenness", "degree"]]
    top_pres.to_csv(TAB / "net1_top_conduits.csv", index=False)
    # overseas share of intermediated value
    oaf["bkind"] = oaf["beneficiary"].map(beneficiary_kind)
    kind_val = oaf.groupby("bkind")["value"].sum().sort_values(ascending=False)
    kind_val.to_csv(TAB / "net1_beneficiary_kind_value.csv")

    print("=== NET1: 1914 intermediation ===")
    print(f"nodes {G.number_of_nodes()} | edges {G.number_of_edges()} | beneficiaries {len(benes)} | presenters {len(presenters)}")
    print("value by beneficiary kind:")
    for k, v in kind_val.items():
        print(f"  {k:26s} £{v:,.0f} ({100*v/oaf['value'].sum():.0f}%)")
    print("top conduits:")
    print(top_pres.to_string(index=False, formatters={"value_out": "{:,.0f}".format}))

    # NOTE: figures are produced by src/network_viz.py (readable Sankey / heatmap /
    # cleaned node-link). This module only computes the tables + metrics.
    return G


def _plot_net1(G, nodes):
    pos = nx.multipartite_layout(G, subset_key="layer", align="vertical")
    kind_color = {"overseas bank/firm": "#762a83", "domestic/provincial bank": "#4393c3",
                  "London branch/place": "#999999", "firm / other": "#dddddd",
                  "London house": "#1b7837", "apex": "#000000"}
    fig, ax = plt.subplots(figsize=(13, 11))
    vmax = max(nodes["value_out"].max(), nodes["value_in"].max())
    sizes, colors = [], []
    for n in G.nodes():
        v = max(G.nodes[n].get("layer") == 2 and sum(d["weight"] for *_, d in G.in_edges(n, data=True)) or 0,
                dict(G.in_degree(weight="weight")).get(n, 0), dict(G.out_degree(weight="weight")).get(n, 0))
        sizes.append(60 + 1500 * (v / vmax))
        colors.append(kind_color.get(G.nodes[n]["kind"], "#cccccc"))
    ew = np.array([d["weight"] for *_, d in G.edges(data=True)])
    nx.draw_networkx_edges(G, pos, width=0.3 + 3.5 * (ew / ew.max()), edge_color="#888888",
                           alpha=0.5, arrows=True, arrowsize=7, ax=ax)
    nx.draw_networkx_nodes(G, pos, node_size=sizes, node_color=colors, edgecolors="white", linewidths=0.5, ax=ax)
    # label the important nodes
    lab = {n: n for n in G.nodes() if (dict(G.in_degree(weight="weight")).get(n, 0) > 150000
           or dict(G.out_degree(weight="weight")).get(n, 0) > 300000 or n == "Bank of England")}
    nx.draw_networkx_labels(G, pos, labels=lab, font_size=7, ax=ax)
    ax.set_title("1914: how the world reached the Bank of England\n"
                 "ultimate beneficiary (left) → London presenting house (centre) → Bank (right)", fontsize=13)
    handles = [plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=c, markersize=10, label=k)
               for k, c in kind_color.items()]
    ax.legend(handles=handles, loc="lower left", fontsize=8, frameon=False)
    ax.axis("off"); fig.tight_layout()
    fig.savefig(FIG / "net1_1914_intermediation.png", dpi=170); plt.close(fig)


# ============================ NET 2 ============================
def net2_affiliation(t):
    cl = t[t["origin_group"] != "Unclassified (long tail)"].copy()
    # co-TIMING network: houses linked when they appear on the same day, but the
    # edge is COSINE-normalised over each house's set of active days so that the
    # tie measures *disproportionate* co-timing, not just both-houses-being-busy.
    from itertools import combinations
    from collections import Counter, defaultdict
    shared = Counter()
    days_of = defaultdict(set)
    house_val = cl.groupby("canonical_house")["value"].sum().to_dict()
    house_grp = cl.groupby("canonical_house")["origin_group"].agg(lambda s: s.mode().iloc[0]).to_dict()
    house_era = cl.groupby("canonical_house")["crisis"].agg(lambda s: s.mode().iloc[0]).to_dict()
    for day, d in cl.groupby("day"):
        houses = sorted(d["canonical_house"].unique())
        for h in houses:
            days_of[h].add(day)
        for a, b in combinations(houses, 2):
            shared[(a, b)] += 1

    G = nx.Graph()
    for h in house_val:
        G.add_node(h, value=house_val[h], origin_group=house_grp[h], era=house_era[h])
    MIN_SHARED, MIN_COS = 2, 0.30
    for (a, b), c in shared.items():
        if c < MIN_SHARED:
            continue
        cos = c / np.sqrt(len(days_of[a]) * len(days_of[b]))
        if cos >= MIN_COS:
            G.add_edge(a, b, weight=round(cos, 3), shared_days=c)
    G.remove_nodes_from([n for n in list(G.nodes()) if G.degree(n) == 0])

    # community detection
    comms = list(nx.community.greedy_modularity_communities(G, weight="weight"))
    node_comm = {n: i for i, c in enumerate(comms) for n in c}
    nx.set_node_attributes(G, node_comm, "community")
    mod = nx.community.modularity(G, comms, weight="weight")

    # alignment: does the structure track ORIGIN, or merely the crisis ERA?
    try:
        from sklearn.metrics import normalized_mutual_info_score
        common = [n for n in G.nodes()]
        cvec = [node_comm[n] for n in common]
        nmi = normalized_mutual_info_score(cvec, [G.nodes[n]["origin_group"] for n in common])
        nmi_era = normalized_mutual_info_score(cvec, [G.nodes[n]["era"] for n in common])
    except Exception:
        nmi = nmi_era = float("nan")

    # centrality table (W4 staple: degree / weighted / eigenvector / closeness / betweenness)
    deg = dict(G.degree()); wdeg = dict(G.degree(weight="weight"))
    # eigenvector centrality is only well-defined on a connected component:
    # compute on the largest component, assign 0.0 to nodes outside it.
    eig = {n: 0.0 for n in G.nodes()}
    if G.number_of_edges():
        lcc = max(nx.connected_components(G), key=len)
        sub = G.subgraph(lcc)
        try:
            eig.update(nx.eigenvector_centrality_numpy(sub, weight="weight"))
        except Exception:
            eig.update(nx.eigenvector_centrality(sub, weight="weight", max_iter=1000))
    clo = nx.closeness_centrality(G); btw = nx.betweenness_centrality(G, weight="weight")
    cent = pd.DataFrame([{
        "house": n, "origin_group": G.nodes[n]["origin_group"], "value": G.nodes[n]["value"],
        "degree": deg[n], "weighted_degree": wdeg[n], "eigenvector": round(eig[n], 4),
        "closeness": round(clo[n], 4), "betweenness": round(btw[n], 4), "community": node_comm[n],
    } for n in G.nodes()]).sort_values("weighted_degree", ascending=False)
    cent.to_csv(TAB / "net2_affiliation_centrality.csv", index=False)

    # community composition by origin
    comp = (cent.groupby(["community", "origin_group"]).size().unstack(fill_value=0))
    comp.to_csv(TAB / "net2_community_origin_composition.csv")

    print("\n=== NET2: affiliation / community (cosine co-timing) ===")
    print(f"nodes {G.number_of_nodes()} | edges {G.number_of_edges()} | communities {len(comms)} | "
          f"modularity {mod:.3f}")
    print(f"NMI(community, ORIGIN) {nmi:.3f}   vs   NMI(community, CRISIS-ERA) {nmi_era:.3f}"
          f"   -> structure tracks {'ERA' if nmi_era > nmi else 'ORIGIN'}")
    print("\ntop houses by weighted degree (the W4 'main players' table):")
    print(cent.head(12)[["house", "origin_group", "degree", "weighted_degree", "betweenness", "eigenvector"]].to_string(index=False))

    # NOTE: figures produced by src/network_viz.py (heatmap + cleaned node-link).
    return G


def _plot_net2(G, color_key, fname, title, palette):
    pos = nx.spring_layout(G, weight="weight", seed=7, k=0.55, iterations=200)
    vmax = max(nx.get_node_attributes(G, "value").values())
    sizes = [80 + 1600 * (G.nodes[n]["value"] / vmax) for n in G.nodes()]
    colors = [palette.get(G.nodes[n][color_key], "#cccccc") for n in G.nodes()]
    ew = np.array([d["weight"] for *_, d in G.edges(data=True)])
    fig, ax = plt.subplots(figsize=(13, 11))
    nx.draw_networkx_edges(G, pos, width=0.2 + 1.8 * (ew / ew.max()), edge_color="#bbbbbb", alpha=0.4, ax=ax)
    nx.draw_networkx_nodes(G, pos, node_size=sizes, node_color=colors, edgecolors="white", linewidths=0.6, ax=ax)
    deg = dict(G.degree(weight="weight"))
    thr = sorted(deg.values())[-min(18, len(deg))] if deg else 0
    lab = {n: n for n in G.nodes() if deg[n] >= thr}
    nx.draw_networkx_labels(G, pos, labels=lab, font_size=6.5, ax=ax)
    ax.set_title(title, fontsize=13)
    if color_key == "origin_group":
        present = [g for g in palette if g in nx.get_node_attributes(G, "origin_group").values()]
        handles = [plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=palette[g], markersize=9, label=g)
                   for g in present]
        ax.legend(handles=handles, loc="lower left", fontsize=7, frameon=False)
    ax.axis("off"); fig.tight_layout()
    fig.savefig(FIG / fname, dpi=170); plt.close(fig)


def main():
    t = load()
    net1_intermediation(t)
    net2_affiliation(t)
    print("\nWrote net1_* and net2_* tables -> outputs/tables/ ; 3 network figures -> outputs/figures/")


if __name__ == "__main__":
    main()
