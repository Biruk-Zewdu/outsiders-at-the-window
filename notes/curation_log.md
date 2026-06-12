# Curation log — Outsiders at the Window

How the dataset behind this project was built, what was decided, and what to
distrust. Read this before quoting any number.

## 1. What this project needs that the source data does not contain

The BoE LOLR transaction ledger (`data/lolr_transactions.parquet`, 9,055 rows
across 1857 / 1866 / 1914) records names, types, amounts, rates, rejections and
bill technicalities — **but nothing about the origin or nationality of the
borrowing house.** The `remarks` field is only bill-handling notes ("irregular",
"wrong stamp", "declined"). The entire émigré/identity dimension therefore had
to be **created by hand**. That hand-coded layer is the contribution of this
project; the digital analysis supplements it.

Two curation tasks were required:
1. **Cross-crisis entity resolution** — the same house appears under different
   spellings / OCR errors / firm-name changes in each crisis. These had to be
   merged so a house can be tracked 1857 → 1914.
2. **An origin register** — for each house, a hand-coded record of origin,
   founder, founding year, community, and fate in WWI.

## 2. Pipeline

```
src/build_register_and_crosswalk.py   # tasks 1 & 2 -> data/*.csv + tagged parquet
src/analyze.py                        # evidence tables + figures
```

Run order: build first, then analyze. Both use the repo's parent `.venv`.

### Outputs
- `data/origin_register.csv` — one row per house (the hand-coded prosopography).
- `data/house_crosswalk.csv` — every raw ledger name -> canonical house + origin group.
- `data/transactions_tagged.parquet` — the full ledger with origin columns joined on.
- `outputs/tables/` — group_share_by_crisis, emigre_house_arc, rate_by_group, wwi_fate.
- `outputs/figures/` — group_share_stacked, emigre_persistence, rate_emigre_vs_native.

## 3. Entity resolution — how it was done

The register encodes each house as a set of **regex patterns** matched
case-insensitively against `counterparty_clean`. Patterns were written to absorb
the variants observed in the ledger, e.g.:

| House | Variants merged |
|---|---|
| J. Henry Schröder & Co | `J H Schroder & Co`, `J.H.Schroder & Co`, `S.N.Schroder & Co` (OCR) |
| Frederick Huth & Co | `F Huth & Co`, `Frederick Huth & Co`, `F.Huth Co` |
| Kleinwort, Sons & Co | `Kleinwort & Cohen`, `Drake, Kleinwort & Cohen`, `Kleinwort Sons & Co` |
| Frühling & Goschen | `Fruhling & Goschen`, `Truhling & Goschen` (OCR T-for-F) |
| Ralli Brothers | `P T Ralli`, `Ralli Bros`, `T & J Ralli`, `Ralli & Mavrojani`, … |

This is deliberately **manual, not automatic fuzzy matching**: the cross-crisis
link is the analytic point, and the teammate's existing fuzzy resolver
(`outputs/tables/counterparty_entity_resolution.csv` in the parent repo) does
*not* merge these — it keeps `F Huth & Co` and `Frederick Huth & Co` as separate
entities. Register order encodes priority (specific houses before broad ones).

## 4. Origin register — sourcing

A v1 grounded in the standard secondary literature: Cassis, *City Bankers
1890–1914*; Chapman, *The Rise of Merchant Banking*; Kynaston, *The City of
London*; Jones, *British Multinational Banking* (for the colonial banks). The
WWI "fate" claims that the narrative leans on were spot-verified online:

- **Schröder** — Bruno Schröder naturalised within days of war, Aug 1914; firm
  survived. (encyclopedia.com, Schroders plc)
- **Frühling & Goschen** — German-named firm wound down into Goschen & Cunliffe,
  1920. (Wikipedia, Harry Goschen)
- **Deutsche / Dresdner / Disconto-Gesellschaft** — London branches sequestered
  and sold via the Public Trustee, 1914–16. (Hansard, German Banks in London, 1916)

Each register row carries a `confidence` flag (high / medium / low). **Treat
`low` rows as placeholders to verify while reading.** Founders/founding years for
the smaller German and Greek houses are the least certain.

## 5. Coverage

- 1,476 distinct raw names; 112 register houses; **172 raw names matched (12%).**
- But matched names are the big ones: **~81% of total transaction value** is
  classified. The unclassified ~19% is the genuine long tail of small,
  one-off, often individual borrowers.

## 6. Known issues / things to distrust

- **Selection bias (most important).** The ledger shows only houses that *came to
  the Bank's window* in a crisis. A house's absence does **not** mean it did not
  exist or matter — it may simply not have needed the Bank. All "share" numbers
  are shares *of crisis borrowing*, not of the City.
- **Small n per house** (most émigré houses: 1–40 transactions). This is a
  prosopographic / share-based study, not a significance-testing one.
- **Origin groups are coarse analytic buckets.** The precise `origin` column
  carries nuance the group label flattens — e.g. Sephardi-Jewish houses (Raphael,
  King & Foa) are bucketed under "Greek & Levantine"; Anglo-Jewish bullion houses
  (Montagu) under "German & Central European". Re-bucket as the argument needs.
- **Baring** is tagged native-British establishment though its 18th-c root was a
  Bremen émigré (Johann Baring) — a deliberate, defensible call; note it.
- **A few benign over-merges:** `Cater & Co` (discount) absorbs `I. W. Cater
  Inman & Co` (a different 1857 merchant); `Imperial Ottoman Bank` absorbs `Imp.
  Ottoman Government`. Both keep the right broad group; value impact is tiny.
- **The `value` field** is `total_amount`, falling back to `value_discounted`
  then `amount_advanced_total`. Documented in both scripts.

## 7. What was NOT needed

No new transactional data (1857/1866/1914 is the full arc); no OCR of new pages;
no balance-sheet or macro data. The curation here is light but bespoke — mostly
reading, not coding.

---

# Stage 3 — Network analysis (added)

`src/network_analysis.py` builds two plotted networks.

**Date recovery.** The ledger's `date` column was stored in microseconds but
mis-tagged on parquet write (it reads as 1969). `pd.to_datetime(date, unit='us')`
recovers the true dates — verified: 1857 Sep–Dec, 1866 Mar–Jun, 1914 Jul–Dec.
This is needed for the day-level co-occurrence network.

## NET 1 — 1914 intermediation (directed)
- Source: the `on_account_for` field (349 rows, 1914 only). Edge = ultimate
  beneficiary → presenting London house → Bank of England, weighted by value.
- Beneficiary `kind` is a keyword heuristic (overseas / domestic / London-place /
  firm) — approximate; eyeball before quoting individual rows.
- **Finding:** 76% of intermediated value flowed to **overseas** beneficiaries;
  Glyn, Mills, Currie is the dominant conduit (£6.3m, mostly Crédit Lyonnais).
  London = the world's discount window in 1914.
- Tables: `net1_intermediation_nodes/edges`, `net1_top_conduits`,
  `net1_beneficiary_kind_value`. Figure: `net1_1914_intermediation.png`.

## NET 2 — affiliation / community (undirected, all crises)
- Houses (origin-classified only) linked when they appear at the window on the
  **same day**, edge weight **cosine-normalised** over each house's active-day set
  (so the tie measures disproportionate co-timing, not both-houses-being-busy).
  Kept edges: ≥2 shared days AND cosine ≥ 0.30.
- Community detection: greedy modularity. Centrality table reports the five W4
  measures (degree, weighted degree, eigenvector, closeness, betweenness);
  eigenvector computed on the largest connected component.
- **Finding (robust):** community structure tracks the **crisis era**
  (NMI 0.56), **not origin** (NMI 0.26). Émigré houses do *not* form a separate
  behavioural bloc — they are woven into each crisis cohort alongside native
  houses. The diaspora was a social network, not a segregated one at the window.
- Caveat: co-timing is one affiliation proxy among several; pooling across crises
  means cross-era pairs can never link (dates carry the year), which is part of
  why structure ≈ era. Reported honestly via the two NMI figures.
- Tables: `net2_affiliation_centrality`, `net2_community_origin_composition`.
  Figures: `net2_affiliation_by_origin.png`, `net2_affiliation_by_community.png`.

# Stage 4 — Text mining: the discursive reversal (added)

`src/textmining_hansard.py`. Corpus: **8 Hansard debates, 1914–18** (Commons +
Lords), downloaded as HTML to `references/hansard/` and parsed to `.txt`. ~45k
tokens, 107 attributed speeches.

- Method: term frequencies, a curated **suspicion lexicon**, KWIC concordance,
  and attributed key quotes. Deliberately *not* a topic model — the corpus is
  small and the goal is evidence + language, not a fitted model (consistent with
  the W3 "don't force embeddings" judgement).
- **Finding:** the lexicon of the reversal — alien (265), enemy (171), German
  (166), suspicion (60), naturalised (41), "wound up/liquidate", "Public
  Trustee", "sold/auction" — documents how the cosmopolitan houses were
  re-described as enemies, exactly as the title's second half claims.
- Caveat: the corpus mixes **bank-specific** debates (German/Enemy Banks in
  London) with **general enemy-alien** debates (which dominate the token count,
  esp. the large 1915-03-03 Aliens debate). It captures the *climate* the houses
  were caught in, not only bank-specific speech. Some extracted "quotes" are Q&A
  fragments — curate before quoting.
- Tables: `hansard_term_frequencies`, `hansard_lexicon_counts`,
  `hansard_key_quotes`, `hansard_concordance`. Figure: `hansard_suspicion_terms.png`.

## Full reproduce order
```
python src/build_register_and_crosswalk.py
python src/analyze.py
python src/network_analysis.py
python src/textmining_hansard.py
```

---

# Stage 3b — Readable visualisations (added; supersedes the first network plots)

The initial node-link plots were unreadable (120-node columns, label pile-ups,
straight-edge hairballs). `src/network_viz.py` replaces them; `network_analysis.py`
now only computes tables/metrics. No new dependencies (pure matplotlib/networkx).

- **NET1 → Sankey** (`net1_1914_intermediation_sankey.png`): country → London
  house → Bank, ribbon width = £value. Beneficiaries aggregated to ~9 regions via
  a keyword map (`REGION_RULES`) — *approximate* for the small/ambiguous tail;
  the big flows (France/Crédit Lyonnais £5.7m, UK provincial £1.35m, Russia,
  Germany, Egypt, S. America) are confident. Top-8 presenting houses shown, rest
  "Other houses".
- **NET2 → heatmap** (`net2_group_cotiming_heatmap.png`): origin-group × group
  mean co-timing affinity (cosine / possible pair). Adds a single-number homophily
  test: **origin assortativity = +0.04 (≈0)** ⇒ no ethnic clustering. High
  co-timing is among British clearing/discount houses (the frequent window users),
  not within émigré groups.
- **NET2 → cleaned node-link** (`net2_affiliation_clean.png`): giant component,
  wider spring layout, size = lending, colour = origin, only the 10 most-central
  houses labelled (white-halo, leader lines). Shows émigré (reds/oranges)
  interspersed among British (blues), in two era-cohort blobs.
- **GraphML exports** (`outputs/net1_intermediation.graphml`,
  `outputs/net2_affiliation.graphml`) for hand-polishing in **Gephi** (ForceAtlas2),
  to match the W4 deck's network aesthetic if a gallery-quality version is wanted.

Run `network_viz.py` after `network_analysis.py`.

---

# Stage 4 — Section 5 reworked: direct insider tests replace the co-timing network

On review, the co-timing affiliation network (NET2: heatmap, mixing bar, ordered
matrix) was judged the wrong instrument for the "insiders not outsiders" claim.
Co-timing on the same days is a weak proxy for social mixing — two houses sharing
a discount day says little about whether they belonged to the same circle, and the
mixing-bar test only had one émigré group (German, n=23) large enough to read, with
the rest (Greek/Indian/American, n=3–4) too small to mean anything. The
assortativity number (+0.04) was technically clean but rested on that same thin base.

`src/experiments.py` replaces NET2 in the paper with three direct tests drawn from
the ledger's own per-transaction fields. The intermediation network (NET1, Sankey)
is kept — it is the right tool for Section 6 and the only network the paper now draws.

- **E1 — rejection by origin** (`e1_rejection_by_origin.png/.csv`). On discount rows
  the ledger records `value_brought` and `value_bills_rejected` (blank = zero
  rejected; populated only on discounts). Rejection rate by value = Σrejected/Σbrought.
  Émigré houses are refused at or below the all-borrower average in every crisis
  (3.9/1.0/4.4% vs 5.5/4.2/4.5%); only the old English private banks are refused less
  (0.0/1.6/2.2%). Honest two-layer finding: inside the normal trust circle, just
  outside the innermost native ring.
- **E2 — rate controlled for size** (`e2_rate_vs_size.png`, `e2_rate_by_size_tier.csv`).
  Per-house value + mean `rate` per crisis; scatter of rate vs log10(value), coloured
  émigré/British/other; plus a larger/smaller size-tier table (split at within-crisis
  median value). The raw rate edge for émigré houses (Fig 4) mostly vanishes once size
  is held level: within each tier émigré and British pay about the same. Reframes the
  old "they paid less" claim as the stronger, more defensible "no penalty for being
  foreign / they paid the ordinary price for their size."
- **E3 — biggest names** (`e3_top_houses_{1857,1866,1914}.csv`). Top-20 houses by
  value per crisis, émigré flagged. 1857: 12/20 émigré (the top ranks are the British
  discount houses — Overend Gurney, Alexanders — with émigré names filling ranks
  ~8–20); 1866: 6/20; 1914: 3/20. The falling count is NOT émigré decline (their value
  share rose to 15.1% in 1914) but the rise of a few giant clearing/discount banks that
  crowd the head of the ranking. Table 3 in the paper = the 1857 top-20.

Paper changes: Section 5 rewritten around four checks (lasted / biggest names /
not refused / no size-adjusted penalty). Removed from the paper: heatmap, mixing bar,
ordered matrix (Appendix A), and the assortativity sentence + glossary entry. Figures
renumbered in reading order (Fig 3 = E1 rejection, Fig 4 = raw rate, Fig 5 = E2 size).
The NET2 figures/tables still build via `network_viz.py` but are no longer cited.

Run `python src/experiments.py` (after the tagged parquet exists) to regenerate E1–E3.

---

# Stage 5 — Primary-source verification of the register: The London Gazette

The register's weakest point is that origins and wartime fates were hand-coded from
secondary books. `src/gazette_verify.py` checks them against the official state record,
The London Gazette (free, fully digitised; thegazette.co.uk), via its Atom data feed.
For each of the 112 houses it caches the raw responses (`data/gazette/raw/`), parses each
notice (publish date, edition, issue, page, canonical URL, highlighted snippet),
classifies it (naturalisation / honour / enemy_property / winding_up / dissolution /
bankruptcy / company / other), and scores it. Output: `gazette_notices.csv` (10,931
scored candidates), `gazette_house_summary.csv` (per house), and a hand-curated
`gazette_evidence_curated.csv` (10 confirmed notices). Full write-up in
`notes/gazette_verification.md`.

Confirmed from the primary record:
- **Deutsche / Disconto / Dresdner (London branches)** — sequestered under a Controller
  and wound up under the Trading with the Enemy Acts (London Gazette 30803/8498 1918;
  32303/3332 1921; 33354/919 1928). Upgrades Table 2 from secondary to primary. Note the
  register's "1914–16" dating is loose: the formal winding-up runs 1918 into the 1920s.
- **J. Henry Schröder & Co** — wartime partner-disclosure filings (29081/1946 1915;
  29961/1993 1917) name Baron Bruno Schröder and the firm at Leadenhall Street, i.e. a
  German-named house openly trading through the war. Primary support for "survived."
- **Hambro, Blydenstein (neutrals)** — confirmed by absence: no enemy/Public-Trustee
  notice 1914–20. Hambro instead appears in a British honours list (31206/2855 1919).
- **N. M. Rothschild** — the only "Rothschild" enemy notice is "Rudolf von
  Goldschmidt-Rothschild, an Enemy within the Act" (29340/10582 1915), a different
  person; confirms the British house was untouched (a worked name-collision case).

Not closed by this pass (left on secondary authority, would need page-level PDFs):
- individual naturalisations (Bruno Schröder, Kleinwort) — the Gazette's naturalisation
  list pages are findable but the search snippet centres on one name and cannot pin a
  specific individual on a dense OCR list.
- the Frühling & Goschen -> Goschen & Cunliffe 1920 merger (no co-occurring notice).

Method caveats: distinctive names (Schroder, Disconto, Blydenstein) verify well; generic
ones (Smith, King, National, Union) return 10^4–10^5 hits and are not machine-checkable,
but the argument rests on the distinctive émigré names. The script reparses the cache and
never re-downloads. Run: `python src/gazette_verify.py`.

**Naturalisation confirmed via page PDF.** The search snippet cannot pin an individual on
a dense naturalisation list, so the page PDF was pulled (`data/gazette/pdf/`) and read with
pdftotext: London Gazette Issue 28892 p7033 (4 Sep 1914) lists "Schroder, Rudolf Bruno,
Germany, 7th August 1914, Banker, 35 Park Street, London" — Baron Bruno Schröder's oath of
allegiance, three days after war was declared. This is now the primary cite for the paper's
opening anecdote. Curated citations (incl. this) in `data/gazette/gazette_evidence_curated.csv`.

---

# Stage 6 — Two new analyses (E4, E5) and integration of the primary sources into the paper

`src/experiments2.py` adds two tests that the primary-source pass made possible/needed:

- **E4 — did the Bank turn on the émigré houses once war began?** Recover the real 1914
  dates (`pd.to_datetime(int64, unit='us')`) and split the ledger at 4 Aug 1914. Result
  (`e4_wartime_treatment.png/.csv`): the émigré share of window lending held 11–17% every
  war month; émigré rejection rose after August (0.4%→4.9%) but the **whole window** rose
  identically (0.3%→4.9%) — a general crisis tightening, not targeting; émigré rates stayed
  at/below the window average. So the political reversal has NO counterpart in the Bank's
  own behaviour in the same months. This is the paper's sharpest result; now Figure 8 +
  the new Section 8 paragraph ("watch both records in the very same months").
  NB: a hoped-for "émigré houses were the 1914 intermediation channels" analysis was
  checked and is FALSE — the named on_account_for flow runs mostly through the British
  house Glyn Mills (£6.4M) vs £54k through émigré houses; Section 6's old "cosmopolitan
  houses were the channels" line was an overclaim and was corrected to be honest.
- **E5 — "no penalty for being foreign," made rigorous.** Per-crisis OLS of mean rate on
  log10(size) + an émigré dummy (`e5_rate_regression.csv`, Table 4). The émigré coefficient
  is statistically indistinguishable from zero every crisis (1914: −0.01, 95% CI −0.19..+0.16,
  p=0.88). Upgrades E2 from eyeball to a coefficient.

Paper integration this stage: opening anecdote now cites the Gazette naturalisation (7 Aug
1914); new Section 3 paragraph on checking the register against the Gazette; Table 4 in
Section 5; Section 6 intermediation overclaim corrected; Section 7 bank-sequestration and
Schröder claims now carry London Gazette cites + the neutrals' confirming-null + Hambro
honour; Figure 8 + new paragraph in Section 8; References gained five London Gazette entries.
PDF rebuilt: 17 pages (was 14). Run order: experiments.py, experiments2.py, gazette_verify.py,
then build_pdf.py + pandoc.

---

# Stage 7 — Extra network experiments integrated; gateway claim removed

The attempted gateway experiment was removed from the active outputs and script.
It showed that the main 1914 on-account-for conduits were overwhelmingly British houses,
especially Glyn, Mills, Currie, not the émigré houses. Since the paper already says the
international routing role belonged to the City as a whole, not to émigré houses in
particular, this experiment was judged distracting rather than useful for the argument.

`src/network_experiments_extra.py` now keeps only two experiments:

- **X2 — Enclave null test.** Build a house co-presence network from shared ledger days,
  then shuffle origin labels 1,000 times across the same graph. The useful result is
  that émigré-to-émigré links are only 4.4% of weighted edges, below the shuffled average
  of 12.9%. This supports the "mixed into the window, not a separate foreign enclave"
  reading. Output: `x2_enclave_null_test.csv`, `x2_copresence_edges.csv`, and
  `x2_enclave_null_binary_assortativity.png`.
- **X3 — Wartime network shock.** Split the 1914 ledger into the 34 days before 4 August,
  the 34 days after 4 August, and the later war months. The Bank's network tightens after
  war begins, but not in a way that singles out émigré houses: early-war rejection is
  3.30% for émigré houses versus 2.75% for all classified houses, and later-war rejection
  is 9.01% versus 9.10%. Output: `x3_wartime_house_day_network_shock.csv` and
  `x3_wartime_network_shock.png`.

Paper integration: X2 added to Section 5 after the direct insider tests; X3 added to
Section 8 after the monthly 1914 treatment test. Figure numbering updated so the enclave
test is Figure 6 and the wartime network shock is Figure 10. `build_pdf.py` inserts both
new figures into `paper.build.md`.
