# Verifying the origin register against a primary source: The London Gazette

**What this is.** The origin register (`data/origin_register.csv`) was hand coded from
secondary histories (Cassis, Chapman, Kynaston, Jones, Roberts, and others). The most
attackable part of the paper is therefore that the labels and the wartime fates rest on
"a historian says so." This pass checks those claims against the official public record
of the British state, **The London Gazette** (thegazette.co.uk), which is free and fully
digitised. The Gazette carries exactly the notices that turn a secondary claim into a
primary one: winding up and liquidation notices, Trading with the Enemy orders, the
Public Trustee and Controller appointments over enemy firms, partnership notices, and
naturalisation lists.

**How it was done.** `src/gazette_verify.py` queries the Gazette's Atom data feed for
each of the 112 houses, caches every raw response in `data/gazette/raw/`, parses each
notice (real publish date, edition, issue, page, canonical URL, and the highlighted text
snippet), classifies it by type, and scores how likely it is to concern the right house.
Nothing is asserted automatically: every candidate is written out with its snippet so a
human can confirm it (`data/gazette/gazette_notices.csv`, 10,931 candidate notices;
per house counts in `data/gazette/gazette_house_summary.csv`). The notices below were
then read by hand and the confirmed ones collected in
`data/gazette/gazette_evidence_curated.csv`.

All citations are given as **edition, issue, page, date** and a link of the form
`https://www.thegazette.co.uk/<edition>/issue/<issue>/page/<page>`.

---

## 1. Confirmed: the German bank branches were sequestered and wound up

This is the core factual claim of Table 2, and the Gazette confirms it cleanly for all
three named houses.

- **Deutsche Bank (London).** London Gazette, Issue 30803, page 8498, 19 July 1918:
  the "Deutsche Bank, formerly at 4, George Yard, Lombard Street, and now situated at
  9, Bishopsgate" is listed in companies' liquidation with a Controller appointed. A
  later notice (Issue 33942, p3506, 1933) recites the Board of Trade order of 10 July
  1918 under the Trading with the Enemy Amendment Act 1916.
  <https://www.thegazette.co.uk/London/issue/30803/page/8498>
- **Disconto-Gesellschaft (London).** Same liquidation list, Issue 30803, page 8498,
  19 July 1918: "Direction der Disconto-Gesellschaft, formerly at 53, Cornhill, and now
  situate at Corbet Court, Gracechurch Street." Confirmed again by Issue 32303, page
  3332, 26 April 1921, a Board of Trade order under the Trading with the Enemy Amendment
  Act 1916. <https://www.thegazette.co.uk/London/issue/32303/page/3332>
- **Dresdner Bank (London).** Issue 33354, page 919, 7 February 1928: the Senior
  Official Receiver signs "as Controller of the Dresdner Bank (London) Branch" under the
  Trading with the Enemy Amendment Act 1916; liquidators were released in 1933 (Issue
  33933). <https://www.thegazette.co.uk/London/issue/33354/page/919>

So "London branch sequestered and sold, 1914 to 1916" in the register is slightly off on
timing (the formal winding up runs 1918 to the later 1920s, after a Controller had been
running the branch), but right on substance, and now resting on the primary record. The
register dates should be softened to "branch placed under a Controller and wound up under
the Trading with the Enemy Acts (orders 1918, completed in the 1920s)."

## 2. Confirmed: Schröder kept operating through the war, German named partner and all

The opening anecdote of the paper is Bruno Schröder. The Gazette confirms it to the day.
Pulling the naturalisation list page (see limits note below on why this needed the PDF,
not the snippet), London Gazette Issue 28892, page 7033, published 4 September 1914, lists:

> **Schroder, Rudolf Bruno | Germany | 7th August, 1914 | Banker | 35, Park Street, London**

(the "Budolf" of the raw OCR is Rudolf.) His oath of allegiance was sworn on 7 August 1914,
three days after Britain declared war on Germany. This is the primary record behind the
paper's first paragraph. The Gazette also shows the firm trading openly through the war
under the wartime partner-disclosure rules:

- London Gazette, Issue 28325, page 104, 1910: a partnership notice names "Baron Sir
  John Henry William Schroder, Baronet, Baron Rudolph Bruno Schroder, and Frank Cyril
  Tiarks, carrying on business as Merchants" as J. Henry Schröder & Co.
- Issue 29081, page 1946, 23 February **1915**, and Issue 29961, page 1993, 23 February
  **1917**: the firm's required wartime partner disclosure, "J. HENRY SCHRODER & CO,"
  still listing Baron Bruno Schroder and Frank Cyril Tiarks at Leadenhall Street.

A German named house openly filing its partner list in the City in 1915 and 1917, rather
than being wound up, is direct primary support for "survived." <https://www.thegazette.co.uk/London/issue/29961/page/1993>

## 3. Confirmed by absence: the neutrals were spared

The register claims Hambro (Danish) and Blydenstein (Dutch) escaped enemy treatment
because Denmark and the Netherlands were neutral. A null result is the right test here,
and it holds:

- **C. J. Hambro & Son**: no Trading with the Enemy, Public Trustee, or sequestration
  notice appears for Hambro in 1914 to 1920. The opposite turns up instead. Issue 31206,
  page 2855, 28 February 1919: **Eric Hambro made a Commander of a British order** while
  serving at the Ministry of Information. A family being honoured in British government
  service is the reverse of enemy treatment. <https://www.thegazette.co.uk/London/issue/31206/page/2855>
- **B. W. Blydenstein & Co**: likewise no enemy notice in the window. Consistent with
  "Netherlands neutral; survived."

## 4. A name collision the data handles correctly

The register says N. M. Rothschild & Sons, as a long naturalised British house, was
unaffected as an enemy alien. The only "Rothschild" enemy notice in the Gazette is Issue
29340, page 10582, 26 October 1915, concerning **"Rudolf von Goldschmidt-Rothschild, an
Enemy within the Act"**, a different, Continental person, not the British house. So the
record contains no enemy action against N. M. Rothschild & Sons, exactly as the register
claims. This is worth keeping as a worked example of why a name match alone is not a
verification.

## 5. Frühling & Goschen: firm confirmed, 1920 merger not found

- Confirmed that the firm existed under that German name in the City: Issue 21953, page
  4350, 26 December 1856, a partnership notice for "Fruhling and Goschen" of Austin
  Friars.
- **Not confirmed**: the register's claim that the firm was wound down and merged into
  Goschen & Cunliffe by 1920. Searches for "Goschen" with "Cunliffe", and for the firm
  name as a phrase, returned nothing in 1918 to 1922. The reconstitution of a private
  partnership was not necessarily Gazetted, so this remains on secondary authority
  (Kynaston) only.

---

## Honest limits of this method

1. **Naturalisations need the page, not the snippet.** The Gazette's naturalisation
   lists are dense tabular OCR pages of many names, and the search snippet centres on one
   matched word, so at the search level you cannot tell whether a "Schroder" on the page
   is our man. The fix is to download the page PDF and read it: doing that for Issue
   28892, page 7033 confirmed Baron Bruno Schröder's entry directly (see section 2). The
   page PDFs are cached in `data/gazette/pdf/`. So individual naturalisations are
   verifiable, but one page at a time, not in bulk from the search feed.
2. **Common names are noise, by design.** Distinctive house names (Schroder, Kleinwort,
   Blydenstein, Disconto) verify well. Generic ones (Smith, King, National, Union,
   County) return tens or hundreds of thousands of hits and cannot be machine verified;
   their rows in `gazette_house_summary.csv` should be read as "not individually
   checkable," not as evidence. This does not hurt the argument, because the houses the
   argument rests on are the distinctive émigré names.
3. **Coverage is the search index, not the whole Gazette.** A firm absent from the
   results is not proven absent from the record; it may sit on a page whose OCR missed
   the name. Absence is treated as supporting evidence only where, as with the neutrals,
   we positively expected a notice and the rest of the picture agrees.

## Files produced

- `data/gazette/raw/` — every raw Atom response, cached (re running the script reparses
  these and never re downloads).
- `data/gazette/gazette_notices.csv` — all 10,931 scored candidate notices.
- `data/gazette/gazette_house_summary.csv` — per house hit counts and best citation.
- `data/gazette/gazette_evidence_curated.csv` — the ten confirmed notices above.
- `src/gazette_verify.py` — reproducible pipeline. Run: `python src/gazette_verify.py`.

## Bottom line for the paper

The Gazette upgrades Table 2 from secondary to primary for the three German banks
(sequestration and winding up), pins Baron Bruno Schröder's naturalisation to 7 August
1914 from the official list, shows the firm trading openly through the war, and confirms
by absence that the neutral houses were spared. One item, the Frühling & Goschen merger of
1920, was not found in the Gazette and remains on secondary authority (Kynaston).
