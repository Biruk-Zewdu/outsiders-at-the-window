"""Assemble paper.md into a PDF-ready markdown (figures + tables embedded inline,
title metadata), then leave compilation to pandoc + xelatex (run separately).

Writes paper.build.md in the project root.
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
TAB = ROOT / "outputs" / "tables"

def clean(s):  # honour the no-hyphen rule in generated cells
    return str(s).replace("-", " ")

# ---- Table 1: the six houses present in all three crises ----
arc = pd.read_csv(TAB / "emigre_house_arc.csv")
core = arc[arc["n_crises"] == 3].sort_values("total_value", ascending=False)
t1 = ["| House | Origin | Crises present | Total crisis lending (£) |",
      "|---|---|---|---:|"]
for _, r in core.iterrows():
    t1.append(f"| {clean(r['canonical_house'])} | {clean(r['origin'])} | "
              f"{r['crises_present'].replace('+', ', ')} | {r['total_value']:,.0f} |")
t1.append("")
t1.append(": The six émigré houses that borrowed from the Bank in all three crises.")
TABLE1 = "\n".join(t1)

# ---- Table 2: selected wartime fates (hand-written, clean text) ----
TABLE2 = """| House | Origin | What happened in the war |
|---|---|---|
| J. Henry Schröder & Co | German (Hamburg) | Bruno Schröder swore the oath of allegiance on 7 August 1914, three days into the war (London Gazette 1914a); the firm survived. |
| Frederick Huth & Co | German (Stade and Hanover) | Survived the war but declined; finally wound up in 1936. |
| Kleinwort, Sons & Co | German (Holstein) | Partners naturalised; survived, later Kleinwort Benson. |
| N. M. Rothschild & Sons | German Jewish (Frankfurt) | Long established British branch; unaffected (the only enemy notice naming a Rothschild is a different, Continental person). |
| Frühling & Goschen | German (Leipzig) | The German named firm was wound down and merged into Goschen and Cunliffe by 1920 (Kynaston; not found in the Gazette). |
| C. J. Hambro & Son | Danish (Copenhagen) | Denmark was neutral; not treated as an enemy; survived. No seizure order in the record; a Hambro honoured in British service (London Gazette 1919). |
| B. W. Blydenstein & Co | Dutch | The Netherlands was neutral; not treated as an enemy; survived. No seizure order in the record. |
| Deutsche Bank, London branch | German | Placed under a Controller and wound up under the Trading with the Enemy Acts; in the 1918 liquidation list (London Gazette 1918). |
| Dresdner Bank, London branch | German | Placed under a Controller and wound up; affairs ran into the later 1920s (London Gazette 1928). |
| Disconto Gesellschaft, London branch | German | Wound up by order under the Trading with the Enemy Acts, 1918 and 1921 (London Gazette 1918, 1921). |

: Fate during the First World War of selected houses seen at the 1914 window. Wartime fates checked against the London Gazette where possible (see notes/gazette_verification.md). Sources: origin register; London Gazette; Hansard 1916; Roberts 1992; Kynaston 1995."""

# ---- Table 3: the twenty largest borrowing houses in 1857 (E3) ----
top = pd.read_csv(TAB / "e3_top_houses_1857.csv")
t3 = ["| Rank | House | Origin | Crisis lending (£) | Émigré |",
      "|---:|---|---|---:|:--:|"]
for _, r in top.iterrows():
    mark = "yes" if r["emigre"] else ""
    t3.append(f"| {int(r['rank'])} | {clean(r['canonical_house'])} | {clean(r['origin_short'])} | "
              f"{r['value']:,.0f} | {mark} |")
t3.append("")
t3.append(": The twenty largest borrowing houses in 1857. Twelve of the twenty (marked) are émigré firms.")
TABLE3 = "\n".join(t3)

# ---- Table 4: rate regressed on size and an émigré indicator (E5) ----
reg = pd.read_csv(TAB / "e5_rate_regression.csv")
t4 = ["| Crisis | Houses | Émigré effect on rate (% points) | 95% range | Size effect |",
      "|---|---:|---:|:--:|---:|"]
for _, r in reg.iterrows():
    t4.append(f"| {r['crisis']} | {int(r['n_houses'])} | {r['emigre_coef_on_rate']:+.2f} | "
              f"{r['ci95_low']:+.2f} to {r['ci95_high']:+.2f} | {r['size_coef']:+.2f} |")
t4.append("")
t4.append(": Each crisis: a house's mean rate explained by its size (log of total lending) and "
          "whether it was an émigré house. The émigré effect is the extra rate, in percentage points, "
          "that comes with being an émigré house once size is held level. In every crisis the 95 percent "
          "range includes zero, so the effect cannot be told apart from no effect at all.")
TABLE4 = "\n".join(t4)

def fig(caption, path, width):
    return f"\n\n![{caption}](outputs/figures/{path}){{width={width}}}\n\n"

# anchor sentence -> block to insert after that paragraph
INSERTS = {
    "on the eve of the reversal.":
        fig("Share of crisis lending by origin group, 1857, 1866 and 1914.", "group_share_stacked.png", "78%")
        + fig("Émigré lending and its share of crisis lending across the three crises.", "emigre_persistence.png", "68%"),
    "for nearly sixty years is no newcomer.":
        "\n\n" + TABLE1 + "\n\n",
    "The banks next to them had just grown much bigger.":
        "\n\n" + TABLE3 + "\n\n",
    "the old native banks were trusted slightly more.":
        fig("Share of bills the Bank rejected, by value. Émigré houses sit at or below the average for all borrowers in every crisis; only the old English private banks were refused less.", "e1_rejection_by_origin.png", "80%"),
    "would have charged one.":
        fig("Average interest rate paid at the window, by type of house.", "rate_emigre_vs_native.png", "70%")
        + fig("Interest rate against house size. Each point is a house in one crisis, sized by how often it borrowed and coloured by origin. Émigré houses (red) pay no more than British houses (blue) of the same size.", "e2_rate_vs_size.png", "100%")
        + "\n\n" + TABLE4 + "\n\n",
    "wider pattern of City borrowing.":
        fig("Network test for an émigré enclave. Red points show the real network score; grey points show the average after shuffling origin labels 1,000 times. The result does not show a separate émigré corner of the Bank's window.", "x2_enclave_null_binary_assortativity.png", "78%"),
    "to the Bank of England (Figure 7).":
        fig("How the world reached the Bank of England in 1914: foreign account on the left, through a London house in the middle, to the Bank on the right. Ribbon width is value.", "net1_1914_intermediation_sankey.png", "100%"),
    "suspicion and naturalised (Figure 8).":
        fig("The vocabulary of the wartime debates on enemy aliens and German banks, 1914 to 1918.", "hansard_suspicion_terms.png", "72%"),
    "neutral in the war (Table 2).":
        "\n\n" + TABLE2 + "\n\n",
    "the ledger shows no sign of the reversal at all.":
        fig("The Bank's treatment of émigré houses across 1914. Left: the émigré share of the Bank's lending each month, holding double digits right through the war. Right: the share of bills the Bank rejected before and after war was declared, for émigré houses and for all borrowers; the Bank grew more careful after August, but equally for everyone.", "e4_wartime_treatment.png", "100%"),
    "singled the émigré houses out.":
        fig("Wartime network shock test around 4 August 1914. The Bank's window changed after war began, but the change does not look like a targeted exclusion of émigré houses.", "x3_wartime_network_shock.png", "100%"),
}

text = (ROOT / "paper.md").read_text()

# Pull the abstract out of the body and into metadata, so pandoc renders it as a
# centred abstract block under the title rather than a left-aligned section.
abs_start = text.index("## Abstract") + len("## Abstract")
abstract = text[abs_start:text.index("---", abs_start)].strip()

# Body now begins at the Introduction (the abstract lives in the YAML).
body = text[text.index("## 1. Introduction"):text.index("## Figures and tables")] + text[text.index("## References"):]

for anchor, block in INSERTS.items():
    i = body.index(anchor)
    j = body.find("\n\n", i + len(anchor))
    if j == -1:
        j = len(body)
    body = body[:j] + block + body[j:]

reader_note = ("*A note for the reader: this paper uses a few terms from nineteenth century "
               "banking and from network analysis. I explain each one the first time it appears, "
               "and there is a short glossary at the end.*\n\n")

yaml = ('---\n'
        'title: "Outsiders at the Window: How the City\'s Émigré Houses Were Made Foreign in 1914"\n'
        'subtitle: "Introduction to Digital History (HSS207/DHS211)"\n'
        'author: "Biruk Kassa (Student ID 20220775)"\n'
        'date: "June 2026"\n'
        'geometry: "left=1.05in, right=1.05in, top=1.5in, bottom=1.2in"\n'
        # By default LaTeX's abstract environment indents both sides; redefine it so
        # the abstract runs the full text width, matching the body margins.
        'header-includes: |\n'
        '  \\renewenvironment{abstract}{\\begin{center}\\textbf{Abstract}\\end{center}}{}\n'
        'abstract: |\n'
        '  ' + abstract + '\n'
        '---\n\n')

(ROOT / "paper.build.md").write_text(yaml + reader_note + body)
print("wrote paper.build.md")
