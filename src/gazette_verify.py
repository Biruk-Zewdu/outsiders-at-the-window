"""Verify the origin register against a primary source: The London Gazette.

The Gazette (thegazette.co.uk) is the official public record of the British state,
free and fully digitised back to 1665. It carries the notices that confirm the two
things our register asserts but only cites secondary books for:
  - naturalisations  (a partner becoming British -> confirms foreign origin)
  - wartime fates    (winding-up, dissolution, enemy property handed to the Public
                      Trustee -> confirms the Table 2 fates)

This script queries the Gazette's Atom data feed for each house, caches every raw
response, parses the notices (real publish date, issue, page, canonical URL, and a
highlighted text snippet), classifies each by what kind of notice it is, and scores
how likely it is to be the right house. Nothing is asserted as a match automatically:
every hit is written out with its snippet so a human can confirm it. See
notes/gazette_verification.md for the readable summary.

Run:  python src/gazette_verify.py            (full register)
      python src/gazette_verify.py Schroder Huth "Deutsche Bank (London)"   (subset)
"""
from __future__ import annotations
import sys, re, time, html, urllib.parse, urllib.request
from pathlib import Path
import xml.etree.ElementTree as ET
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "gazette" / "raw"
RAW.mkdir(parents=True, exist_ok=True)
NOTES = ROOT / "notes"

FEED = "https://www.thegazette.co.uk/all-notices/notice/data.feed"
A = "{http://www.w3.org/2005/Atom}"
F = "{https://www.thegazette.co.uk/facets}"
UA = "Mozilla/5.0 (research; digital-history term paper; polite)"

# Date window: from before the first crisis to after the last fate (Huth wound up 1936).
START, END = "1840-01-01", "1945-12-31"
MAX_PAGES = 6          # cap at ~60 notices per house
PAGE_PAUSE = 0.5       # be polite to the server

# Distinctive, OCR-robust ASCII search tokens for the houses that carry the argument.
# (Umlauts and unstable spellings are avoided; e.g. Fruhling -> search the partner Goschen.)
TOKENS = {
    "J. Henry Schröder & Co": "Schroder",
    "Frederick Huth & Co": "Huth",
    "Kleinwort, Sons & Co": "Kleinwort",
    "C. J. Hambro & Son": "Hambro",
    "N. M. Rothschild & Sons": "Rothschild",
    "Bischoffsheim & Goldschmidt": "Bischoffsheim",
    "Frühling & Goschen": "Goschen",
    "Stern Brothers": "Stern Brothers",
    "S. Oppenheim & Sons": "Oppenheim",
    "William Brandt's Sons & Co": "Brandt",
    "B. W. Blydenstein & Co": "Blydenstein",
    "Samuel Montagu & Co": "Montagu",
    "Ralli Brothers": "Ralli",
    "R. Raphael & Sons": "Raphael",
    "Cama & Co": "Cama",
    "Dadabhai Naoroji & Co": "Naoroji",
    "George Peabody & Co": "Peabody",
    "J. S. Morgan & Co": "Morgan Grenfell",
    "Brown, Shipley & Co": "Shipley",
    "Deutsche Bank (London)": "Deutsche Bank",
    "Dresdner Bank (London)": "Dresdner",
    "Disconto-Gesellschaft (London)": "Disconto",
    "Overend, Gurney & Co": "Overend Gurney",
    "Agra & Masterman's Bank": "Masterman",
}

# Houses whose origin/fate the thesis actually rests on. Reported first.
PRIORITY_GROUPS = {
    "Émigré: German & Central European", "Émigré: Greek & Levantine",
    "Émigré: Indian / Parsi", "Émigré: American", "Foreign bank (1914 wartime)",
}

TRANS = str.maketrans("öäüéèáàóòíìúùçß", "oaueeaaooiiuucs")


def derive_token(house: str) -> str:
    """Pick the most distinctive word from a house name for houses not hand-mapped."""
    cleaned = house.translate(TRANS)
    cleaned = re.sub(r"\(.*?\)", " ", cleaned)
    stop = {"co", "sons", "son", "brothers", "bank", "and", "of", "the", "london",
            "company", "ltd", "limited", "corporation", "corp", "bros"}
    for w in re.split(r"[\s,.&]+", cleaned):
        if len(w) > 2 and w.lower() not in stop:
            return w
    return cleaned.strip()


CATEGORIES = [
    ("naturalisation", r"naturaliz|naturalis|certificate of natural|oath of allegiance|former nationality"),
    # honours/appointments first: a German-named man getting a British order or office is
    # an integration signal, and it must not be mis-read as enemy treatment.
    ("honour", r"most excellent order|to be (?:a )?(?:commander|officer|member|knight|companion)|"
               r"order of the british empire|\bO\.?B\.?E\b|\bC\.?B\.?E\b|\bM\.?B\.?E\b|"
               r"knighthood|mentioned in despatch|his majesty has been graciously"),
    ("enemy_property", r"trading with the enemy|public trustee|custodian of enemy|sequestrat|"
                       r"enemy (?:bank|firm|property|business|subject)|wound up.*enemy|controller"),
    ("winding_up", r"winding[- ]up|liquidat|voluntar(?:y|ily) wound|in liquidation|ordered to be wound up"),
    ("dissolution", r"dissolv|partnership.*dissol|retired from|carrying on business|carried on business"),
    ("bankruptcy", r"bankrupt|receiving order|adjudicat"),
    ("company", r"capital|registered office|dividend|prospectus|debenture|director"),
]


def classify(snippet: str) -> str:
    s = snippet.lower()
    for name, pat in CATEGORIES:
        if re.search(pat, s):
            return name
    return "other"


def fetch_feed(token: str, page: int) -> str:
    qs = urllib.parse.urlencode({
        "text": token, "start-publish-date": START, "end-publish-date": END,
        "results-page-size": "20", "results-page": str(page),
    })
    req = urllib.request.Request(f"{FEED}?{qs}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace")


def strip_tags(xhtml: str) -> str:
    txt = re.sub(r"<[^>]+>", "", xhtml)
    return html.unescape(re.sub(r"\s+", " ", txt)).strip()


def parse(xml_text: str):
    root = ET.fromstring(xml_text)
    total_el = root.find(f"{F}total")
    total = int(total_el.text) if total_el is not None and total_el.text else 0
    out = []
    for e in root.findall(f"{A}entry"):
        title = (e.findtext(f"{A}title") or "").strip()
        url = (e.findtext(f"{A}id") or "").strip()
        published = (e.findtext(f"{A}published") or "")[:10]
        pdf = ""
        for l in e.findall(f"{A}link"):
            if l.get("href"):
                pdf = "https://www.thegazette.co.uk" + l.get("href")
                break
        m_iss = re.search(r"(Issue|Supplement)\s+(\d+)", title)
        m_pg = re.search(r"Page\s+(\d+)", title)
        m_ed = re.search(r"/(London|Edinburgh|Belfast)/", url)
        content = e.find(f"{A}content")
        snippet = strip_tags(ET.tostring(content, encoding="unicode")) if content is not None else ""
        out.append({
            "date": published, "edition": m_ed.group(1) if m_ed else "London",
            "issue": m_iss.group(2) if m_iss else "",
            "kind_of_issue": m_iss.group(1) if m_iss else "", "page": m_pg.group(1) if m_pg else "",
            "url": url, "pdf": pdf, "snippet": snippet,
        })
    return total, out


def score(house: str, token: str, origin: str, rec: dict) -> int:
    """0..3 confidence that this notice really concerns this house, from the snippet."""
    s = rec["snippet"].lower()
    toks = [t for t in re.split(r"\s+", token.lower()) if len(t) > 2]
    if not any(t in s for t in toks):
        return 0                          # token not even in the highlighted context
    sc = 1
    if rec["category"] in ("naturalisation", "honour", "enemy_property", "winding_up", "dissolution"):
        sc += 1                           # a notice type that matters for us
    corrob = ["& co", "bankers", "banker", "merchant", "limited", "lombard", "leadenhall",
              "throgmorton", "austin friars", "old broad", "bishopsgate", "mark lane",
              "fenchurch", "e.c", "partnership"]
    nat = re.split(r"[\s(/]", origin.lower())[0]
    if nat and len(nat) > 3:
        corrob.append(nat)
    if any(c in s for c in corrob):
        sc += 1
    return min(sc, 3)


def run(houses_df: pd.DataFrame):
    notices, summaries = [], []
    for _, row in houses_df.iterrows():
        house, origin, group = row["house"], row["origin"], row["group"]
        token = TOKENS.get(house) or derive_token(house)
        slug = re.sub(r"[^a-z0-9]+", "_", house.lower()).strip("_")
        total, recs = 0, []
        cached = sorted(RAW.glob(f"{slug}_p*.xml"))
        for page in range(1, MAX_PAGES + 1):
            fp = RAW / f"{slug}_p{page}.xml"
            if cached and fp.exists():          # reuse cache; never re-download
                xml_text = fp.read_text()
            elif cached and not fp.exists():
                break                            # cache for this house ends here
            else:
                try:
                    xml_text = fetch_feed(token, page)
                except Exception as ex:
                    print(f"  ! {house}: {ex}")
                    break
                fp.write_text(xml_text)
                time.sleep(PAGE_PAUSE)
            total, page_recs = parse(xml_text)
            recs.extend(page_recs)
            if page * 20 >= total or not page_recs:
                break
        for rec in recs:
            rec["category"] = classify(rec["snippet"])
            rec["confidence"] = score(house, token, origin, rec)
            rec.update({"house": house, "origin": origin, "group": group, "token": token})
        recs = [r for r in recs if r["confidence"] >= 1]
        recs.sort(key=lambda r: (-r["confidence"], r["date"]))
        notices.extend(recs)
        cats = sorted({r["category"] for r in recs if r["confidence"] >= 2})
        best = recs[0] if recs else {}
        summaries.append({
            "house": house, "group": group, "origin": origin, "token": token,
            "gazette_total_hits": total, "candidates": len(recs),
            "strong_candidates": sum(1 for r in recs if r["confidence"] >= 2),
            "notice_types": ", ".join(cats),
            "best_date": best.get("date", ""), "best_edition": best.get("edition", ""),
            "best_issue": best.get("issue", ""),
            "best_page": best.get("page", ""), "best_url": best.get("url", ""),
            "priority": group in PRIORITY_GROUPS,
        })
        print(f"  {house[:38]:38s} token={token[:16]:16s} hits={total:5d} "
              f"kept={len(recs):3d} strong={summaries[-1]['strong_candidates']:2d}  {', '.join(cats)}")
    return pd.DataFrame(notices), pd.DataFrame(summaries)


def main():
    reg = pd.read_csv(DATA / "origin_register.csv")
    args = sys.argv[1:]
    if args:
        mask = reg["house"].apply(lambda h: any(a.lower() in h.lower() or a.lower() in TOKENS.get(h, "").lower() for a in args))
        reg = reg[mask]
        print(f"Subset: {list(reg['house'])}")
    print(f"Querying The London Gazette for {len(reg)} houses ({START}..{END})\n")
    notices, summary = run(reg)
    outdir = DATA / "gazette"
    cols = ["house", "group", "origin", "token", "confidence", "category", "date",
            "edition", "kind_of_issue", "issue", "page", "url", "pdf", "snippet"]
    notices = notices[cols] if len(notices) else pd.DataFrame(columns=cols)
    notices.to_csv(outdir / "gazette_notices.csv", index=False)
    summary.to_csv(outdir / "gazette_house_summary.csv", index=False)
    print(f"\nWrote {len(notices)} candidate notices -> data/gazette/gazette_notices.csv")
    print(f"Wrote per-house summary           -> data/gazette/gazette_house_summary.csv")
    print(f"Raw feeds cached                  -> data/gazette/raw/")


if __name__ == "__main__":
    main()
