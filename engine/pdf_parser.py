"""
Module A - The LaTeX-PDF Parsing Engine

Standard `pdf.extract_text()` calls scramble multi-column LaTeX resumes
because they walk the raw content stream, not visual reading order. This
module clusters words into columns by x-position, sorts each column
top-to-bottom, and reassembles clean, section-aware, reading-order text.
It also pulls every embedded hyperlink (GitHub, LinkedIn, portfolio, etc.)
and tags which resume line each link is attached to.

Section headings are detected two ways, combined:
  1. An alias dictionary of known IITK/SPO resume heading phrasings.
  2. A font-signal fallback: pdfplumber exposes each word's font size and
     name, so a short line rendered visibly larger/bolder than the resume's
     modal body-text size is recognized as a heading even if its exact
     wording isn't in the alias dictionary (handles resumes that use
     "Research Project", "Key Projects", "Work Experience", etc.).
"""
import re
from collections import Counter
from dataclasses import dataclass, field

import pdfplumber

# Section headers commonly used in IITK / SPO-style resumes. Keys are
# normalized (lowercase, punctuation-stripped, collapsed whitespace).
SECTION_ALIASES = {
    "education": "Education",
    "academic qualifications": "Education",
    "academic qualification": "Education",
    "educational qualifications": "Education",
    "experience": "Experience",
    "work experience": "Experience",
    "internship": "Experience",
    "internships": "Experience",
    "internship experience": "Experience",
    "professional experience": "Experience",
    "projects": "Projects",
    "academic projects": "Projects",
    "key projects": "Projects",
    "personal projects": "Projects",
    "research project": "Projects",
    "research projects": "Projects",
    "research experience": "Projects",
    "positions of responsibility": "Positions of Responsibility",
    "position of responsibility": "Positions of Responsibility",
    "por": "Positions of Responsibility",
    "leadership experience": "Positions of Responsibility",
    "achievements": "Achievements",
    "awards": "Achievements",
    "awards and achievements": "Achievements",
    "scholastic achievements": "Achievements",
    "achievements and awards": "Achievements",
    "honors and awards": "Achievements",
    "skills": "Skills",
    "technical skills": "Skills",
    "skills summary": "Skills",
    "skills and interests": "Skills",
    "extracurricular": "Extracurricular",
    "extracurriculars": "Extracurricular",
    "extra curricular": "Extracurricular",
    "extra curriculars": "Extracurricular",
    "extra-curricular": "Extracurricular",
    "extra-curriculars": "Extracurricular",
    "extra-curricular activities": "Extracurricular",
    "extra-curricular activity": "Extracurricular",
    "co-curricular activities": "Extracurricular",
    "coursework": "Coursework",
    "relevant coursework": "Coursework",
    "relevant courses": "Coursework",
    "key courses": "Coursework",
    "course work": "Coursework",
    "publications": "Publications",
}

# Sub-labels used inside a project/PoR entry's structured bullets
# (e.g. "Objective • ...", "Approach • ...", "Results • ..."). These must
# NEVER be treated as new section headings, and are stripped from the
# front of a bullet when they prefix one on the same line.
KNOWN_SUBLABELS = {
    "objective", "approach", "result", "results", "impact", "leadership",
    "initiative", "cultural", "social work", "and", "outcome", "methodology",
}

CPI_RE = re.compile(r"(?:CPI|CGPA)\s*[:\-]?\s*(\d{1,2}(?:\.\d{1,2})?)", re.IGNORECASE)
TABLE_CPI_RE = re.compile(r"(\d{1,2}\.\d{1,2})\s*/\s*10(?:\.0)?\b")
DEGREE_ROW_RE = re.compile(r"\bB\.?\s?TECH\b", re.IGNORECASE)

BULLET_CHARS = r"•\-\u2022\u25CF\u25AA\*o\u2023\u2043"
BULLET_START_RE = re.compile(rf"^[{BULLET_CHARS}]\s*")
LABEL_PREFIX_RE = re.compile(
    r"^(Objective|Approach|Results?|Impact|Leadership|Initiative|Cultural|Social\s+Work|"
    r"Outcome|Methodology)\s*[" + BULLET_CHARS + r"]?\s*",
    re.IGNORECASE,
)

TRAILING_ANNOTATION_RE = re.compile(r"\s*[\(\u2020].*$")  # strip "(*Ongoing)", "†: Online Course", etc.

# Cleans up spacing artifacts from glyph-level PDF extraction: a space
# inserted before punctuation ("results , showing"), before an ordinal
# suffix ("10 th"), or around a superscript-rendered character ("R ²").
_SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([,.;:%)])")
_ORDINAL_SPACING_RE = re.compile(r"(\d)\s+(st|nd|rd|th)\b", re.IGNORECASE)
_SUPERSCRIPT_SPACING_RE = re.compile(r"\s+([²³¹])")


def _clean_line_spacing(text: str) -> str:
    text = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", text)
    text = _ORDINAL_SPACING_RE.sub(r"\1\2", text)
    text = _SUPERSCRIPT_SPACING_RE.sub(r"\1", text)
    return text


@dataclass
class ParsedResume:
    raw_text: str = ""
    sections: dict = field(default_factory=dict)   # section_name -> list of lines
    bullets: dict = field(default_factory=dict)     # section_name -> list of bullet strings
    hyperlinks: list = field(default_factory=list)  # list of {"text_hint", "url", "page"}
    cpi: float = None
    column_layout_detected: bool = False
    warnings: list = field(default_factory=list)


def _cluster_columns(words, page_width, gap_ratio_threshold=0.04):
    """
    Given pdfplumber `words` (list of dicts with x0, x1, top, bottom, text),
    detect a vertical whitespace gap that splits the page into columns, and
    return a list of column bounding boxes [(x_min, x_max), ...] left-to-right.

    Falls back to a single column if no consistent gap is found.
    """
    if not words:
        return [(0, page_width)]

    resolution = 200
    bin_width = page_width / resolution
    coverage = [0] * resolution
    for w in words:
        start_bin = max(0, int(w["x0"] / bin_width))
        end_bin = min(resolution - 1, int(w["x1"] / bin_width))
        for b in range(start_bin, end_bin + 1):
            coverage[b] += 1

    # Search for the widest contiguous zero-coverage band in the central band of the page.
    # Widened beyond the middle third to also catch off-center sidebar layouts (e.g. a
    # 33/67 split), which are common in SPO-style resumes with a narrow left column.
    mid_lo, mid_hi = int(resolution * 0.15), int(resolution * 0.85)
    best_gap = None
    run_start = None
    for i in range(mid_lo, mid_hi + 1):
        if coverage[i] == 0:
            if run_start is None:
                run_start = i
        else:
            if run_start is not None:
                run_len = i - run_start
                if best_gap is None or run_len > (best_gap[1] - best_gap[0]):
                    best_gap = (run_start, i)
                run_start = None
    if run_start is not None:
        run_len = mid_hi - run_start
        if best_gap is None or run_len > (best_gap[1] - best_gap[0]):
            best_gap = (run_start, mid_hi)

    if best_gap and (best_gap[1] - best_gap[0]) * bin_width >= page_width * gap_ratio_threshold:
        gutter_x = ((best_gap[0] + best_gap[1]) / 2) * bin_width
        return [(0, gutter_x), (gutter_x, page_width)]

    return [(0, page_width)]


def _words_to_lines(words, line_tolerance=3.0):
    """
    Group words (already restricted to one column) into visual lines by `top`,
    sort left-to-right, and return (text, avg_font_size, is_bold) tuples so
    the caller can do font-signal heading detection.
    """
    if not words:
        return []
    words = sorted(words, key=lambda w: (round(w["top"] / line_tolerance), w["x0"]))
    lines = []
    current_line = []
    current_top = None
    for w in words:
        if current_top is None or abs(w["top"] - current_top) <= line_tolerance:
            current_line.append(w)
            current_top = w["top"] if current_top is None else current_top
        else:
            lines.append(current_line)
            current_line = [w]
            current_top = w["top"]
    if current_line:
        lines.append(current_line)

    text_lines = []
    for line in lines:
        line_sorted = sorted(line, key=lambda w: w["x0"])
        text = " ".join(w["text"] for w in line_sorted)
        top = min(w["top"] for w in line_sorted)
        sizes = [w.get("size") for w in line_sorted if w.get("size")]
        avg_size = sum(sizes) / len(sizes) if sizes else 0.0
        bold_count = sum(1 for w in line_sorted if "bold" in (w.get("fontname") or "").lower())
        is_bold = bold_count >= max(1, len(line_sorted) // 2)
        text_lines.append((top, text, avg_size, is_bold))
    text_lines.sort(key=lambda t: t[0])
    return [(_clean_line_spacing(t[1]), t[2], t[3]) for t in text_lines]


def _normalize_heading_key(line: str) -> str:
    key = line.strip().lower()
    key = TRAILING_ANNOTATION_RE.sub("", key)  # drop "(*Ongoing)" / "†: Online Course" etc.
    key = key.strip().rstrip(":").strip()
    key = re.sub(r"\s+", " ", key)
    return key


def _classify_section(line: str):
    return SECTION_ALIASES.get(_normalize_heading_key(line))


def _clean_heading_text(line: str) -> str:
    """Turn a detected-but-unaliased heading line into a display-friendly section name."""
    cleaned = TRAILING_ANNOTATION_RE.sub("", line.strip()).strip().rstrip(":").strip()
    return re.sub(r"\s+", " ", cleaned).title()


def _is_known_sublabel(line: str) -> bool:
    return _normalize_heading_key(line) in KNOWN_SUBLABELS


_FOOTER_RE = re.compile(
    r"(curriculum vitae|résumé|\bresume\b|\bpage\b|\bcv\b)\s*\d*\s*$", re.IGNORECASE)


def _looks_like_heading(line: str, avg_size: float = 0.0, is_bold: bool = False,
                         body_size: float = 0.0) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > 45:
        return False
    if _is_known_sublabel(stripped):
        return False
    # Page footers / running headers ("Shrey Mehta · Curriculum Vitae 1")
    # are not section headings.
    if _FOOTER_RE.search(stripped):
        return False
    # A line containing a date/tenure is an entry title (e.g. "Software
    # Associate Intern May '23 - Jul '23"), not a section heading.
    if re.search(r"\b(19|20)\d{2}\b", stripped) or \
       re.search(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)['’]?\s?\d{2}", stripped):
        return False
    if BULLET_START_RE.match(stripped) or LABEL_PREFIX_RE.match(stripped):
        return False

    # Signal 1: known alias.
    if _classify_section(stripped) is not None:
        return True

    # Signal 2: strong uppercase ratio (classic "PROJECTS" style headers).
    letters = [c for c in stripped if c.isalpha()]
    if letters:
        upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        if upper_ratio > 0.7:
            return True

    # Signal 3: font-size stands out from the body text. Requires a short,
    # title-like line (few words) to avoid misfiring on bolded phrases inside
    # a bullet (e.g. a bolded metric). Deliberately NOT triggered by boldness
    # alone at body-text size — many resumes bold sub-entry titles (project
    # names, company names) at the same size as body text, and treating every
    # short bold phrase as a new top-level section fragments Projects/
    # Experience into one section per entry.
    word_count = len(stripped.split())
    if body_size > 0 and word_count <= 6 and avg_size >= body_size * 1.08:
        return True

    return False


def _extract_cpi(sections: dict, raw_text: str):
    """
    Prefer a table-aware extraction: find the Education row for the current
    B.Tech/BTech degree (contains the degree keyword) and pull the "X.XX/10"
    figure from that specific row, so we don't accidentally grab a XII/X
    board percentage instead.
    """
    edu_lines = sections.get("Education", [])
    for line in edu_lines:
        if DEGREE_ROW_RE.search(line):
            m = TABLE_CPI_RE.search(line)
            if m:
                try:
                    return float(m.group(1))
                except ValueError:
                    pass
    # Fallback: any "X.XX/10" pattern anywhere in Education section.
    for line in edu_lines:
        m = TABLE_CPI_RE.search(line)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                pass
    # Last resort: the original "CPI: 8.7" adjacency pattern anywhere in the doc.
    m = CPI_RE.search(raw_text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return None


def parse_resume(pdf_path: str) -> ParsedResume:
    result = ParsedResume()
    all_lines = []       # list of (text, avg_size, is_bold)
    all_word_sizes = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            # x_tolerance=1.5 avoids gluing adjacent words together in tightly
            # kerned / justified PDF text (the default tolerance of 3 merges
            # e.g. "Received Academic Excellence Award" into one word on some
            # LaTeX resume templates).
            words = page.extract_words(
                use_text_flow=False, keep_blank_chars=False,
                x_tolerance=1.5, extra_attrs=["size", "fontname"],
            )
            all_word_sizes.extend(w.get("size") for w in words if w.get("size"))

            columns = _cluster_columns(words, page.width)
            if len(columns) > 1:
                result.column_layout_detected = True

            for (x_min, x_max) in columns:
                col_words = [w for w in words if x_min <= (w["x0"] + w["x1"]) / 2 < x_max]
                lines = _words_to_lines(col_words)
                all_lines.extend(lines)

            # Hyperlinks: pdfplumber exposes them via page.hyperlinks (annotations)
            for link in getattr(page, "hyperlinks", []):
                uri = link.get("uri")
                if not uri:
                    continue
                x0, top, x1, bottom = link.get("x0", 0), link.get("top", 0), link.get("x1", 0), link.get("bottom", 0)
                nearby = [w["text"] for w in words
                          if w["x0"] >= x0 - 2 and w["x1"] <= x1 + 2
                          and w["top"] >= top - 2 and w["bottom"] <= bottom + 2]
                result.hyperlinks.append({
                    "url": uri,
                    "text_hint": " ".join(nearby) if nearby else None,
                    "page": page_num + 1,
                })

    result.raw_text = "\n".join(t for t, _, _ in all_lines)

    # Body font size = the modal (most common) word size across the document.
    # Rounded to 1 decimal so tiny rendering jitter doesn't split the mode.
    body_size = 0.0
    if all_word_sizes:
        rounded = [round(s, 1) for s in all_word_sizes]
        body_size = Counter(rounded).most_common(1)[0][0]

    # --- Segment into sections ---
    # The very first heading-like line on the page is almost always the resume
    # owner's name (rendered in the largest font on the page), not a section
    # title — never start a new section from it, keep it under "Header".
    current_section = "Header"
    result.sections[current_section] = []
    for idx, (text, avg_size, is_bold) in enumerate(all_lines):
        if idx == 0:
            result.sections[current_section].append(text)
            continue
        if _looks_like_heading(text, avg_size, is_bold, body_size):
            alias = _classify_section(text)
            current_section = alias if alias else _clean_heading_text(text)
            result.sections.setdefault(current_section, [])
            continue
        result.sections.setdefault(current_section, []).append(text)

    result.cpi = _extract_cpi(result.sections, result.raw_text)

    # --- Extract bullet points per section ---
    # Primary signal: an explicit bullet glyph at line start (how LaTeX \item
    # renders in the PDF content stream). Some structured entries prefix a
    # sub-label before the bullet on the same line ("Objective • ...") —
    # that label is stripped, not treated as heading or lost.
    BULLET_ELIGIBLE_SECTIONS = {"Experience", "Projects", "Achievements",
                                 "Positions of Responsibility", "Extracurricular", "Publications"}
    marker_found_anywhere = any(
        BULLET_START_RE.match(line.strip()) or LABEL_PREFIX_RE.match(line.strip())
        for lines in result.sections.values() for line in lines
    )
    for section, lines in result.sections.items():
        bullets = []
        for line in lines:
            stripped = line.strip()
            if _is_known_sublabel(stripped):
                continue  # bare "Approach" / "Results" label with no content on this line
            if BULLET_START_RE.match(stripped):
                bullets.append(BULLET_START_RE.sub("", stripped))
                continue
            label_match = LABEL_PREFIX_RE.match(stripped)
            if label_match:
                remainder = stripped[label_match.end():].strip()
                if len(remainder.split()) >= 3:
                    bullets.append(remainder)
                continue
        if not bullets and not marker_found_anywhere and section in BULLET_ELIGIBLE_SECTIONS:
            # Fallback heuristic: some PDF exporters don't emit bullet glyphs as
            # extractable text at all. Treat sentence-like lines as bullets so
            # downstream verb/impact analysis still runs.
            for line in lines:
                words_in_line = line.strip().split()
                if len(words_in_line) < 5:
                    continue
                if _looks_like_heading(line, body_size=body_size):
                    continue
                if line.count(",") <= 1 and not line.rstrip().endswith(".") and len(words_in_line) < 8:
                    continue
                bullets.append(line.strip())
        result.bullets[section] = bullets

    if not result.column_layout_detected:
        result.warnings.append(
            "Single-column layout detected (or column-splitting failed) — "
            "verify reading order manually for this resume."
        )
    if "Positions of Responsibility" not in result.sections:
        result.warnings.append("No 'Positions of Responsibility' section detected.")
    if result.cpi is None:
        result.warnings.append("Could not extract CPI/CGPA from the document.")
    if not result.hyperlinks:
        result.warnings.append("No hyperlinks found in the PDF (GitHub/LinkedIn/portfolio may be missing or as plain text).")

    return result
