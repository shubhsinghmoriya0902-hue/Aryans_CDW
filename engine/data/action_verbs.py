"""
Action verb strength classification used to score the first word of each
resume bullet point (Module B - Action Verb evaluation).
"""

# High-impact, quantifiable-outcome verbs (top tier)
STRONG_VERBS = {
    "engineered", "architected", "spearheaded", "optimized", "automated",
    "accelerated", "reduced", "increased", "boosted", "scaled", "launched",
    "built", "designed", "developed", "implemented", "deployed", "shipped",
    "led", "drove", "delivered", "achieved", "improved", "streamlined",
    "eliminated", "generated", "negotiated", "orchestrated", "pioneered",
    "restructured", "transformed", "cut", "grew", "won", "secured",
    "quantified", "benchmarked", "refactored", "integrated", "migrated",
    "mentored", "guided", "tutored", "advised", "coached",
}

# Acceptable but generic verbs (mid tier) - not penalized but not rewarded
MEDIUM_VERBS = {
    "created", "managed", "coordinated", "organized", "conducted",
    "analyzed", "researched", "presented", "trained",
    "collaborated", "wrote", "tested", "debugged", "maintained",
    "supervised", "planned", "executed", "reviewed", "supported",
}

# Weak / passive verbs that recruiters and seniors flag as low-signal
WEAK_VERBS = {
    "worked", "helped", "assisted", "responsible", "involved", "handled",
    "participated", "contributed", "did", "tasked", "used", "utilized",
    "learned", "gained", "familiarized", "exposed", "attended", "dealt",
}

WEAK_PHRASES = [
    r"\bresponsible for\b",
    r"\bworked on\b",
    r"\bworked with\b",
    r"\bhelped (?:with|to)?\b",
    r"\btasked with\b",
    r"\bwas involved in\b",
    r"\bassisted (?:with|in)?\b",
    r"\bgot exposure to\b",
]


def classify_verb(word: str) -> str:
    w = word.lower().strip(".,;:")
    if w in STRONG_VERBS:
        return "strong"
    if w in MEDIUM_VERBS:
        return "medium"
    if w in WEAK_VERBS:
        return "weak"
    return "unknown"
