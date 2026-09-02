"""
Module B - The Semantic Weighting & NLP Engine

Pure rule-based / regex heuristics (no external model downloads needed,
runs fully offline) covering:
  1. Entity Recognition  - IITK jargon (SURGE, CPI, AnC Council, etc.)
  2. Impact Detection     - does a bullet contain a quantifiable metric?
  3. Action Verb Strength - is the bullet's opening verb strong/medium/weak?
  4. PoR Recognition       - fuzzy-match "Positions of Responsibility" lines
                             against the institute-wide PoR rating catalogue.
"""
import re
from dataclasses import dataclass, field

from .data.iitk_entities import flatten_entities
from .data.action_verbs import classify_verb, WEAK_PHRASES
from .data.por_ratings import PoRCatalogue

# --- Impact detection -------------------------------------------------

METRIC_PATTERNS = [
    r"\d+(?:\.\d+)?\s*%",                                                    # 20%
    r"\d+(?:\.\d+)?\s*[xX]\b",                                               # 2x, 3.5x
    r"(?:₹|\$|Rs\.?|INR|USD|\|\s*)\s?\d+(?:\.\d+)?\s*(?:[kKmMbB]|lakh|crore|L\+|Cr\+|L|Cr)?\b",  # $50K, | 8L+, | 650Cr+
    r"\b\d+(?:\.\d+)?\s*[kK]\+?\b",                                          # 90k, 12k+, 5k+
    r"\b\d{1,3}(?:,\d{3})+\b",                                               # 10,000
    r"\b\d+\+?\s*(?:users|students|clients|requests|records|nodes|servers|teams|members|states|reform areas|profiles|startups|deliveries|indicators|features|days|lines|queries|models)\b",
    r"\b(?:0\.\d+|[1-9]\d*(?:\.\d+)?)\s*(?:acc|f1|accuracy|precision|recall|auc|roc|score|latency|ms|fps|gb|mb|tb)\b",
    r"\b(?:reduced|increased|improved|decreased|cut|boosted|grew)\b[^.]{0,40}?\d",
]
METRIC_RE = re.compile("|".join(METRIC_PATTERNS), re.IGNORECASE)


def has_quantifiable_metric(bullet: str) -> bool:
    return bool(METRIC_RE.search(bullet))


def weak_phrase_hits(bullet: str):
    hits = []
    low = bullet.lower()
    for pattern in WEAK_PHRASES:
        if re.search(pattern, low):
            hits.append(re.search(pattern, low).group(0))
    return hits


# --- Entity recognition -------------------------------------------------

_COMPILED_ENTITIES = [
    (category, canonical, [re.compile(p, re.IGNORECASE) for p in patterns])
    for category, canonical, patterns in flatten_entities()
]


def find_entities(text: str):
    """Returns list of {category, canonical, count} for all IITK entities found in text."""
    found = {}
    for category, canonical, compiled_patterns in _COMPILED_ENTITIES:
        count = 0
        for pat in compiled_patterns:
            count += len(pat.findall(text))
        if count > 0:
            found[canonical] = {"category": category, "count": count}
    return found


# --- Action verb analysis -------------------------------------------------

@dataclass
class BulletAnalysis:
    text: str
    opening_word: str = ""
    verb_strength: str = "unknown"
    has_metric: bool = False
    weak_phrases: list = field(default_factory=list)


def analyze_bullet(bullet: str) -> BulletAnalysis:
    words = bullet.strip().split()
    opening = words[0] if words else ""
    strength = classify_verb(opening) if opening else "unknown"
    return BulletAnalysis(
        text=bullet,
        opening_word=opening,
        verb_strength=strength,
        has_metric=has_quantifiable_metric(bullet),
        weak_phrases=weak_phrase_hits(bullet),
    )


def analyze_bullets(bullets):
    return [analyze_bullet(b) for b in bullets]


# --- Keyword relevance (per-track) -------------------------------------------------

def _keyword_present(kw: str, low_text: str) -> bool:
    """
    Short/ambiguous keywords are matched on word boundaries to avoid false
    positives (e.g. bare substring 'cad' matches inside 'aCADemic', 'r' inside
    every word). Multi-word or clearly-technical keywords keep fast substring
    matching. Keywords containing regex-significant chars (c++, r&d) are
    escaped and boundary-checked on their alphanumeric edges only.
    """
    if len(kw) <= 4 and kw.replace("+", "").replace("#", "").isalnum():
        # \b doesn't work after '+'/'#', but these short alnum keywords are the
        # risky-substring ones; require boundaries on both sides.
        return re.search(rf"\b{re.escape(kw)}\b", low_text) is not None
    return kw in low_text


def keyword_relevance_score(text: str, keyword_weights: dict, target_coverage: float = 0.25):
    """
    Returns (norm_score, matched_keywords) where norm_score in [0, 1] is the
    matched weight as a fraction of `target_coverage` * total pool weight.

    Calibration note: `target_coverage` was originally a flat 0.55, but real
    placed resumes match only ~0.11 (median) to ~0.21 (p75) of a track's
    weighted keyword pool — nobody lists 55% of a 25-keyword pool. That made
    the projects/coursework components structurally unreachable (placed SDE
    median projects sub-score was ~10/100). Callers now pass a per-track
    target near that track's placed p75 so a strong, realistic resume can
    approach full marks. Default 0.25 is a sensible mid value.
    """
    low = text.lower()
    matched = {}
    total = 0.0
    for kw, weight in keyword_weights.items():
        if _keyword_present(kw, low):
            matched[kw] = weight
            total += weight

    max_possible = sum(keyword_weights.values())
    target = max_possible * target_coverage
    norm = min(1.0, total / target) if target > 0 else 0.0
    return norm, matched


# --- PoR matching -------------------------------------------------

_POR_CATALOGUE = None


def get_por_catalogue():
    global _POR_CATALOGUE
    if _POR_CATALOGUE is None:
        _POR_CATALOGUE = PoRCatalogue()
    return _POR_CATALOGUE


def match_por_lines(por_section_lines):
    catalogue = get_por_catalogue()
    matches = []
    for line in por_section_lines:
        m = catalogue.match(line)
        matches.append({"line": line, "match": m})
    return matches
