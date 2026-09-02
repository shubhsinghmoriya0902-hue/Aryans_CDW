"""
Loads the IITK_PoR_Ratings.xlsx-derived CSV into memory and exposes a
fuzzy-matching lookup used to score Positions of Responsibility (PoRs)
found on a resume against the institute-wide 92-entry rating catalogue.
"""
import csv
import os
import re
from difflib import SequenceMatcher

_DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "por_ratings.csv",
)


_STOPWORDS = {"any", "of", "the", "and", "a", "an", "in", "for", "to", "by", "at"}


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _tokens(norm_text: str):
    return {t for t in norm_text.split() if t not in _STOPWORDS}


class PoRCatalogue:
    def __init__(self, csv_path: str = _DATA_PATH):
        self.entries = []
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if not row.get("Position of Responsibility"):
                    continue
                self.entries.append({
                    "council": row["Council / Body"],
                    "por": row["Position of Responsibility"],
                    "tier": row["Tier"],
                    "selection_mode": row.get("Selection Mode", "Appointed"),
                    "rating": float(row["Rating (1-10)"]),
                    "norm": _normalize(row["Position of Responsibility"]),
                })

    def match(self, candidate_line: str, threshold: float = 0.38):
        """
        Fuzzy-match a line of resume text against the PoR catalogue.
        Returns the best-matching entry dict (with a 'score' key) or None.
        """
        # PoR title lines usually carry a trailing date/tenure and sometimes a
        # body after a '|' separator ("Manager, Design | Core Team E-Cell
        # Aug'22 - Apr'23"). Keep only the part before '|' and strip trailing
        # month/year tenure so it doesn't dilute token overlap with the catalogue.
        candidate = candidate_line.split("|")[0]
        candidate = re.sub(
            r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*"
            r"[\s'’]*\d{2,4}.*$", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"\b(19|20)\d{2}\b.*$", "", candidate)
        candidate = re.sub(r"\(.*?\)", "", candidate)

        norm_line = _normalize(candidate)
        if len(norm_line) < 4:
            norm_line = _normalize(candidate_line)  # fall back to full line
        if len(norm_line) < 4:
            return None

        line_tokens = _tokens(norm_line)
        best = None
        best_score = 0.0
        for entry in self.entries:
            entry_tokens = _tokens(entry["norm"])
            if not entry_tokens or not line_tokens:
                continue

            # Symmetric Jaccard overlap so short entries ("Council Secretary")
            # don't automatically outscore longer, more specific ones
            # ("General Secretary (any Council)") just by having fewer tokens.
            union = entry_tokens | line_tokens
            jaccard = len(entry_tokens & line_tokens) / len(union) if union else 0.0

            # Sequence similarity catches near-exact phrasing even with reordering noise.
            seq_ratio = SequenceMatcher(None, entry["norm"], norm_line).ratio()

            # Small boost if the full entry title appears verbatim as a substring.
            substring_bonus = 0.15 if entry["norm"] in norm_line else 0.0

            score = max(jaccard, seq_ratio * 0.8) + substring_bonus
            if score > best_score:
                best_score = score
                best = entry

        if best and best_score >= threshold:
            result = dict(best)
            result["score"] = round(best_score, 2)
            return result
        return None

    def match_all(self, lines, threshold: float = 0.38):
        """Match each line in a list; returns list of (line, match_or_None)."""
        return [(line, self.match(line, threshold)) for line in lines]
