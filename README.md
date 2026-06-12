# Outsiders at the Window

**Émigré merchant houses and the making of cosmopolitan London at the Bank of
England's crisis window, 1857–1914.**

A digital-history project, separate from the shared lender-of-last-resort paper.
Where that project asks *whether the Bank acted like a modern lender of last
resort*, this one asks a different, narrative question:

> The German-Jewish, Greek, Parsi and American houses long treated as outsiders
> to the City — how central were they, in fact, to the Bank's crisis lending?
> And what happened to them when 1914 turned "cosmopolitan" into "enemy alien"?

The data supplement a historical narrative about *people and houses*; they are
not the argument themselves.

## The one-sentence framing

> *This paper offers an original narrative that the émigré merchant houses long
> treated as outsiders to the City were in fact load-bearing pillars of its
> crisis finance — until 1914 turned them from indispensable into suspect.*

## What the data show (v1)

- **Émigré houses were a persistent, sizeable minority of crisis lending** —
  **12.5% (1857), 10.9% (1866), 15.1% (1914)** of classified-window value — from
  just a few dozen firms. Their share is **highest in 1914**, the eve of the
  reversal. (`outputs/figures/emigre_persistence.png`)
- **A persistence core ran through all three crises**: Huth, Brandt, Kleinwort,
  Raphael, Frühling & Goschen, Ralli. (`outputs/tables/emigre_house_arc.csv`)
- **The composition of the window changed**: 1857 was dominated by British
  discount houses; by 1914 the borrowers are far more diverse — native clearing
  banks, colonial banks, and a new layer of *foreign* banks (Deutsche, Dresdner,
  Crédit Lyonnais) appear. (`outputs/figures/group_share_stacked.png`)
- **Émigré houses paid marginally *less*, not more**, than native British
  merchants in every crisis (e.g. 1866: 8.27% vs 8.93%) — consistent with the
  elite merchant banks being trusted insiders, not marginal outsiders, at the
  window. (`outputs/figures/rate_emigre_vs_native.png`)
- **The 1914 reversal is documented**: German *branch* banks were sequestered;
  German *houses* survived only by hurried naturalisation (Schröder) or were
  wound down (Frühling & Goschen); neutral-origin houses (Hambro/Danish,
  Blydenstein/Dutch) were spared. (`outputs/tables/wwi_fate.csv`)

## Structure

```
data/
  lolr_transactions.parquet      copied from the shared repo (the source ledger)
  origin_register.csv            HAND-CODED prosopography of the houses (the new data)
  house_crosswalk.csv            raw ledger name -> canonical house + origin group
  transactions_tagged.parquet    the ledger with origin columns joined on
src/
  build_register_and_crosswalk.py  entity resolution + register -> data/*
  analyze.py                       evidence tables + figures
outputs/
  tables/   group_share_by_crisis, emigre_house_arc, rate_by_group, wwi_fate
  figures/  group_share_stacked, emigre_persistence, rate_emigre_vs_native
references/ Anson et al. 2017 (source), White 2016
notes/      curation_log.md  (methodology, sources, caveats — READ THIS)
```

## Methods (W12 stack)

- **Prosopography + database construction** (`origin_register.csv`) — the spine.
- **Record linkage / entity resolution** — cross-crisis name merging.
- **Descriptive comparative analysis** — shares, rates, persistence.
- **Network analysis (W4)** — two plotted networks:
  - *1914 intermediation* (directed): beneficiary → London house → Bank.
  - *Affiliation / community* (co-timing): community detection coloured by origin.
- **Text mining (W3)** — the 1914–18 Hansard enemy-bank/alien debates.

## What the network + text strands add

- **London as the world's window (1914):** 76% of intermediated value flowed to
  **overseas** beneficiaries; France (Crédit Lyonnais) alone was £5.7m, almost all
  via the conduit Glyn, Mills, Currie (£6.3m). (`net1_1914_intermediation_sankey.png`)
- **Outsiders were integrated, not segregated:** community structure tracks the
  **crisis era** (NMI 0.56), **not origin** (NMI 0.26), and origin assortativity is
  ≈0 (+0.04) — émigré houses come to the window woven among native houses, not in
  an ethnic bloc. (`net2_group_cotiming_heatmap.png`, `net2_affiliation_clean.png`)
- **The discursive reversal:** across 8 Hansard debates (1914–18) the language of
  suspicion dominates — alien (265), enemy (171), German (166), naturalised (41),
  "wound up", "Public Trustee", "sold/auction". (`hansard_suspicion_terms.png`,
  `hansard_key_quotes.csv`)

## Website

`site/` is an interactive single-page companion to the paper: the charts are
driven by the same output CSVs (via `src/build_site_data.py` → `site/data.js`),
plus an explorable house register, a WWI fate table, the reliability/criticism
material, glossary, and the Use of AI statement.

```bash
python src/build_site_data.py                # regenerate site/data.js from outputs/tables
python3 -m http.server --directory site      # then open http://localhost:8000
```

Opening `site/index.html` directly also works. Charts need internet once for the
Chart.js CDN. `site/paper.pdf` and `site/figures/` are copied from the project
(re-copy after rebuilding the PDF or figures).

## Reproduce

```bash
source ../.venv/bin/activate
python src/build_register_and_crosswalk.py   # data/* (register, crosswalk, tagged ledger)
python src/analyze.py                        # outputs/* (shares, rates, persistence, fate)
python src/network_analysis.py               # network tables + metrics (NMI, centrality)
python src/network_viz.py                     # readable figures (Sankey/heatmap/graph) + GraphML
python src/textmining_hansard.py             # Hansard text mining (needs references/hansard/*.html)
python src/build_site_data.py                # site/data.js for the interactive website
```

Polished figures are produced by `network_viz.py`; `network_analysis.py` only
computes the tables/metrics. `outputs/net1_intermediation.graphml` and
`outputs/net2_affiliation.graphml` can be opened in **Gephi** for gallery-quality
hand-layout (ForceAtlas2), matching the course's W4 network aesthetic.

## Status & next steps

Stage-1 data gathering and curation is **complete**: the ledger is tagged, the
register and crosswalk exist, and the evidence tables/figures reproduce. The
register is a v1 — refine the `confidence == low` rows (founders, dates, a few
attributions) as you read Cassis / Chapman. The natural next step is to write the
narrative section by section around the named houses, using these figures as
evidence. See `notes/curation_log.md` for every methodological decision and
caveat (selection bias, small-n, coarse origin buckets).
