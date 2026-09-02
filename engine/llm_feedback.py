"""
Module B (hybrid) - LLM feedback layer.

Design contract: **the LLM never computes or alters the score.** All numbers,
weights, penalties and calibration remain 100% deterministic rule-based output
(engine/scoring.py). This layer only *rewrites the feedback text* into more
specific, actionable, senior-mentor-style advice:

  1. bullet rewrites  - turn a flagged bullet + its mechanical issues into a
                        concrete suggested rewrite ("Quantify the user base
                        growth in Project 2" rather than "add a metric").
  2. narrative summary - a short paragraph a human senior would write, grounded
                        strictly in the rule-based strengths/gaps already found.

If no API key is configured, or the call errors, every function degrades
gracefully to the original rule-based strings — so the app still runs fully
offline, exactly as before. The hybrid is opt-in via the RESUME_ENGINE_USE_LLM
environment variable (or the app's toggle), not on by default.

The API call uses the Anthropic Messages endpoint. The model is instructed to
return strict JSON, which we parse defensively.
"""
import json
import os
import re

# The model used for feedback enrichment. Small/fast is fine here — this is a
# text-rewriting task, not the scoring itself.
_MODEL = os.environ.get("RESUME_ENGINE_LLM_MODEL", "claude-sonnet-4-6")
_MAX_BULLETS = 12  # cap how many bullets we send, to keep latency/cost bounded


def llm_enabled() -> bool:
    """Hybrid mode is on only when explicitly enabled AND a key is present."""
    flag = os.environ.get("RESUME_ENGINE_USE_LLM", "").strip().lower()
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
    return flag in ("1", "true", "yes", "on") and has_key


def _get_client():
    """Lazily import the SDK so the package has no hard dependency on it."""
    try:
        from anthropic import Anthropic
    except ImportError:
        return None
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return None
    try:
        return Anthropic(api_key=key)
    except Exception:
        return None


def _extract_json(text: str):
    """Pull the first JSON object/array out of a model response, tolerating
    stray prose or ```json fences. Checks whichever of '['/'{' appears FIRST
    in the text, so an array of objects isn't mis-parsed as its first element."""
    cleaned = re.sub(r"```(?:json)?", "", text).strip()

    # Try direct parse first (well-behaved responses).
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Otherwise, bracket-match starting from whichever delimiter comes first.
    candidates = []
    for opener, closer in (("[", "]"), ("{", "}")):
        start = cleaned.find(opener)
        if start != -1:
            candidates.append((start, opener, closer))
    candidates.sort()  # earliest delimiter in the text wins
    for start, opener, closer in candidates:
        end = cleaned.rfind(closer)
        if end > start:
            try:
                return json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError:
                continue
    return None


def _call(prompt: str, max_tokens: int = 1200):
    client = _get_client()
    if client is None:
        return None
    try:
        resp = client.messages.create(
            model=_MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
        return "\n".join(parts)
    except Exception:
        return None


# --------------------------------------------------------------------------
# 1. Bullet rewrites
# --------------------------------------------------------------------------

def enrich_bullet_fixes(track_display: str, formatting_fixes: list) -> list:
    """
    Given the rule-based formatting_fixes (each: {section, bullet, issues}),
    ask the LLM for a concrete suggested rewrite per bullet. Returns the same
    list with an added "suggested_rewrite" key where possible. On any failure,
    returns the input unchanged.
    """
    if not formatting_fixes or not llm_enabled():
        return formatting_fixes

    subset = formatting_fixes[:_MAX_BULLETS]
    payload = [{"i": idx, "section": f["section"], "bullet": f["bullet"], "issues": f["issues"]}
               for idx, f in enumerate(subset)]

    prompt = (
        "You are a senior IIT Kanpur student mentor reviewing resume bullets for a "
        f"candidate targeting a {track_display} role. For each bullet below, write ONE "
        "improved rewrite that fixes the listed issues: lead with a strong action verb, "
        "add a plausible quantifiable metric (use a placeholder like [X]% or [N] if the "
        "real number is unknown — never invent a specific false figure), and keep it to a "
        "single concise line. Preserve the candidate's real work; do not fabricate new "
        "projects.\n\n"
        "Return STRICT JSON only, no prose, no markdown fences: an array of objects "
        '{"i": <index>, "rewrite": "<one line>"}.\n\n'
        f"Bullets:\n{json.dumps(payload, ensure_ascii=False)}"
    )

    raw = _call(prompt, max_tokens=1400)
    parsed = _extract_json(raw) if raw else None
    if not isinstance(parsed, list):
        return formatting_fixes

    rewrites = {}
    for item in parsed:
        if isinstance(item, dict) and "i" in item and "rewrite" in item:
            rewrites[item["i"]] = str(item["rewrite"]).strip()

    for idx, fix in enumerate(subset):
        if idx in rewrites and rewrites[idx]:
            fix["suggested_rewrite"] = rewrites[idx]
    return formatting_fixes


# --------------------------------------------------------------------------
# 2. Narrative summary
# --------------------------------------------------------------------------

def generate_summary(track_display: str, overall_score: float,
                     strengths: list, critical_missing: list) -> str:
    """
    Produce a short (2-4 sentence) mentor-style narrative grounded strictly in
    the rule-based strengths and gaps already computed. Returns "" if the LLM
    is disabled or the call fails (the UI simply shows no summary in that case).
    """
    if not llm_enabled():
        return ""

    prompt = (
        "You are a senior IIT Kanpur placement mentor. Write a concise 2-4 sentence "
        f"assessment of a resume targeting a {track_display} role that scored "
        f"{overall_score:.0f}/100 on our diagnostic. Base your assessment ONLY on the "
        "strengths and gaps listed below — do not introduce new claims or invent details. "
        "Be direct and encouraging, like advice from an experienced senior. Plain text only.\n\n"
        f"Strengths:\n- " + "\n- ".join(strengths or ["(none flagged)"]) + "\n\n"
        f"Gaps:\n- " + "\n- ".join(critical_missing or ["(none flagged)"])
    )

    raw = _call(prompt, max_tokens=350)
    return raw.strip() if raw else ""

