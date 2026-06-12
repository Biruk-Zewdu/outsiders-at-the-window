"""Outsiders at the Window — Stage 1 data curation.

Builds, from the BoE LOLR transaction ledger:
  1. data/origin_register.csv     — hand-coded prosopography of the houses
                                    (origin, founder, year, community, WWI fate)
  2. data/house_crosswalk.csv     — raw ledger name -> canonical house + origin group
                                    (this is the cross-crisis entity-resolution layer
                                     that merges spelling / OCR / firm-name variants)
  3. data/transactions_tagged.parquet — the ledger with origin columns joined on

The register below is a v1 grounded in the standard secondary literature
(Cassis, *City Bankers 1890-1914*; Chapman, *The Rise of Merchant Banking*;
Kynaston, *The City of London*) plus targeted verification of the WWI "fate"
claims (Hansard 1916 on sequestered German banks; encyclopedia.com / Wikipedia
on Schröder and Frühling & Goschen). `confidence` flags how settled each row is;
refine the registry as you read.

Patterns are regexes matched case-insensitively against `counterparty_clean`;
they are written to absorb the OCR / spelling variants documented in
notes/ (e.g. 'Truhling' for 'Fruhling', 'S.N.Schroder' for 'J.H.Schroder').
"""
from __future__ import annotations
import re
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# Broad analytical groups -------------------------------------------------
G_GER = "Émigré: German & Central European"
G_GRK = "Émigré: Greek & Levantine"
G_PAR = "Émigré: Indian / Parsi"
G_AME = "Émigré: American"
G_BRM = "British: private / merchant (native)"
G_BRD = "British: discount house"
G_BRC = "British: clearing / joint-stock bank"
G_COL = "Colonial / Imperial bank"
G_FOR = "Foreign bank (1914 wartime)"

# The register. Each entry: canonical house + match patterns + prosopography.
# fields: house, patterns, origin, group, founder, founded, community, wwi_fate, confidence, source
REGISTER = [
    # ---- German & Central European émigré merchant houses (the core) ----
    dict(house="J. Henry Schröder & Co", patterns=[r"schroder"], origin="German (Hamburg)", group=G_GER,
         founder="Johann Heinrich Schröder", founded=1818, community="German / Hanseatic Protestant",
         wwi_fate="Senior partner Baron Bruno Schröder naturalised within days of war (Aug 1914); firm survived as Schroders",
         confidence="high", source="encyclopedia.com (Schroders plc); Roberts, Schroders"),
    dict(house="Frederick Huth & Co", patterns=[r"huth"], origin="German (Stade/Hanover)", group=G_GER,
         founder="Johann Friedrich (Frederick) Huth", founded=1809, community="German merchant diaspora",
         wwi_fate="Survived WWI but long declined; wound up 1936",
         confidence="high", source="Chapman, Rise of Merchant Banking"),
    dict(house="Kleinwort, Sons & Co", patterns=[r"kleinwort"], origin="German (Holstein)", group=G_GER,
         founder="Alexander Friedrich Kleinwort", founded=1855, community="German (Schleswig-Holstein)",
         wwi_fate="Partners naturalised; survived, later Kleinwort Benson",
         confidence="high", source="Cassis; Wake, Kleinwort Benson"),
    dict(house="C. J. Hambro & Son", patterns=[r"hambro"], origin="Danish (Copenhagen)", group=G_GER,
         founder="Carl Joachim Hambro", founded=1839, community="Danish (neutral in WWI) / Sephardi descent",
         wwi_fate="Denmark neutral — escaped enemy-alien treatment; survived as Hambros Bank",
         confidence="high", source="Bramsen & Wain, The Hambros"),
    dict(house="N. M. Rothschild & Sons", patterns=[r"rothschild"], origin="German-Jewish (Frankfurt)", group=G_GER,
         founder="Nathan Mayer Rothschild", founded=1811, community="German-Jewish (Frankfurt Judengasse)",
         wwi_fate="Long-naturalised British branch; unaffected as enemy alien",
         confidence="high", source="Ferguson, The World's Banker"),
    dict(house="Bischoffsheim & Goldschmidt", patterns=[r"bischoffsheim", r"goldschmidt"], origin="German-Jewish (Mainz/Amsterdam)", group=G_GER,
         founder="Louis-Raphaël Bischoffsheim", founded=1846, community="German/Dutch-Jewish; later merged into Banque de Paris",
         wwi_fate="Largely absorbed/wound down before WWI", confidence="medium", source="Cassis"),
    dict(house="Frühling & Goschen", patterns=[r"fruhling", r"truhling"], origin="German (Leipzig)", group=G_GER,
         founder="Heinrich Frühling & W. H. Göschen", founded=1814, community="German Saxon merchant",
         wwi_fate="German-named firm wound down amid anti-German pressure; merged into Goschen & Cunliffe 1920",
         confidence="high", source="Wikipedia (Harry Goschen); Kynaston"),
    dict(house="Stern Brothers", patterns=[r"stern bros", r"stern brother"], origin="German-Jewish (Frankfurt)", group=G_GER,
         founder="Stern family", founded=1833, community="German-Jewish (Frankfurt)",
         wwi_fate="Survived", confidence="medium", source="Cassis"),
    dict(house="S. Oppenheim & Sons", patterns=[r"oppenheim"], origin="German-Jewish (Cologne)", group=G_GER,
         founder="Salomon Oppenheim", founded=1789, community="German-Jewish (Rhineland)",
         wwi_fate="Cologne house; London ties strained by war", confidence="medium", source="Cassis"),
    dict(house="William Brandt's Sons & Co", patterns=[r"brandt'?s", r"brandts", r"e h brandt", r"w brandt", r"william brandt"],
         origin="German (Hamburg/Archangel)", group=G_GER,
         founder="Edmund Heinrich Brandt", founded=1805, community="German-Russian (Archangel trade)",
         wwi_fate="Russia-trade house; strained by war and 1917; survived diminished", confidence="medium", source="Chapman"),
    dict(house="E. Sieveking & Son", patterns=[r"sieveking"], origin="German (Hamburg)", group=G_GER,
         founder="Sieveking family", founded=None, community="German Hanseatic", wwi_fate="—",
         confidence="low", source="Cassis"),
    dict(house="Schunck, Souchay & Co", patterns=[r"schunck"], origin="German", group=G_GER,
         founder="Souchay family", founded=None, community="German (Saxon/Huguenot)", wwi_fate="—",
         confidence="low", source="Chapman"),
    dict(house="Bieber & Co", patterns=[r"bieber"], origin="German", group=G_GER, founder=None, founded=None,
         community="German merchant", wwi_fate="—", confidence="low", source="ledger"),
    dict(house="Lütgens & Ripley", patterns=[r"lutgens"], origin="German (Hamburg)", group=G_GER, founder=None, founded=None,
         community="German Hanseatic", wwi_fate="—", confidence="low", source="ledger"),
    dict(house="Haarbleicher & Schumann", patterns=[r"haarbleich"], origin="German (Hamburg)", group=G_GER, founder=None, founded=None,
         community="German Hanseatic", wwi_fate="—", confidence="low", source="ledger"),
    dict(house="König Brothers", patterns=[r"konig bro"], origin="German", group=G_GER, founder=None, founded=None,
         community="German merchant", wwi_fate="—", confidence="low", source="ledger"),
    dict(house="Suse & Sibeth", patterns=[r"suse \+ sibeth", r"suse & sibeth"], origin="German (Hamburg)", group=G_GER,
         founder=None, founded=None, community="German Hanseatic", wwi_fate="—", confidence="low", source="ledger"),
    dict(house="R. Heine, Semon & Co", patterns=[r"heine semon"], origin="German-Jewish", group=G_GER, founder=None, founded=None,
         community="German-Jewish (Heine family)", wwi_fate="—", confidence="low", source="ledger"),
    dict(house="Kraeutler & Mieville", patterns=[r"kraeutler"], origin="German / Swiss", group=G_GER, founder=None, founded=None,
         community="German-Swiss", wwi_fate="—", confidence="low", source="ledger"),
    dict(house="J. L. Lemme & Co", patterns=[r"lemme & co", r"j l lemme"], origin="German", group=G_GER, founder=None, founded=None,
         community="German merchant", wwi_fate="—", confidence="low", source="ledger"),
    dict(house="M. Levin & Adler", patterns=[r"levin & adler"], origin="German-Jewish", group=G_GER, founder=None, founded=None,
         community="German-Jewish", wwi_fate="—", confidence="low", source="ledger"),
    dict(house="B. Simon & A. Jacoby", patterns=[r"simon & a jacoby"], origin="German-Jewish", group=G_GER, founder=None, founded=None,
         community="German-Jewish", wwi_fate="—", confidence="low", source="ledger"),
    dict(house="H. J. Enthoven & Sons", patterns=[r"einthoven", r"enthoven"], origin="Dutch", group=G_GER, founder=None, founded=None,
         community="Dutch merchant", wwi_fate="Netherlands neutral", confidence="medium", source="ledger"),
    dict(house="B. W. Blydenstein & Co", patterns=[r"blydenstein"], origin="Dutch (Twente)", group=G_GER,
         founder="Benjamin Willem Blijdenstein", founded=1858, community="Dutch (Twentsche Bank agency)",
         wwi_fate="Netherlands neutral; survived", confidence="medium", source="Cassis"),
    dict(house="J. C. Im Thurn & Co", patterns=[r"im thurm", r"im thurn"], origin="Swiss (Schaffhausen)", group=G_GER, founder=None, founded=None,
         community="Swiss", wwi_fate="Switzerland neutral", confidence="medium", source="Chapman"),
    dict(house="Bordier, Fabris & Co", patterns=[r"bordier"], origin="Swiss (Geneva)", group=G_GER, founder=None, founded=None,
         community="Genevan Protestant", wwi_fate="Switzerland neutral", confidence="low", source="ledger"),
    dict(house="Heilbut, Symons & Co", patterns=[r"heilbut"], origin="German", group=G_GER, founder=None, founded=None,
         community="German merchant", wwi_fate="—", confidence="low", source="ledger"),

    # ---- Greek & Levantine émigré houses ----
    dict(house="Ralli Brothers", patterns=[r"\bralli\b", r"t & j ralli", r"p t ralli", r"p\. t\. ralli"], origin="Greek (Chios)", group=G_GRK,
         founder="Pandia Ralli & brothers", founded=1818, community="Greek (Chiot diaspora)",
         wwi_fate="Greek; unaffected by enemy-alien rules; survived", confidence="high", source="Chapman; Catsiyannis, The Rallis"),
    dict(house="Schilizzi & Co", patterns=[r"schilizzi"], origin="Greek (Chios)", group=G_GRK, founder=None, founded=None,
         community="Greek (Chiot)", wwi_fate="—", confidence="medium", source="Chapman"),
    dict(house="Zarifi Brothers & Co", patterns=[r"zarifi"], origin="Greek (Constantinople)", group=G_GRK, founder=None, founded=None,
         community="Greek (Ottoman)", wwi_fate="—", confidence="medium", source="Chapman"),
    dict(house="Spartali & Co", patterns=[r"spartali"], origin="Greek", group=G_GRK, founder=None, founded=None,
         community="Greek (Chiot/Levantine)", wwi_fate="—", confidence="low", source="ledger"),
    dict(house="Leonino & Co", patterns=[r"leonino"], origin="Italian-Jewish", group=G_GRK, founder=None, founded=None,
         community="Italian-Jewish / Levantine", wwi_fate="—", confidence="low", source="ledger"),

    # ---- Indian / Parsi houses ----
    dict(house="Cama & Co", patterns=[r"\bcama\b"], origin="Parsi (Bombay)", group=G_PAR,
         founder="Cama family", founded=1855, community="Parsi (first Indian firm in the City)",
         wwi_fate="Indian (imperial subject); —", confidence="medium", source="Chapman; Cassis"),
    dict(house="Framjee & Co", patterns=[r"framjee"], origin="Parsi (Bombay)", group=G_PAR, founder=None, founded=None,
         community="Parsi", wwi_fate="—", confidence="low", source="ledger"),
    dict(house="Dadabhai Naoroji & Co", patterns=[r"naoroji"], origin="Parsi (Bombay)", group=G_PAR,
         founder="Dadabhai Naoroji", founded=1855, community="Parsi; Naoroji later first Indian/British MP",
         wwi_fate="—", confidence="high", source="Naoroji biographies"),

    # ---- American houses ----
    dict(house="George Peabody & Co", patterns=[r"peabody"], origin="American (Massachusetts)", group=G_AME,
         founder="George Peabody", founded=1851, community="American; predecessor of J. S. Morgan",
         wwi_fate="(superseded 1864)", confidence="high", source="Chapman; Carosso, The Morgans"),
    dict(house="J. S. Morgan & Co", patterns=[r"j\.? ?s\.? morgan"], origin="American", group=G_AME,
         founder="Junius Spencer Morgan", founded=1864, community="American (successor to Peabody); later Morgan Grenfell",
         wwi_fate="Anglo-American; flourished as Allied war financier", confidence="high", source="Carosso, The Morgans"),
    dict(house="Brown, Shipley & Co", patterns=[r"brown shipley"], origin="Anglo-American (Baltimore/Liverpool)", group=G_AME,
         founder="Alexander Brown family", founded=1810, community="Anglo-American (Brown Brothers)",
         wwi_fate="Survived", confidence="high", source="Chapman"),
    dict(house="McCalmont Brothers & Co", patterns=[r"mccalmont"], origin="Anglo-American / Irish", group=G_AME, founder=None, founded=None,
         community="Anglo-American", wwi_fate="—", confidence="low", source="ledger"),
    dict(house="Guaranty Trust Co of New York", patterns=[r"guaranty trust"], origin="American", group=G_AME, founder=None, founded=1864,
         community="American trust bank (1914 entrant)", wwi_fate="Allied war finance", confidence="medium", source="ledger"),
    dict(house="International Banking Corporation", patterns=[r"international banking corp"], origin="American", group=G_AME, founder=None, founded=1902,
         community="American (Citibank precursor)", wwi_fate="—", confidence="medium", source="ledger"),

    # ---- British native private / merchant houses (baseline) ----
    dict(house="Baring Brothers & Co", patterns=[r"baring"], origin="German-origin, naturalised Anglo establishment", group=G_BRM,
         founder="John & Francis Baring (sons of Johann Baring of Bremen)", founded=1762,
         community="German-émigré root, fully Anglo by 19thc; rescued 1890",
         wwi_fate="Established Anglo house", confidence="high", source="Ziegler, The Sixth Great Power"),
    dict(house="Glyn, Mills, Currie & Co", patterns=[r"glyn"], origin="British", group=G_BRM, founder="Glyn family", founded=1753,
         community="English private bank", wwi_fate="Survived", confidence="high", source="Kynaston"),
    dict(house="Robarts, Lubbock & Co", patterns=[r"robarts lubbock"], origin="British", group=G_BRM, founder=None, founded=None,
         community="English private bank", wwi_fate="—", confidence="medium", source="ledger"),

    # ---- British discount houses (comparison group) ----
    dict(house="Overend, Gurney & Co", patterns=[r"overend gurney"], origin="British (Quaker, Norwich)", group=G_BRD,
         founder="Gurney family", founded=1800, community="English Quaker; failed 1866",
         wwi_fate="(failed 1866)", confidence="high", source="Flandreau-Ugolini"),
    dict(house="Union Discount Co. of London", patterns=[r"union discount"], origin="British", group=G_BRD, founder=None, founded=1885,
         community="English discount house", wwi_fate="Survived", confidence="high", source="ledger"),
    dict(house="National Discount Co.", patterns=[r"national discount"], origin="British", group=G_BRD, founder=None, founded=1856,
         community="English discount house", wwi_fate="Survived", confidence="high", source="ledger"),
    dict(house="Alexanders & Co (discount)", patterns=[r"a & g w alexander", r"alexanders & co"], origin="British (Quaker)", group=G_BRD,
         founder="Alexander family", founded=None, community="English Quaker discount house", wwi_fate="Survived",
         confidence="medium", source="ledger"),
    dict(house="Smith, St Aubyn & Co", patterns=[r"smith st aubyn"], origin="British", group=G_BRD, founder=None, founded=None,
         community="English discount house", wwi_fate="—", confidence="medium", source="ledger"),
    dict(house="Sanderson, Sandeman & Co", patterns=[r"sanderson sandeman"], origin="British", group=G_BRD, founder=None, founded=None,
         community="English bill broker", wwi_fate="—", confidence="low", source="ledger"),
    dict(house="Gillett Brothers", patterns=[r"gillett bro"], origin="British (Quaker)", group=G_BRD, founder=None, founded=None,
         community="English Quaker discount house", wwi_fate="—", confidence="low", source="ledger"),

    # ---- British clearing / joint-stock banks (comparison group) ----
    dict(house="London County & Westminster Bank", patterns=[r"london county & westminster", r"london county bank", r"westmin"],
         origin="British", group=G_BRC, founder=None, founded=None, community="English clearing bank", wwi_fate="—",
         confidence="medium", source="ledger"),
    dict(house="Lloyds Bank", patterns=[r"lloyd'?s bank"], origin="British", group=G_BRC, founder=None, founded=None,
         community="English clearing bank", wwi_fate="—", confidence="high", source="ledger"),
    dict(house="National Provincial Bank", patterns=[r"national provincial"], origin="British", group=G_BRC, founder=None, founded=None,
         community="English clearing bank", wwi_fate="—", confidence="high", source="ledger"),
    dict(house="Parr's Bank", patterns=[r"parr'?s bank"], origin="British", group=G_BRC, founder=None, founded=None,
         community="English clearing bank", wwi_fate="—", confidence="medium", source="ledger"),
    dict(house="Union of London & Smiths Bank", patterns=[r"union smiths", r"union bank of london"], origin="British", group=G_BRC,
         founder=None, founded=None, community="English clearing bank", wwi_fate="—", confidence="medium", source="ledger"),

    # ---- Colonial / Imperial banks (comparison group) ----
    dict(house="Oriental Bank Corporation", patterns=[r"oriental bank"], origin="British colonial (East)", group=G_COL, founder=None, founded=1842,
         community="Anglo-Eastern exchange bank; failed 1884/revived", wwi_fate="—", confidence="high", source="Jones, British Multinational Banking"),
    dict(house="Agra & Masterman's Bank", patterns=[r"agra & masterman", r"agra and masterman"], origin="British colonial (India)", group=G_COL,
         founder=None, founded=1833, community="Anglo-Indian bank; failed 1866", wwi_fate="(failed 1866)", confidence="high", source="Jones"),
    dict(house="Bank of Hindustan", patterns=[r"bank of hindustan"], origin="British colonial (India)", group=G_COL, founder=None, founded=None,
         community="Anglo-Indian bank", wwi_fate="—", confidence="medium", source="ledger"),
    dict(house="Chartered Bank of India, Australia & China", patterns=[r"chartered bank of india"], origin="British colonial", group=G_COL,
         founder=None, founded=1853, community="Anglo-Eastern exchange bank", wwi_fate="Survived (Standard Chartered)", confidence="high", source="Jones"),
    dict(house="Hongkong & Shanghai Banking Corp.", patterns=[r"hong kong & shanghai", r"hongkong"], origin="British colonial (China)", group=G_COL,
         founder=None, founded=1865, community="Anglo-Eastern exchange bank", wwi_fate="Survived (HSBC)", confidence="high", source="Jones"),
    dict(house="National Bank of India", patterns=[r"national bank of india", r"natl bk of india"], origin="British colonial (India)", group=G_COL,
         founder=None, founded=1863, community="Anglo-Indian exchange bank", wwi_fate="Survived", confidence="high", source="Jones"),
    dict(house="Mercantile Bank of India", patterns=[r"mercantile bank of india"], origin="British colonial (India)", group=G_COL,
         founder=None, founded=1853, community="Anglo-Eastern exchange bank", wwi_fate="Survived", confidence="medium", source="Jones"),
    dict(house="Bank of New South Wales", patterns=[r"new south wales"], origin="British colonial (Australia)", group=G_COL, founder=None, founded=1817,
         community="Australian bank", wwi_fate="Survived (Westpac)", confidence="medium", source="ledger"),

    # ---- Foreign banks (1914 wartime entrants at the window) ----
    dict(house="Deutsche Bank (London)", patterns=[r"deutsche bank"], origin="German", group=G_FOR, founder=None, founded=1870,
         community="German universal bank — London branch", wwi_fate="London branch sequestered & sold 1914-16 (Public Trustee)",
         confidence="high", source="Hansard 1916, German Banks in London"),
    dict(house="Dresdner Bank (London)", patterns=[r"dresdner"], origin="German", group=G_FOR, founder=None, founded=1872,
         community="German bank — London branch", wwi_fate="London branch sequestered & sold 1914-16",
         confidence="high", source="Hansard 1916"),
    dict(house="Disconto-Gesellschaft (London)", patterns=[r"direction der discont", r"disconto"], origin="German", group=G_FOR,
         founder=None, founded=1851, community="German bank — London branch", wwi_fate="London branch sequestered & sold 1914-16",
         confidence="high", source="Hansard 1916"),
    dict(house="London Hanseatic Bank", patterns=[r"hanseatic"], origin="German", group=G_FOR, founder=None, founded=None,
         community="German-linked London bank", wwi_fate="enemy-linked; wound down", confidence="medium", source="ledger"),
    dict(house="Crédit Lyonnais", patterns=[r"credit lyonnais"], origin="French", group=G_FOR, founder=None, founded=1863,
         community="French bank — London branch (Allied)", wwi_fate="Allied", confidence="high", source="ledger"),
    dict(house="Comptoir National d'Escompte de Paris", patterns=[r"comptoir national"], origin="French", group=G_FOR, founder=None, founded=1848,
         community="French bank — London branch (Allied)", wwi_fate="Allied", confidence="high", source="ledger"),
    dict(house="Banque Belge", patterns=[r"banque belge"], origin="Belgian", group=G_FOR, founder=None, founded=None,
         community="Belgian bank (Allied)", wwi_fate="Allied", confidence="medium", source="ledger"),
    dict(house="Swiss Bankverein", patterns=[r"swiss bankverein", r"swiss bank"], origin="Swiss", group=G_FOR, founder=None, founded=1854,
         community="Swiss bank — London branch (neutral)", wwi_fate="neutral", confidence="medium", source="ledger"),
    dict(house="Credito Italiano", patterns=[r"credito italiano"], origin="Italian", group=G_FOR, founder=None, founded=1870,
         community="Italian bank (Allied from 1915)", wwi_fate="Allied", confidence="medium", source="ledger"),
    dict(house="Banca Commerciale Italiana", patterns=[r"banca commerciale italiana"], origin="Italian", group=G_FOR, founder=None, founded=1894,
         community="Italian bank", wwi_fate="Allied", confidence="medium", source="ledger"),
    dict(house="Imperial Ottoman Bank", patterns=[r"ottoman"], origin="Anglo-French / Ottoman", group=G_FOR, founder=None, founded=1863,
         community="Anglo-French bank of the Ottoman Empire", wwi_fate="enemy state but Anglo-French owned — complex", confidence="medium", source="ledger"),

    # ---- second pass: émigré houses surfaced in the unclassified audit ----
    dict(house="Samuel Montagu & Co", patterns=[r"montagu"], origin="Anglo-Jewish (German-Jewish descent)", group=G_GER,
         founder="Samuel Montagu (b. Montagu Samuel)", founded=1853, community="Jewish bullion broker; family of German-Jewish origin",
         wwi_fate="Naturalised Anglo-Jewish; survived", confidence="medium", source="Cassis"),
    dict(house="R. Raphael & Sons", patterns=[r"raphael"], origin="Sephardi-Jewish (Dutch/Portuguese)", group=G_GRK,
         founder="Raphael family", founded=1787, community="Sephardi-Jewish bullion brokers",
         wwi_fate="Long-established Anglo-Jewish; survived", confidence="medium", source="ledger; Chapman"),
    dict(house="King & Foa", patterns=[r"king & foa"], origin="Sephardi-Jewish / Anglo (Foa family)", group=G_GRK,
         founder="Foa family", founded=None, community="Levantine/Sephardi foreign-exchange house",
         wwi_fate="—", confidence="low", source="ledger"),
    dict(house="A. Ruffer & Sons", patterns=[r"ruffer"], origin="French/German (Alsace)", group=G_GER,
         founder="Ruffer family", founded=None, community="Alsatian merchant bank (Lyon/London)",
         wwi_fate="French-aligned; strained", confidence="low", source="ledger"),

    # ---- second pass: native-British baseline (discount / merchant / clearing) ----
    dict(house="Allen, Harvey & Ross", patterns=[r"allen harvey"], origin="British", group=G_BRD, founder=None, founded=None,
         community="English bill broker / discount house", wwi_fate="—", confidence="medium", source="ledger"),
    dict(house="Bruce, Wilkinson & Co", patterns=[r"bruce wilkinson"], origin="British", group=G_BRD, founder=None, founded=None,
         community="English bill broker", wwi_fate="—", confidence="medium", source="ledger"),
    dict(house="Frith, Sands & Co", patterns=[r"frith sands", r"frith, sands"], origin="British", group=G_BRD, founder=None, founded=None,
         community="English bill broker", wwi_fate="—", confidence="medium", source="ledger"),
    dict(house="White & Shaxson", patterns=[r"white & shaxson"], origin="British", group=G_BRD, founder=None, founded=None,
         community="English discount house", wwi_fate="—", confidence="medium", source="ledger"),
    dict(house="Cater & Co", patterns=[r"\bcater\b"], origin="British", group=G_BRD, founder=None, founded=None,
         community="English discount house (later Cater Ryder)", wwi_fate="—", confidence="medium", source="ledger"),
    dict(house="Ryder & Co", patterns=[r"ryder & co"], origin="British", group=G_BRD, founder=None, founded=None,
         community="English discount house", wwi_fate="—", confidence="low", source="ledger"),
    dict(house="Cunliffe Brothers", patterns=[r"cunliffe"], origin="British", group=G_BRM, founder="Cunliffe family", founded=None,
         community="English merchant bank (Lord Cunliffe, Governor of the Bank 1913-18)", wwi_fate="merged into Goschen & Cunliffe 1920",
         confidence="medium", source="Kynaston"),
    dict(house="Smith, Fleming & Co", patterns=[r"smith fleming", r"smith, fleming"], origin="British (Anglo-Indian)", group=G_BRM,
         founder=None, founded=None, community="Anglo-Indian eastern merchant house", wwi_fate="—", confidence="low", source="ledger"),
    dict(house="Wallace Brothers & Co", patterns=[r"wallace bro"], origin="British (Anglo-Burmese)", group=G_BRM, founder=None, founded=None,
         community="Anglo-Eastern merchant house", wwi_fate="—", confidence="low", source="ledger"),
    dict(house="Daniell, Cazenove & Co", patterns=[r"cazenove", r"cafenove"], origin="British (Huguenot-descended, Anglo)", group=G_BRM,
         founder="Cazenove family", founded=None, community="English (Huguenot-origin) house", wwi_fate="—", confidence="low", source="ledger"),
    dict(house="Brightwen & Co", patterns=[r"brightwen"], origin="British", group=G_BRM, founder=None, founded=None,
         community="English merchant / bill house", wwi_fate="—", confidence="low", source="ledger"),
    dict(house="Reeves, Whitburn & Co", patterns=[r"reeves whitburn"], origin="British", group=G_BRM, founder=None, founded=None,
         community="English merchant / bill house", wwi_fate="—", confidence="low", source="ledger"),
    dict(house="Baker, Duncombe & Co", patterns=[r"baker duncombe"], origin="British", group=G_BRM, founder=None, founded=None,
         community="English merchant / bill house", wwi_fate="—", confidence="low", source="ledger"),
    dict(house="Barclay & Co", patterns=[r"^barclay & co"], origin="British (Quaker)", group=G_BRC, founder="Barclay family", founded=1690,
         community="English Quaker clearing bank", wwi_fate="—", confidence="high", source="ledger"),
    dict(house="Royal Bank of Scotland", patterns=[r"royal bank of scotland"], origin="British (Scottish)", group=G_BRC, founder=None, founded=1727,
         community="Scottish bank", wwi_fate="—", confidence="high", source="ledger"),
    dict(house="Union Bank of Scotland", patterns=[r"union bank of scotland"], origin="British (Scottish)", group=G_BRC, founder=None, founded=1830,
         community="Scottish bank", wwi_fate="—", confidence="medium", source="ledger"),
    dict(house="National Bank of Scotland", patterns=[r"national bank of scotland"], origin="British (Scottish)", group=G_BRC, founder=None, founded=1825,
         community="Scottish bank", wwi_fate="—", confidence="medium", source="ledger"),
    dict(house="Capital & Counties Bank", patterns=[r"capital & counties"], origin="British", group=G_BRC, founder=None, founded=None,
         community="English clearing bank", wwi_fate="—", confidence="medium", source="ledger"),
    dict(house="Alliance Bank", patterns=[r"alliance bank"], origin="British", group=G_BRC, founder=None, founded=1862,
         community="English joint-stock bank", wwi_fate="—", confidence="low", source="ledger"),
    dict(house="London Joint Stock Bank", patterns=[r"london joint & stock", r"lon jt stock", r"london joint stock"], origin="British", group=G_BRC,
         founder=None, founded=1836, community="English joint-stock bank", wwi_fate="—", confidence="medium", source="ledger"),
    dict(house="London & South Western Bank", patterns=[r"london & south western", r"lon s.western"], origin="British", group=G_BRC,
         founder=None, founded=1862, community="English clearing bank", wwi_fate="—", confidence="medium", source="ledger"),
    dict(house="Manchester & Liverpool District Bank", patterns=[r"manchester & liverpool"], origin="British", group=G_BRC, founder=None, founded=None,
         community="English provincial joint-stock bank", wwi_fate="—", confidence="low", source="ledger"),

    # ---- second pass: colonial / imperial & foreign banks ----
    dict(house="London & River Plate Bank", patterns=[r"river plate"], origin="British colonial (S. America)", group=G_COL, founder=None, founded=1862,
         community="Anglo-South-American bank", wwi_fate="—", confidence="medium", source="Jones"),
    dict(house="Anglo South American Bank", patterns=[r"anglo south american"], origin="British colonial (S. America)", group=G_COL, founder=None, founded=1888,
         community="Anglo-South-American bank", wwi_fate="—", confidence="medium", source="Jones"),
    dict(house="London & Brazilian Bank", patterns=[r"london & brazilian", r"london brazilian", r"brazilian bank"], origin="British colonial (Brazil)", group=G_COL,
         founder=None, founded=1862, community="Anglo-Brazilian bank", wwi_fate="—", confidence="medium", source="Jones"),
    dict(house="British Bank of South America", patterns=[r"bank of south america"], origin="British colonial (S. America)", group=G_COL, founder=None, founded=1863,
         community="Anglo-South-American bank", wwi_fate="—", confidence="low", source="Jones"),
    dict(house="Standard Bank of South Africa", patterns=[r"standard b(an)?k of s"], origin="British colonial (Africa)", group=G_COL, founder=None, founded=1862,
         community="Anglo-African bank", wwi_fate="Survived (Standard Bank)", confidence="medium", source="Jones"),
    dict(house="Bank of Africa", patterns=[r"bank of africa", r"natl bk of africa"], origin="British colonial (Africa)", group=G_COL, founder=None, founded=None,
         community="Anglo-African bank", wwi_fate="—", confidence="low", source="ledger"),
    dict(house="Eastern Bank", patterns=[r"eastern bank"], origin="British colonial (East)", group=G_COL, founder=None, founded=1909,
         community="Anglo-Eastern exchange bank", wwi_fate="—", confidence="low", source="Jones"),
    dict(house="Canadian Bank of Commerce", patterns=[r"canadian bank of commerce"], origin="British colonial (Canada)", group=G_COL, founder=None, founded=1867,
         community="Canadian bank", wwi_fate="Survived (CIBC)", confidence="medium", source="ledger"),
    dict(house="Bank of Montreal", patterns=[r"bank of montreal"], origin="British colonial (Canada)", group=G_COL, founder=None, founded=1817,
         community="Canadian bank", wwi_fate="Survived", confidence="medium", source="ledger"),
    dict(house="Union Bank of Australia", patterns=[r"union bank of australia"], origin="British colonial (Australia)", group=G_COL, founder=None, founded=1837,
         community="Australian bank", wwi_fate="Survived (ANZ)", confidence="medium", source="ledger"),
    dict(house="Yokohama Specie Bank", patterns=[r"yokohama"], origin="Japanese", group=G_FOR, founder=None, founded=1880,
         community="Japanese exchange bank — London branch (Allied)", wwi_fate="Allied", confidence="medium", source="ledger"),
]


def compile_register():
    rows = []
    for e in REGISTER:
        rx = re.compile("|".join(f"(?:{p})" for p in e["patterns"]), re.IGNORECASE)
        rows.append((rx, e))
    return rows


def match_house(name: str, compiled):
    """Return the first register entry whose pattern matches; None otherwise.
    Order in REGISTER encodes priority (specific houses listed before broad)."""
    if not isinstance(name, str):
        return None
    for rx, e in compiled:
        if rx.search(name):
            return e
    return None


def main():
    df = pd.read_parquet(DATA / "lolr_transactions.parquet")
    # unified transaction value
    df["value"] = df["total_amount"].fillna(df["value_discounted"]).fillna(df["amount_advanced_total"])

    compiled = compile_register()

    # ---- crosswalk: one row per distinct raw name ----
    names = sorted(df["counterparty_clean"].dropna().astype(str).unique())
    cw = []
    for nm in names:
        e = match_house(nm, compiled)
        cw.append(dict(
            counterparty_clean=nm,
            canonical_house=e["house"] if e else "(unclassified)",
            origin=e["origin"] if e else "",
            origin_group=e["group"] if e else "Unclassified (long tail)",
            confidence=e["confidence"] if e else "",
            matched=bool(e),
        ))
    crosswalk = pd.DataFrame(cw)
    crosswalk.to_csv(DATA / "house_crosswalk.csv", index=False)

    # ---- register table (one row per house) ----
    reg = pd.DataFrame([{k: v for k, v in e.items() if k != "patterns"} for e in REGISTER])
    reg = reg[["house", "origin", "group", "founder", "founded", "community", "wwi_fate", "confidence", "source"]]
    reg.to_csv(DATA / "origin_register.csv", index=False)

    # ---- tag the full ledger ----
    tagged = df.merge(crosswalk[["counterparty_clean", "canonical_house", "origin", "origin_group", "confidence"]],
                      on="counterparty_clean", how="left")
    tagged["origin_group"] = tagged["origin_group"].fillna("Unclassified (long tail)")
    tagged.to_parquet(DATA / "transactions_tagged.parquet")

    # ---- coverage report ----
    tot = df["value"].sum()
    matched_val = tagged.loc[tagged["canonical_house"] != "(unclassified)", "value"].sum()
    print(f"distinct raw names         : {len(names)}")
    print(f"register houses            : {len(REGISTER)}")
    print(f"raw names matched to a house: {crosswalk['matched'].sum()} ({100*crosswalk['matched'].mean():.0f}%)")
    print(f"transaction VALUE classified: £{matched_val:,.0f} / £{tot:,.0f} ({100*matched_val/tot:.0f}%)")
    print("\nvalue by origin_group:")
    vg = tagged.groupby("origin_group")["value"].sum().sort_values(ascending=False)
    for k, v in vg.items():
        print(f"  {k:42s} £{v:,.0f}  ({100*v/tot:.1f}%)")
    print("\nWrote: data/origin_register.csv, data/house_crosswalk.csv, data/transactions_tagged.parquet")


if __name__ == "__main__":
    main()
