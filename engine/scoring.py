"""
Combines Module A (parsed resume) + Module B (NLP analysis) against a
Role-Specific Evaluation Baseline (Section 3 of the PS) to produce:
  - an overall Profile Match Score /100
  - per-component sub-scores
  - Top 3 Strengths
  - Critical Missing Elements
  - Line-by-Line Formatting Fixes (bullet-level, actionable)
"""
from dataclasses import dataclass, field

import re
from .data.role_baselines import ROLE_BASELINES
from .data.tech_field_courses import match_tech_field_courses
from .nlp_engine import (
    analyze_bullet, analyze_bullets, keyword_relevance_score, match_por_lines, find_entities,
)


@dataclass
class ScoreReport:
    track: str
    overall_score: float = 0.0
    component_scores: dict = field(default_factory=dict)     # component -> {"score": 0-100, "weight": w, "contribution": pts}
    strengths: list = field(default_factory=list)
    critical_missing: list = field(default_factory=list)
    formatting_fixes: list = field(default_factory=list)      # [{section, bullet, issue, suggestion}]
    entities_found: dict = field(default_factory=dict)
    por_matches: list = field(default_factory=list)
    penalties_applied: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    summary: str = ""          # LLM narrative (hybrid mode only; "" otherwise)
    llm_used: bool = False     # True when LLM feedback enrichment was applied
    is_circuital: bool = False # True when CSE/MTH/SDS/EE branch signal is detected


def _detect_circuital_branch(text: str) -> bool:
    """
    Detects whether candidate belongs to circuital branch (CSE, EE, MTH/MnC, SDS).
    Excludes non-circuital departments (e.g. Materials Science, Mechanical, Chemical, Aerospace, Civil)
    to prevent false positives from project keywords.
    """
    low = text.lower()
    
    # If explicitly from a core/non-circuital department, ensure no false positives
    non_circuital_branches = [
        "materials science", "mechanical", "chemical", "aerospace", "civil",
        "biological sciences", "bsbe", "economic sciences", "economics", "earth sciences", "chemistry"
    ]
    is_explicit_non_circ = any(nc in low for nc in non_circuital_branches)
    
    circuital_patterns = [
        r"\b(?:computer science(?:\s*and\s*engineering)?|cse|comp\.?\s*sci)\b",
        r"\b(?:mathematics and scientific computing|mnc|b\.?tech\s+mth|bs\s+mth|bs\s+mathematics)\b",
        r"\b(?:statistics and data science|sds|bs\s+sds|bs\s+statistics)\b",
        r"\b(?:electrical engineering|ee\b|b\.?tech\s+ee)\b",
    ]
    
    has_circ_match = any(re.search(pat, low) for pat in circuital_patterns)
    
    if is_explicit_non_circ and not any(re.search(p, low) for p in [r"\bdouble\s*major\b", r"\bdual\s*degree\b", r"\bcse\b", r"\bee\b"]):
        return False
        
    return has_circ_match


def _coursework_grade_multiplier(coursework_text: str) -> float:
    """Detects A/A* grades listed in coursework and returns a grade excellence multiplier."""
    high_grade_patterns = [r"\bA\*\b", r"\bGrade\s*[:\-]?\s*A\*\b", r"\(A\*\)", r"\[A\*\]", r"\bGrade\s*[:\-]?\s*A\b"]
    hits = sum(len(re.findall(pat, coursework_text, re.IGNORECASE)) for pat in high_grade_patterns)
    if hits >= 3:
        return 1.25
    elif hits >= 1:
        return 1.15
    return 1.0


def _evaluate_inter_iit(full_text: str, track: str):
    """
    Evaluates Inter IIT participation & medals with track-specific priority:
    - Quant Finance: Inter IIT Tech (Gold/Silver/Bronze) > Inter IIT Sports > Inter IIT Cult
    - Consulting: Inter IIT Sports (Gold/Silver/Bronze) > Inter IIT Tech > Inter IIT Cult
    - SDE / Core: Inter IIT Tech > Inter IIT Sports > Inter IIT Cult
    Returns (points_boost, category_detected, is_medalist)
    """
    low = full_text.lower()
    if not re.search(r"\binter[\s\-]?iit\b", low):
        return 0.0, None, False
        
    has_medal = bool(re.search(r"\b(?:gold|silver|bronze|winner|runner[\s\-]?up|1st|2nd|3rd|first|second|third|podium|champion|medal|medalist)\b", low))
    
    is_tech = bool(re.search(r"\binter[\s\-]?iit\s*(?:tech|technical|data|hackathon|engineer|robotics|ai)\b", low))
    is_sports = bool(re.search(r"\binter[\s\-]?iit\s*(?:sport|aquatic|athletic|cricket|football|badminton|basketball|tennis|volleyball|hockey|squash|weightlifting|table\s*tennis)\b", low))
    is_cult = bool(re.search(r"\binter[\s\-]?iit\s*(?:cult|cultural|dance|music|drama|debate|quiz)\b", low))
    
    if not (is_tech or is_sports or is_cult):
        if any(w in low for w in ["sport", "athlet", "captain", "cricket", "football", "badminton", "basketball"]):
            is_sports = True
        elif any(w in low for w in ["tech", "data", "hackathon", "robotics", "ai"]):
            is_tech = True
        else:
            is_tech = True
            
    base_tech = 35.0 if has_medal else 20.0
    base_sports = 35.0 if has_medal else 20.0
    base_cult = 25.0 if has_medal else 15.0
    
    if track == "Quant Finance":
        # Quant: Tech (1.3x) > Sports (0.8x) > Cult (0.5x)
        if is_tech:
            return base_tech * 1.3, "Inter IIT Tech", has_medal
        elif is_sports:
            return base_sports * 0.8, "Inter IIT Sports", has_medal
        else:
            return base_cult * 0.5, "Inter IIT Cultural", has_medal
    elif track == "Management Consulting":
        # Consulting: Sports (1.3x) > Tech (0.9x) > Cult (0.8x)
        if is_sports:
            return base_sports * 1.3, "Inter IIT Sports", has_medal
        elif is_tech:
            return base_tech * 0.9, "Inter IIT Tech", has_medal
        else:
            return base_cult * 0.8, "Inter IIT Cultural", has_medal
    else:
        # SDE / Core: Tech (1.2x) > Sports (0.7x) > Cult (0.5x)
        if is_tech:
            return base_tech * 1.2, "Inter IIT Tech", has_medal
        elif is_sports:
            return base_sports * 0.7, "Inter IIT Sports", has_medal
        else:
            return base_cult * 0.5, "Inter IIT Cultural", has_medal


def _detect_snt_coordinator(full_text: str, por_matches: list) -> bool:
    """
    Detects if candidate is a Coordinator / Head / Lead / Manager in Science and Technology Council (SnT):
    - Clubs: Aeromodelling, Astronomy, Electronics, Finance & Analytics, Programming, Robotics, Speedcubing
    - Societies: Brain & Cognitive (BCS), Descon, Game Development, IITK Consulting Group, Science Coffee House
    - Teams: Aerial Robotics, Team AUV, ERA, Team Humanoid, IITK Motorsports, Team Vision
    - Wings: Outreach & Connect, SnT Web Division
    """
    snt_keywords = [
        "science and technology council", "snt council", "snt", "aeromodelling", "astronomy",
        "electronics club", "finance & analytics", "finance and analytics", "programming club", "p-club",
        "robotics club", "speedcubing", "brain & cognitive", "brain and cognitive", "bcs", "descon",
        "game development", "game dev", "iitk consulting group", "science coffee house", "aerial robotics",
        "auv", "era", "humanoid", "motorsports", "team vision", "snt web", "outreach & connect"
    ]
    coord_titles = ["coordinator", "head", "lead", "team lead", "manager", "overall coordinator", "associate head", "captain"]
    
    for m in por_matches:
        match = m.get("match")
        line = m.get("line", "").lower()
        if match:
            por_name = str(match.get("por", "")).lower()
            council = str(match.get("council", "")).lower()
            if ("science & technology" in council or "snt" in council or any(k in por_name for k in snt_keywords)):
                if any(t in por_name or t in line for t in coord_titles):
                    return True
        if any(k in line for k in snt_keywords) and any(t in line for t in coord_titles):
            return True
            
    low = full_text.lower()
    for kw in snt_keywords:
        pat1 = rf"\b(?:coordinator|head|lead|manager|overall coordinator)\b[^\n]{{0,50}}\b{re.escape(kw)}\b"
        pat2 = rf"\b{re.escape(kw)}\b[^\n]{{0,50}}\b(?:coordinator|head|lead|manager|overall coordinator)\b"
        if re.search(pat1, low) or re.search(pat2, low):
            return True
    return False


def _detect_other_council_coordinator(full_text: str, por_matches: list):
    """
    Detects if candidate is a Coordinator / Manager / Head in other Councils, Cells, or Fests:
    - AnC (Academics & Career Council: UG Academics, Research, IR, Career Development Wing)
    - MnC (Media & Cultural Council: Clubs & Societies)
    - GnS (Games & Sports Council: Clubs, Societies & Teams)
    - Cells: Community Welfare (Prakriti, Pragati, Prayas, Raktarpan, Unmukt, Vivekananda Samiti), Election Commission, E-Cell, Outreach Cell, PPOC, Vox Populi
    - Fests: Antaragni, Techkriti, Udghosh
    Returns (has_coord, body_name)
    """
    councils_data = [
        ("Academic & Career Council (AnC)", ["academic and career", "academics and career", "anc", "ug academics", "career development wing", "cdw", "international relations wing", "research wing"]),
        ("Media & Cultural Council (MnC)", ["media and cultural", "mnc", "dramatics club", "dance club", "music club", "fine arts club", "quiz club", "debate and discussion", "film club", "design and animation", "hindi sahitya sabha", "humour house", "photography club", "anime society", "english literary society"]),
        ("Games & Sports Council (GnS)", ["games and sports", "gns", "gnc", "adventure sports", "archery", "chess club", "badminton", "basketball", "cricket", "football", "hockey", "lawn tennis", "squash", "table tennis", "volleyball", "weightlifting", "taekwondo", "aquatics", "athletics"]),
        ("Campus Cells (E-Cell / Outreach / PPOC / CWC / Vox / EC)", ["e-cell", "entrepreneurship cell", "outreach cell", "ppoc", "public policy", "vox populi", "cwc", "community welfare", "prakriti", "pragati", "prayas", "raktarpan", "unmukt", "vivekananda samiti", "election commission"]),
        ("Institute Festivals (Antaragni / Techkriti / Udghosh)", ["antaragni", "techkriti", "udghosh", "festival coordinator", "special task force"])
    ]
    coord_titles = ["coordinator", "head", "manager", "overall coordinator", "festival coordinator", "associate head", "chief editor", "convener", "wing manager"]
    
    for m in por_matches:
        match = m.get("match")
        line = m.get("line", "").lower()
        if match:
            por_name = str(match.get("por", "")).lower()
            council = str(match.get("council", "")).lower()
            for cname, kws in councils_data:
                if any(k in council or k in por_name for k in kws) and any(t in por_name or t in line for t in coord_titles):
                    return True, cname
        for cname, kws in councils_data:
            if any(k in line for k in kws) and any(t in line for t in coord_titles):
                return True, cname
                
    low = full_text.lower()
    for cname, kws in councils_data:
        for kw in kws:
            pat = rf"\b(?:coordinator|head|manager|overall coordinator|wing manager)\b[^\n]{{0,50}}\b{re.escape(kw)}\b"
            pat2 = rf"\b{re.escape(kw)}\b[^\n]{{0,50}}\b(?:coordinator|head|manager|overall coordinator|wing manager)\b"
            if re.search(pat, low) or re.search(pat2, low):
                return True, cname
    return False, None


def _project_tier_multiplier(projects_text: str, full_text: str) -> float:
    """
    Project Hierarchy:
    Prof Project / Research under Professor (1.30x) > Course Project (1.15x) > Club Project (1.05x) > Self / Hobby (0.95x)
    """
    low = (projects_text + " " + full_text).lower()
    prof_signals = ["under prof", "prof.", "professor", "guide: prof", "surge", "research intern", "btp", "ugp", "faculty"]
    course_signals = ["course project", "cs210", "cs330", "cs425", "eso207", "esc101", "instructor"]
    club_signals = ["programming club", "p-club", "robotics club", "aeromodelling", "electronics club", "e-cell", "snt"]
    
    if any(s in low for s in prof_signals):
        return 1.30
    elif any(s in low for s in course_signals):
        return 1.15
    elif any(s in low for s in club_signals):
        return 1.05
    return 0.95


def _cpi_subscore(cpi, thresholds, track: str = ""):
    if cpi is None:
        return 0.0
    good, excellent = thresholds["good"], thresholds["excellent"]
    if cpi >= excellent:
        # CPI >= 9.5 receives maximum reward with distinction
        return 100.0
    if cpi >= good:
        # linear between 60 and 100 across [good, excellent]
        return 60 + 40 * (cpi - good) / (excellent - good)
    # below "good": linear 0 to 60 across [good-2.5, good]
    floor = max(0.0, good - 2.5)
    if cpi <= floor:
        return 0.0
    return 60 * (cpi - floor) / (good - floor)


def _impact_density(all_bullet_analyses, target_density=0.22):
    """
    Fraction of narrative bullets carrying a quantifiable metric, rescaled so
    that hitting `target_density` earns full marks.

    Calibration note: across 74 real placed IITK resumes, the MEDIAN fraction
    of bullets with a true impact metric was only ~0.07-0.15 by track (even
    strong candidates quantify a minority of their bullets; ranks, years and
    course names aren't impact metrics). Scoring raw density * 100 therefore
    capped even excellent resumes around 10-15/100 on this component. We
    instead treat ~0.22 density (roughly the 75th percentile of the placed
    distribution) as full marks, so the component rewards being ABOVE the
    placed norm rather than demanding an unrealistic quantify-everything bar.
    """
    if not all_bullet_analyses:
        return 0.0, 0, 0
    total = len(all_bullet_analyses)
    with_metric = sum(1 for b in all_bullet_analyses if b.has_metric)
    density = with_metric / total
    score = min(100.0, (density / target_density) * 100.0)
    return score, with_metric, total


def _action_verb_subscore(all_bullet_analyses):
    """
    Calibration note: placed resumes open ~11-36% of bullets with a "strong"
    verb (Consulting lowest at ~0.11, Quant highest at ~0.36); the rest are
    'unknown' first tokens (a project/company name, a noun-led phrase), which
    are neutral, not bad. We give 'unknown' a baseline 0.55 rather than
    penalizing it, and reserve the 0-point floor for genuinely weak/passive
    openers ("Worked on", "Responsible for"). This keeps the component from
    unfairly punishing the common, acceptable noun-led bullet style seen
    throughout the placed corpus.
    """
    if not all_bullet_analyses:
        return 0.0
    points = {"strong": 1.0, "medium": 0.75, "unknown": 0.55, "weak": 0.0}
    total = sum(points[b.verb_strength] for b in all_bullet_analyses)
    return (total / len(all_bullet_analyses)) * 100.0


def _por_subscore(por_matches, weight_multiplier, full_text: str = ""):
    ratings = [m["match"]["rating"] for m in por_matches if m.get("match")]
    
    # Check for Elected selection mode or text mention
    is_elected = any(
        m.get("match") and (
            "elected" in str(m["match"].get("selection_mode", "")).lower() or
            "elected" in str(m.get("line", "")).lower()
        )
        for m in por_matches
    )
    if not is_elected and full_text:
        is_elected = bool(re.search(
            r"\b(?:democratically\s+elected|elected\s+as|elected\s+senator|elected\s+representative|elected\s+by|general\s+election|hall\s+president|general\s+secretary)\b",
            full_text, re.IGNORECASE
        ))

    # Check for Mentorship role or text mention
    is_mentor = any(
        m.get("match") and any(
            w in str(m["match"].get("por", "")).lower()
            for w in ["mentor", "guide", "tutor", "counselling"]
        )
        for m in por_matches
    )
    if not is_mentor and full_text:
        is_mentor = bool(re.search(
            r"\b(?:mentored|mentoring|peer\s+mentor|academic\s+mentor|career\s+departmental\s+mentor|student\s+guide|tutored|guided\s+\d+|onboarded\s+and\s+mentored)\b",
            full_text, re.IGNORECASE
        ))

    if not ratings:
        if is_elected and is_mentor:
            raw = 65.0
        elif is_elected:
            raw = 55.0
        elif is_mentor:
            raw = 45.0
        else:
            return 0.0, is_elected, is_mentor
    else:
        best = max(ratings)
        avg_extra = (sum(ratings) - best) / max(1, len(ratings) - 1) if len(ratings) > 1 else 0
        raw = best * 10 + avg_extra * 3   # best PoR dominates, others add a little
        
        # Significant weightage multipliers for elected mandate and mentorship
        if is_elected:
            # Democratic mandate / election represents major peer trust & leadership
            raw = min(100.0, raw * 1.30 + 10.0)
        if is_mentor:
            # Mentorship represents proactive empathy, guidance, and knowledge-sharing
            raw = min(100.0, raw * 1.20 + 8.0)

    raw *= weight_multiplier / 1.0 if weight_multiplier <= 1.0 else 1.0
    return min(100.0, raw), is_elected, is_mentor


def _links_formatting_subscore(parsed):
    score = 0.0
    if parsed.hyperlinks:
        score += 60.0
    github = any("github" in (l.get("url") or "").lower() for l in parsed.hyperlinks)
    linkedin = any("linkedin" in (l.get("url") or "").lower() for l in parsed.hyperlinks)
    if github:
        score += 25.0
    if linkedin:
        score += 15.0
    if parsed.column_layout_detected:
        score = min(100.0, score + 0)  # layout doesn't add points, just informs warnings
    return min(100.0, score)


def _research_subscore(text):
    text_low = text.lower()
    hits = sum(text_low.count(k) for k in ["publication", "research paper", "conference", "patent", "journal"])
    return min(100.0, hits * 35.0)


def score_resume(parsed, track: str, use_llm: bool = True) -> ScoreReport:
    """
    Score a parsed resume against a track baseline.

    `use_llm` only *permits* the optional hybrid feedback-text enrichment; it
    still requires hybrid mode to be actually enabled (env flag + API key) to
    have any effect. Pass use_llm=False to guarantee pure rule-based output
    (used by the deterministic test suite). The numeric score is identical
    either way — the LLM never touches scoring.
    """
    if track not in ROLE_BASELINES:
        raise ValueError(f"Unknown track '{track}'. Valid tracks: {list(ROLE_BASELINES)}")

    baseline = ROLE_BASELINES[track]
    weights = baseline["component_weights"]
    report = ScoreReport(track=track)
    report.warnings = list(parsed.warnings)

    # Flatten bullets for verb/impact analysis — but ONLY from narrative
    # achievement sections. Skills / Coursework / Education are lists of nouns
    # ("Programming Languages: C, C++, Python", "Linear Algebra, Calculus-I"),
    # not achievement bullets: including them would drag impact-density and
    # action-verb scores toward zero for every candidate, since a comma list
    # of course names has no metric and no opening verb. This mattered a lot
    # during calibration against real placed resumes (impact_density read as
    # ~0.05 before this fix, purely from list-line pollution).
    NARRATIVE_SECTIONS = {"Experience", "Projects", "Positions of Responsibility",
                          "Achievements", "Extracurricular", "Publications"}
    all_bullets = []
    bullet_origin = []  # (section, bullet_text)
    for section, bullets in parsed.bullets.items():
        # Match known section names, and also unaliased ones that clearly map to
        # a narrative bucket (e.g. "Self Projects", "Course Projects", "Work Experience").
        sec_low = section.lower()
        is_narrative = (section in NARRATIVE_SECTIONS
                        or "project" in sec_low or "experience" in sec_low
                        or "responsib" in sec_low or "achievement" in sec_low
                        or "intern" in sec_low)
        if not is_narrative:
            continue
        for b in bullets:
            all_bullets.append(b)
            bullet_origin.append((section, b))
    bullet_analyses = analyze_bullets(all_bullets)

    full_text = parsed.raw_text
    report.entities_found = find_entities(full_text)
    edu_hdr_text = " ".join(parsed.sections.get("Education", []) + parsed.sections.get("Header", []))
    if not edu_hdr_text.strip():
        edu_hdr_text = parsed.raw_text[:600]
    is_circuital = _detect_circuital_branch(edu_hdr_text)
    report.is_circuital = is_circuital

    # --- Component sub-scores (each 0-100) ---
    subscores = {}

    if "cpi" in weights:
        subscores["cpi"] = _cpi_subscore(parsed.cpi, baseline["cpi_threshold"], track=track)

    if "coursework" in weights:
        coursework_text = " ".join(parsed.sections.get("Coursework", []) + parsed.sections.get("Education", []))
        norm, matched = keyword_relevance_score(
            coursework_text, baseline["coursework_keywords"],
            target_coverage=baseline.get("coursework_target", 0.12))
        # Immediate strong score scaling if candidate has written genuine coursework
        if matched:
            count = len(matched)
            # 1 course -> base 60.0, 2 courses -> 80.0, 3+ -> 95.0 - 100.0
            base_score = 60.0 + min(40.0, (count - 1) * 20.0)
            cw_raw = max(norm * 100.0, base_score)
        else:
            cw_raw = 0.0
        grade_mult = _coursework_grade_multiplier(coursework_text)
        cw_score = cw_raw * grade_mult
        if is_circuital and track in ["SDE", "Quant Finance"]:
            cw_score *= 1.10  # Circuital branch curriculum alignment edge
        if track == "SDE":
            tech_matches = match_tech_field_courses(full_text)
            if tech_matches:
                cw_score *= 1.20  # 1.2x edge for tech-field courses from word document
                report.__dict__["_tech_field_courses"] = tech_matches
        subscores["coursework"] = min(100.0, cw_score)
        report.__dict__.setdefault("_matched_coursework", matched)

    if "projects" in weights:
        # Include narrative project/experience bullet text, not just the raw
        # section header lines, so keywords inside bullets count.
        proj_bullet_text = " ".join(
            b for s, bl in parsed.bullets.items() for b in bl
            if any(k in s.lower() for k in ["project", "experience", "intern"]))
        projects_text = " ".join(parsed.sections.get("Projects", [])
                                  + parsed.sections.get("Experience", [])) + " " + proj_bullet_text
        norm, matched = keyword_relevance_score(
            projects_text, baseline["keywords"],
            target_coverage=baseline.get("keyword_target", 0.25))
        proj_mult = _project_tier_multiplier(projects_text, full_text)
        subscores["projects"] = min(100.0, norm * 100.0 * proj_mult)
        report.__dict__.setdefault("_matched_projects", matched)

    inter_boost, inter_cat, is_medalist = _evaluate_inter_iit(full_text, track)

    if "competitive_programming" in weights and weights["competitive_programming"] > 0:
        cp_terms = ["codeforces", "codechef", "leetcode", "icpc", "kaggle", "competitive programming"]
        low = full_text.lower()
        cp_hits = sum(low.count(t) for t in cp_terms)
        raw_cp = cp_hits * 40.0
        if inter_cat and ("Tech" in inter_cat or track in ["Quant Finance", "SDE"]):
            raw_cp += inter_boost
        subscores["competitive_programming"] = min(100.0, raw_cp)

    if "por_leadership" in weights:
        # The matchable PoR *titles* ("Secretary, Debating Society", "Manager,
        # Academics and Career Council") are the non-bullet header lines of the
        # PoR section — the bullets are the DESCRIPTIONS ("Organized...",
        # "Led..."), which don't match catalogue role names. Feed the section's
        # non-bullet lines (the titles) to the matcher; fall back to bullets
        # only if there are no title lines.
        por_section_lines = parsed.sections.get("Positions of Responsibility", [])
        por_bullets = parsed.bullets.get("Positions of Responsibility", [])
        title_lines = [ln for ln in por_section_lines if ln.strip() and ln.strip() not in por_bullets]
        candidates = title_lines if title_lines else por_bullets
        por_matches = match_por_lines(candidates)
        report.por_matches = por_matches
        por_val, is_elected, is_mentor = _por_subscore(por_matches, baseline["por_weight_multiplier"], full_text=full_text)
        report.__dict__["_is_elected"] = is_elected
        report.__dict__["_is_mentor"] = is_mentor
        
        # Detect SnT Coordinator & Other Council Coordinator roles
        is_snt_coord = _detect_snt_coordinator(full_text, por_matches)
        has_other_coord, other_coord_council = _detect_other_council_coordinator(full_text, por_matches)
        report.__dict__["_is_snt_coord"] = is_snt_coord
        report.__dict__["_has_other_coord"] = has_other_coord
        report.__dict__["_other_coord_council"] = other_coord_council
        
        if is_snt_coord:
            por_val = min(100.0, por_val * 1.25 + 15.0)
        elif has_other_coord:
            por_val = min(100.0, por_val * 1.20 + 12.0)
        
        # Inter IIT Sports boost for Management Consulting (Sports > Tech > Cult)
        if inter_cat and track == "Management Consulting":
            por_val = min(100.0, por_val + inter_boost)
            
        # Synergy boost: Good CPI (>=8.0) + SnT Coordinator / P-Club / CoCo
        low_t = full_text.lower()
        if parsed.cpi and parsed.cpi >= 8.0 and any(k in low_t for k in ["programming club", "p-club", "snt", "company coordinator", "coco"]):
            por_val = min(100.0, por_val * 1.15)
        subscores["por_leadership"] = por_val

    if "impact_density" in weights:
        density, with_metric, total = _impact_density(bullet_analyses)
        subscores["impact_density"] = density
        report.__dict__["_impact_stats"] = (with_metric, total)

    if "action_verbs" in weights:
        subscores["action_verbs"] = _action_verb_subscore(bullet_analyses)

    if "links_formatting" in weights:
        subscores["links_formatting"] = _links_formatting_subscore(parsed)

    if "research_publications" in weights:
        subscores["research_publications"] = _research_subscore(full_text)

    # --- Weighted combination ---
    overall = 0.0
    for component, weight in weights.items():
        sub = subscores.get(component, 0.0)
        contribution = (sub / 100.0) * weight
        overall += contribution
        report.component_scores[component] = {
            "score": round(sub, 1), "weight": weight, "contribution": round(contribution, 1),
        }

    # --- Role & Council Strategic Edges ---
    # 1. 15-Point Boot Start for Circuital Branches in SDE and Quant roles
    if is_circuital and track in ["SDE", "Quant Finance"]:
        overall += 15.0

    # 2. 9-Point Edge for Circuital Branches with SnT Coordinator Leadership
    if is_circuital and report.__dict__.get("_is_snt_coord"):
        overall += 9.0

    # 3. Managerial Coordinator Edge for Other Councils in Consulting Track
    if report.__dict__.get("_has_other_coord") and track == "Management Consulting":
        overall += 8.0

    # --- Penalties ---
    penalties = baseline["penalties"]
    applied_penalty_pts = 0.0

    if "missing_github" in penalties:
        github = any("github" in (l.get("url") or "").lower() for l in parsed.hyperlinks)
        if not github:
            desc, pts = penalties["missing_github"]
            report.penalties_applied.append({"rule": "missing_github", "description": desc, "points": pts})
            applied_penalty_pts += pts

    if "no_recognized_language" in penalties:
        langs = ["c++", "java", "python", "golang", "go ", "rust"]
        if not any(l in full_text.lower() for l in langs):
            desc, pts = penalties["no_recognized_language"]
            report.penalties_applied.append({"rule": "no_recognized_language", "description": desc, "points": pts})
            applied_penalty_pts += pts

    if "generic_project_no_impact" in penalties:
        # Only penalize when the WHOLE narrative body is metric-free — not just
        # the Projects section in isolation. Placed resumes routinely have some
        # metric-free project bullets while quantifying impact elsewhere
        # (Experience, Achievements); firing on Projects-only was too harsh
        # (triggered on 28% of placed SDE resumes during calibration).
        if bullet_analyses and not any(b.has_metric for b in bullet_analyses):
            desc, pts = penalties["generic_project_no_impact"]
            report.penalties_applied.append({"rule": "generic_project_no_impact", "description": desc, "points": pts})
            applied_penalty_pts += pts

    if "low_cpi" in penalties and parsed.cpi is not None:
        if parsed.cpi < baseline["cpi_threshold"]["good"] - 1.0:
            desc, pts = penalties["low_cpi"]
            report.penalties_applied.append({"rule": "low_cpi", "description": desc, "points": pts})
            applied_penalty_pts += pts

    if "no_math_project" in penalties:
        math_terms = ["probability", "stochastic", "statistics", "linear algebra", "optimization"]
        if not any(t in full_text.lower() for t in math_terms):
            desc, pts = penalties["no_math_project"]
            report.penalties_applied.append({"rule": "no_math_project", "description": desc, "points": pts})
            applied_penalty_pts += pts

    if "no_algorithmic_signal" in penalties:
        if not any(t in full_text.lower() for t in ["codeforces", "codechef", "leetcode", "icpc", "algorithm"]):
            desc, pts = penalties["no_algorithmic_signal"]
            report.penalties_applied.append({"rule": "no_algorithmic_signal", "description": desc, "points": pts})
            applied_penalty_pts += pts

    if "no_leadership_por" in penalties:
        # Fire only when there's NO recognizable PoR at all — not merely when
        # the best PoR is below "Mid" tier. Requiring Mid+ was too strict: it
        # penalized every placed Consulting candidate whose genuine leadership
        # role (club secretary, design manager) matched the catalogue at a
        # lower tier. Any confident catalogue match now clears the penalty.
        por_matches = report.por_matches or []
        any_match = [m for m in por_matches if m["match"]]
        if not any_match:
            desc, pts = penalties["no_leadership_por"]
            report.penalties_applied.append({"rule": "no_leadership_por", "description": desc, "points": pts})
            applied_penalty_pts += pts

    if "no_business_impact_metric" in penalties:
        if bullet_analyses and not any(b.has_metric for b in bullet_analyses):
            desc, pts = penalties["no_business_impact_metric"]
            report.penalties_applied.append({"rule": "no_business_impact_metric", "description": desc, "points": pts})
            applied_penalty_pts += pts

    if "generic_web_dev_dominant" in penalties:
        proj_text = " ".join(parsed.sections.get("Projects", [])).lower()
        web_terms = ["website", "web app", "e-commerce", "todo app", "blog site"]
        core_terms = list(baseline["keywords"].keys())
        web_hits = sum(proj_text.count(t) for t in web_terms)
        core_hits = sum(proj_text.count(t) for t in core_terms)
        if web_hits > 0 and core_hits == 0:
            desc, pts = penalties["generic_web_dev_dominant"]
            report.penalties_applied.append({"rule": "generic_web_dev_dominant", "description": desc, "points": pts})
            applied_penalty_pts += pts

    if "no_surge_or_core_internship" in penalties:
        if "surge" not in full_text.lower() and not parsed.sections.get("Experience"):
            desc, pts = penalties["no_surge_or_core_internship"]
            report.penalties_applied.append({"rule": "no_surge_or_core_internship", "description": desc, "points": pts})
            applied_penalty_pts += pts

    overall = max(0.0, min(100.0, overall) - applied_penalty_pts)
    report.overall_score = round(overall, 1)

    # --- Strengths (top 3 by contribution) ---
    ranked = sorted(report.component_scores.items(), key=lambda kv: kv[1]["contribution"], reverse=True)
    strength_labels = {
        "cpi": "Strong CPI relative to track expectations",
        "coursework": "Coursework closely matches track requirements",
        "projects": "Projects show strong keyword/tech alignment with the track",
        "competitive_programming": "Solid competitive programming signal",
        "por_leadership": "High-impact Positions of Responsibility",
        "impact_density": "Bullet points are well-quantified with metrics",
        "action_verbs": "Bullets consistently open with strong action verbs",
        "links_formatting": "Portfolio/GitHub links are present and well-attached",
        "research_publications": "Research/publication signal detected",
    }
    for component, data in ranked[:3]:
        if data["score"] >= 40:
            report.strengths.append(f"{strength_labels.get(component, component)} "
                                     f"(scored {data['score']}/100, contributing {data['contribution']} pts)")
    
    if inter_cat:
        if track == "Quant Finance" and "Tech" in inter_cat:
            report.strengths.insert(0, f"{inter_cat} {'Medalist' if is_medalist else 'Participant'} (Top Priority for Quant Technical Rigor)")
        elif track == "Management Consulting" and "Sports" in inter_cat:
            report.strengths.insert(0, f"{inter_cat} {'Medalist / Athlete' if is_medalist else 'Varsity Player'} (Top Priority for Consulting Leadership & Grit)")
        elif is_medalist:
            report.strengths.insert(0, f"{inter_cat} Medalist — prestigious institute milestone")
            
    if track == "SDE" and report.__dict__.get("_tech_field_courses"):
        t_courses = report.__dict__["_tech_field_courses"]
        report.strengths.insert(0, f"Tech Coursework Edge (1.2x) — completed tech-aligned coursework ({t_courses[0]})")
        
    if is_circuital and report.__dict__.get("_is_snt_coord"):
        report.strengths.insert(0, "Circuital + SnT Coordinator Edge (+9 pts) — elite technical leadership & domain synergy")
    elif is_circuital and track in ["SDE", "Quant Finance"]:
        report.strengths.insert(0, "Circuital Branch Advantage (+15 pts) — strong curriculum alignment in SDE & Quant")
        
    if report.__dict__.get("_has_other_coord"):
        cname = report.__dict__.get("_other_coord_council", "Campus Council")
        report.strengths.insert(0, f"Managerial Leadership ({cname}) — verified executive coordination")

    if report.__dict__.get("_is_elected"):
        report.strengths.insert(0, "Democratic Mandate: Holds an elected leadership position with verified peer consensus")
    elif report.__dict__.get("_is_mentor"):
        report.strengths.insert(0, "Mentorship & Guidance: Proven track record of mentoring and developing peers/juniors")
    
    report.strengths = report.strengths[:3]
    if not report.strengths:
        report.strengths.append("No component scored strongly enough to flag as a clear strength — "
                                 "see Critical Missing Elements below.")

    # --- Critical Missing Elements ---
    for component, data in report.component_scores.items():
        if data["score"] < 30 and weights.get(component, 0) >= 5:
            report.critical_missing.append(
                f"{strength_labels.get(component, component).replace('Strong', 'Weak').replace('High-impact', 'Low-impact')} "
                f"— only {data['score']}/100 (this component is worth {data['weight']} pts for {track})"
            )
    for p in report.penalties_applied:
        report.critical_missing.append(f"[Penalty -{p['points']} pts] {p['description']}")

    # --- Line-by-line bullet analysis ---
    for (section, bullet), analysis in zip(bullet_origin, bullet_analyses):
        issues = []
        if analysis.verb_strength == "weak":
            issues.append(f"Opens with a weak verb ('{analysis.opening_word}'). "
                           f"Replace with a strong action verb (e.g., 'Engineered', 'Optimized', 'Led').")
        if analysis.weak_phrases:
            issues.append(f"Contains a passive/low-signal phrase: '{analysis.weak_phrases[0]}'. Rewrite to lead with the outcome.")
        # Only flag missing metrics for Projects and Experience bullets where measurable engineering/business impact is expected
        # Never flag for Achievements, Honors, Awards, Extracurricular, or PoRs
        if not analysis.has_metric and any(k in section.lower() for k in ["project", "experience", "intern"]):
            issues.append("No quantifiable metric — add a number (%, count, time saved, scale) to show impact.")
        if issues:
            report.formatting_fixes.append({
                "section": section,
                "bullet": bullet,
                "issues": issues,
            })

    # --- Hybrid LLM enrichment (optional, never affects the score) ---
    # The scoring above is fully deterministic and complete at this point. If
    # hybrid mode is enabled (env flag + API key), we enrich the *text* only:
    # concrete bullet rewrites and a narrative summary. On any failure this is
    # a no-op and the rule-based feedback stands.
    if use_llm:
        try:
            from .llm_feedback import llm_enabled, enrich_bullet_fixes, generate_summary
            if llm_enabled():
                report.formatting_fixes = enrich_bullet_fixes(
                    baseline["display_name"], report.formatting_fixes)
                report.summary = generate_summary(
                    baseline["display_name"], report.overall_score,
                    report.strengths, report.critical_missing)
                report.llm_used = any("suggested_rewrite" in f for f in report.formatting_fixes) \
                    or bool(report.summary)
        except Exception:
            # Never let feedback enrichment break scoring.
            pass

    return report
