# IITK Context-Aware Resume Diagnostic Engine

Built for the Career Development Wing, Academics and Career Council, IIT Kanpur.

An automated, role-aware resume advisor for IITK students. Upload an SPO-formatted
PDF resume, pick a target track (SDE / Quant Finance / Management Consulting / Core
Engineering), and get a **Profile Match Score /100** plus specific, line-by-line
feedback — the kind a knowledgeable senior would give, minus the wait and the
inconsistency.

## Why this exists

Every placement season, IITK students compress three years of work into a single
dense SPO LaTeX template, then rely on scattered senior advice to know whether
their resume actually fits their target industry. This tool automates that gap
check.

## Architecture

```
resume_engine/
├── app.py                     # Module C — Streamlit Advisory Dashboard
├── engine/
│   ├── pdf_parser.py          # Module A — LaTeX-PDF Parsing Engine
│   ├── nlp_engine.py          # Module B — Semantic Weighting & NLP Engine
│   ├── scoring.py             # Combines A + B against Role Baselines
│   └── data/
│       ├── iitk_entities.py   # IITK jargon list (SURGE, CPI, AnC Council, ...)
│       ├── action_verbs.py    # Strong / medium / weak verb classification
│       ├── role_baselines.py  # Section-3 evaluation baselines (4 tracks)
│       └── por_ratings.py     # Fuzzy-matcher over the 92-entry PoR catalogue
├── data/
│   └── por_ratings.csv        # Exported from IITK_PoR_Ratings.xlsx
├── tests/
│   ├── test_engine.py         # 26 automated tests (pytest)
│   └── mock_resumes/          # Synthetic SPO-style test fixtures + .html sources
└── requirements.txt
```

### Module A — The LaTeX-PDF Parsing Engine (`engine/pdf_parser.py`)

Naive PDF text extraction reads the raw content stream, which scrambles
multi-column resumes: text from the left and right column at the same
vertical height gets interleaved mid-sentence. This module instead:

1. Extracts every word with its bounding box via `pdfplumber`.
2. Builds an x-axis coverage histogram to find a vertical whitespace "gutter"
   — the empty band between columns — and splits the page into column
   bounding boxes at that gutter. Falls back to a single column if no
   consistent gap is found (handles both true 2-column SPO layouts and
   single-column resumes).
3. Within each column, groups words into lines by `top`-coordinate proximity,
   sorts lines top-to-bottom, and sorts words within a line left-to-right.
4. Reassembles the full document by concatenating columns left-to-right —
   i.e., the entire left column finishes before the right column starts.
5. Classifies headings (Education, Experience, Projects, Positions of
   Responsibility, Achievements, Coursework, Skills, Publications) via an
   alias dictionary + heading heuristics (short line, high uppercase ratio).
6. Extracts every embedded hyperlink via `page.hyperlinks` (PDF annotations)
   and tags which nearby text it's attached to — critically, this
   distinguishes a real clickable GitHub link from someone typing
   `github.com/username` as plain text (the latter is *not* credited).
7. Extracts CPI/CGPA via regex.
8. Extracts bullet points primarily via bullet-glyph detection
   (`•`, `-`, `*`, etc. — how LaTeX `\item` renders in the content stream).
   **Fallback:** if no bullet glyphs are found anywhere in the document
   (some non-LaTeX PDF exporters don't emit them as extractable text), a
   sentence heuristic treats long, sentence-like lines in bullet-eligible
   sections as bullets, so verb/impact analysis still runs.

### Hybrid mode (rules for scoring, LLM for feedback text)

The engine runs **fully offline and rule-based by default**. An optional
**hybrid** mode adds an LLM layer (`engine/llm_feedback.py`) that enriches only
the *feedback text* — it never computes or alters the numeric score, which
stays 100% deterministic:

- **Bullet rewrites**: turns a flagged bullet + its mechanical issues into a
  concrete suggested rewrite ("Engineered checkout-service test coverage,
  cutting escaped defects by [X]%" instead of "add a metric").
- **Mentor summary**: a short narrative grounded strictly in the rule-based
  strengths/gaps already found.


### Module B — The Semantic Weighting & NLP Engine (`engine/nlp_engine.py`)

Deliberately **rule-based / regex**, not a downloaded ML model — fully
offline, fully deterministic, and easy for a grader to audit line-by-line
(the brief explicitly said "keyword matching is insufficient," not "you must
use a neural model"; a curated, IITK-specific rule set is more precise here
than a generic NLP library that's never heard of "SURGE" or "AnC Council").

- **Entity Recognition** — a categorized dictionary (`iitk_entities.py`) of
  IITK-specific jargon (SURGE, GSoC, AnC Council, SPO, Antaragni, Techkriti,
  Codeforces, Inter IIT, etc.), matched via compiled regex.
- **Impact Detection** — regex family covering `%`, multipliers (`2x`),
  currency (`$50K`, `₹2 lakh`), large comma-grouped numbers, and
  "reduced/increased/improved ... <number>" patterns.
- **Action Verb Strength** — the first word of every bullet is classified
  strong / medium / weak against curated verb lists, plus a separate
  regex pass for weak passive phrases ("responsible for", "worked on",
  "helped with").
- **PoR Matching** — every line in the Positions of Responsibility section
  is fuzzy-matched against the 92-entry `IITK_PoR_Ratings.xlsx` catalogue
  using a **symmetric Jaccard token-overlap** score (not naive substring or
  one-directional overlap — an earlier version of this scored the generic
  "Council Secretary" above the correct, more specific "General Secretary
  (any Council)" simply because the generic entry had fewer tokens; fixed
  by normalizing against the union of both token sets, plus stopword
  removal and a verbatim-substring bonus).

### Scoring (`engine/scoring.py`)

Each track (`role_baselines.py`) defines its own component weights (summing
to 100), keyword pools, coursework pools, CPI thresholds, PoR weight
multiplier, and penalty rules — directly from PS Section 3. The same parsed
resume is scored independently per track, so switching tracks produces a
materially different score and different flagged gaps (verified in
`test_score_shifts_dynamically_across_tracks_for_same_resume`).

Output: overall Profile Match Score, per-component sub-scores, Top 3
Strengths, Critical Missing Elements (weak components + triggered
penalties), and per-bullet Line-by-Line Formatting Fixes.

### Module C — The Advisory Dashboard (`app.py`)

Streamlit app: upload PDF → pick track → **Run Diagnostic** → see the score,
component breakdown, parsing diagnostics (columns detected? CPI found?
hyperlinks found?), strengths, gaps, bullet-level fixes, matched PoRs, and
recognized IITK entities.

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

## Changelog

**v1.1** — Fixed against two real IITK resumes (table-based Academic
Qualifications block, "Objective/Approach/Results" structured project
bullets, headings outside the original alias list):
- Word-gluing fix: `x_tolerance=1.5` on `extract_words` (default 3 merges
  tightly-kerned justified text into one run, e.g. turning "Received Academic
  Excellence Award" into a single unbroken token).
- Section detection now combines the alias dictionary with a **font-signal
  fallback** — pdfplumber exposes each word's font size, so a short line
  rendered visibly larger than the resume's modal body-text size is
  recognized as a heading even when its exact wording ("Research Project",
  "Key Projects", "Work Experience", "Academic Qualifications") isn't in the
  dictionary. (A same-size-but-bold-only signal was tried and reverted — it
  false-positived on bolded project/company sub-titles, e.g. "Personal
  Portfolio Website", fragmenting Projects into one section per entry.)
- CPI extraction is now **table-aware**: it locates the Education row
  containing "B.Tech"/"BTech" and reads the `X.XX/10` figure from that row
  specifically, instead of requiring the literal word "CPI" to sit next to
  the number (which fails when CPI is a table column header, not inline text).
- Bullet extraction now handles the "`Objective • text`" / "`Approach •
  text`" / "`Results • text`" sub-labeled structure common in IITK project
  write-ups — the label is stripped and the remainder becomes the bullet; a
  bare label line with no content on it (common when the bullet wraps to the
  next line) is dropped rather than misread as a heading or an empty bullet.
- Cosmetic: strips glyph-level spacing artifacts (`"results , showing"` →
  `"results, showing"`, `"10 th"` → `"10th"`, `"R ²"` → `"R²"`).
- The first heading-like line on the page (almost always the candidate's own
  name, rendered in the largest font) is never treated as a section boundary.

## Testing

```bash
pip install pytest
pytest tests/test_engine.py -v
```

34 tests cover: section/CPI/hyperlink extraction, column-reading-order
correctness, bullet extraction (including the fallback path and the
Objective/Approach/Results label-stripping path), entity recognition,
impact/weak-verb flagging, PoR-matching accuracy (including a regression
test for the generic-vs-specific matching bug found during development),
per-track score bounds/sensitivity, and 8 regression tests against two real
(anonymized) IITK resumes in `tests/mock_resumes/real_*.pdf`.

To regenerate a mock resume fixture after editing its `.html` source:

```bash
wkhtmltopdf --enable-local-file-access tests/mock_resumes/mock_sde.html tests/mock_resumes/mock_sde.pdf
```

## Known limitations (honest, for the ATR)

- Column detection uses a single global vertical gutter per page; a resume
  with an irregular grid (e.g. columns that shift width partway down the
  page) would need a per-row column detector.
- PoR fuzzy-matching is intentionally generous (threshold 0.38) to catch
  loosely-phrased titles; council-specific titles not close to any catalogue
  entry (e.g. a vertical name the catalogue doesn't enumerate) can still miss.
- Bullet-glyph fallback heuristic is a best-effort sentence detector, not a
  layout-aware list detector — very short bullets (<5 words) can be missed.
- Impact-detection regex will not catch impact phrased without a number at
  all (e.g. "significantly improved") — which is arguably correct behavior,
  since that's exactly the kind of unquantified claim the engine should flag.