"""Outsiders at the Window — Stage 4 text mining (the discursive reversal).

Mines the 1914-18 House of Commons / Lords debates on enemy aliens and the
"German / Enemy Banks in London" (downloaded HTML in references/hansard/)
to capture, in Parliament's own words,
how the cosmopolitan houses were re-described as enemies — the rhetorical other
half of the title's "from indispensable to suspect".

This is a deliberately small, close-reading-plus-counting text analysis (a handful
of debates), not a topic model: the corpus does not justify embeddings, and the
point is to surface the language of suspicion and quotable evidence, not to fit a
model. (W3 method, used in service of the narrative.)

Outputs:
  tables/hansard_term_frequencies.csv   top content words across the corpus
  tables/hansard_lexicon_counts.csv     counts for a curated suspicion lexicon
  tables/hansard_key_quotes.csv         attributed illustrative quotations
  tables/hansard_concordance.csv        keyword-in-context lines for key terms
  figures/hansard_suspicion_terms.png   bar chart of the suspicion lexicon
"""
from __future__ import annotations
import re
from collections import Counter
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
HANS = ROOT / "references" / "hansard"
TAB = ROOT / "outputs" / "tables"
FIG = ROOT / "outputs" / "figures"
TAB.mkdir(parents=True, exist_ok=True); FIG.mkdir(parents=True, exist_ok=True)

STOP = set("""the of to and a in is be was that it for on as are with by this his he had at which not from or an
have has were they their but all would s i we our your you them then there been being would could should
will may can do does did no nor so if than when what who whom whose how into out up down off over under again
further once here why any both each few more most other some such only own same too very my me him her she
hon honourable member members gentleman right sir mr question questions answer asked ask whether house
order paragraph col deb vol hc said say states state made make given give upon
""".split())

LEXICON = {
    "enemy": [r"enem(?:y|ies)"], "alien": [r"alien"], "German(y)": [r"german"],
    "naturalised": [r"naturali[sz]"], "trading-with-enemy": [r"trading with the enemy"],
    "sequestrate": [r"sequestrat"], "Public Trustee": [r"public trustee"],
    "wound up / liquidate": [r"wound up", r"winding", r"liquidat"],
    "sold / auction": [r"\bsold\b", r"\bsale\b", r"auction"],
    "premises closed": [r"premises", r"\bclosed?\b"],
    "control / influence": [r"control", r"influence"],
    "suspicion": [r"suspic", r"hostile", r"\bspy\b", r"espionage"],
}


def parse_html(path: Path):
    h = path.read_text(errors="ignore")
    # (speaker, speech-html) pairs
    pairs = re.findall(
        r"member_contribution'.*?title=\"([^\"]+)\".*?<blockquote[^>]*class='contribution_text.*?>(.*?)</blockquote>",
        h, re.S)
    # also all speech blocks (full text, incl. continuations without a cite)
    blocks = re.findall(r"<blockquote[^>]*class='contribution_text.*?>(.*?)</blockquote>", h, re.S)

    def clean(html):
        x = re.sub(r"<span class='question_no'>.*?</span>", " ", html, flags=re.S)
        x = re.sub(r"<[^>]+>", " ", x)
        x = (x.replace("&sect;", " ").replace("&mdash;", "—").replace("&amp;", "&")
               .replace("&#039;", "'").replace("&quot;", '"'))
        return re.sub(r"\s+", " ", x).strip()

    speeches = [(sp, clean(txt)) for sp, txt in pairs]
    full = " ".join(clean(b) for b in blocks)
    return speeches, full


def main():
    files = sorted(HANS.glob("*.html"))
    corpus, all_speeches = [], []
    for f in files:
        speeches, full = parse_html(f)
        (HANS / (f.stem + ".txt")).write_text(full)
        corpus.append(full)
        date = f.stem[:10]
        for sp, txt in speeches:
            all_speeches.append({"date": date, "source": f.stem, "speaker": sp, "text": txt})
    text = "\n".join(corpus).lower()
    print(f"corpus: {len(files)} debates, {len(text.split()):,} tokens, {len(all_speeches)} attributed speeches")

    # ---- term frequencies ----
    toks = re.findall(r"[a-z][a-z'-]+", text)
    freq = Counter(w for w in toks if w not in STOP and len(w) > 2)
    tf = pd.DataFrame(freq.most_common(40), columns=["term", "count"])
    tf.to_csv(TAB / "hansard_term_frequencies.csv", index=False)

    # ---- curated suspicion lexicon ----
    lex_rows = []
    for label, pats in LEXICON.items():
        c = sum(len(re.findall(p, text)) for p in pats)
        lex_rows.append({"lexicon_term": label, "count": c})
    lex = pd.DataFrame(lex_rows).sort_values("count", ascending=False)
    lex.to_csv(TAB / "hansard_lexicon_counts.csv", index=False)
    print("\nsuspicion lexicon counts:")
    print(lex.to_string(index=False))

    # ---- KWIC concordance for the core terms ----
    conc = []
    words = re.findall(r"\S+", " ".join(corpus))
    low = [w.lower() for w in words]
    targets = ["enemy", "alien", "german", "naturalised", "naturalized", "sequestrated"]
    W = 10
    for i, w in enumerate(low):
        if any(t in w for t in targets):
            left = " ".join(words[max(0, i - W):i])
            right = " ".join(words[i + 1:i + 1 + W])
            conc.append({"left": left, "keyword": words[i], "right": right})
    pd.DataFrame(conc).to_csv(TAB / "hansard_concordance.csv", index=False)
    print(f"\nconcordance lines for enemy/alien/German/naturalised: {len(conc)}")

    # ---- attributed key quotes (sentences mentioning the reversal) ----
    keys = re.compile(r"enem|alien|german|naturali|sequestrat|public trustee|trading with the enemy", re.I)
    quotes = []
    for s in all_speeches:
        for sent in re.split(r"(?<=[.;])\s+", s["text"]):
            if keys.search(sent) and 40 <= len(sent) <= 320:
                quotes.append({"date": s["date"], "speaker": s["speaker"], "quote": sent.strip()})
    qdf = pd.DataFrame(quotes).drop_duplicates("quote").head(40)
    qdf.to_csv(TAB / "hansard_key_quotes.csv", index=False)
    print(f"key quotes extracted: {len(qdf)}")
    print("\nsample quotes:")
    for _, r in qdf.head(5).iterrows():
        print(f"  [{r['date']} {r['speaker']}] {r['quote'][:140]}")

    # ---- figure: suspicion lexicon ----
    fig, ax = plt.subplots(figsize=(9, 5.5))
    d = lex[lex["count"] > 0].sort_values("count")
    ax.barh(d["lexicon_term"], d["count"], color="#762a83")
    ax.set_xlabel("Mentions across the 1914–18 'German/Enemy Banks' debates")
    ax.set_title("The language of the reversal:\nhow Parliament re-described the cosmopolitan houses")
    fig.tight_layout()
    fig.savefig(FIG / "hansard_suspicion_terms.png", dpi=170)
    plt.close(fig)
    print("\nWrote hansard_* tables -> outputs/tables/ ; hansard_suspicion_terms.png -> outputs/figures/")
    print("Cleaned debate texts saved as references/hansard/*.txt")


if __name__ == "__main__":
    main()
