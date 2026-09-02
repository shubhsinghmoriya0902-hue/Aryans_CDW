"""
Module C - The Advisory Dashboard (Streamlit)

A clean, light, ATS-inspired interface for the Resume Diagnostic Engine.
Branding: Pool Aryans · Career Development Wing

Run with:  streamlit run app.py
"""
import os
import re
import time
import tempfile
import streamlit as st

from engine import parse_resume, score_resume, TRACKS, ROLE_BASELINES
from engine.scoring import _detect_circuital_branch, _detect_snt_coordinator, _detect_other_council_coordinator

# --- Palette (clean, accessible, ATS-inspired) -------------------------------
BLUE = "#1a73e8"       # brand / accent
DARK_NAVY = "#0f1e3c"  # primary title
INK = "#1e293b"        # primary text
SLATE = "#64748b"      # secondary text
GREEN = "#10b981"      # good band
AMBER = "#f59e0b"      # mid band
RED = "#ef4444"        # low band
LINE = "#e2e8f0"       # hairline borders
CARD = "#ffffff"
BG = "#f8fafc"
CARD_BG = "#f1f5f9"

st.set_page_config(
    page_title="Pool Aryans · Resume Diagnostic",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Global CSS -------------------------------------------------------------
st.markdown(f"""
<style>
    .stApp {{ background: {BG}; }}
    #MainMenu {{ visibility: hidden; }}
    footer {{ visibility: hidden; }}
    header {{ background: transparent !important; }}
    
    /* Keep sidebar reopen button visible and styled */
    [data-testid="stSidebarCollapseButton"],
    [data-testid="stSidebarCollapsedControl"],
    button[kind="header"] {{
        display: flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        color: {BLUE} !important;
        background: #ffffff !important;
        border: 1px solid {LINE} !important;
        border-radius: 8px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08) !important;
        z-index: 999999 !important;
    }}
    .block-container {{ padding-top: 2rem; max-width: 1140px; }}

    html, body, [class*="css"] {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
        color: {INK};
    }}

    .app-title {{
        font-size: 1.65rem; font-weight: 800; color: {DARK_NAVY};
        letter-spacing: -0.02em; margin-bottom: 0.15rem;
    }}
    .app-sub {{ color: {SLATE}; font-size: 0.92rem; margin-bottom: 1.3rem; }}

    .card {{
        background: {CARD}; border: 1px solid {LINE}; border-radius: 12px;
        padding: 1.25rem 1.4rem; margin-bottom: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.02);
    }}
    .card-title {{
        font-size: 0.74rem; font-weight: 700; letter-spacing: 0.08em;
        text-transform: uppercase; color: {SLATE}; margin-bottom: 0.9rem;
    }}

    /* Candidate Profile Box */
    .profile-banner {{
        background: linear-gradient(135deg, #0f1e3c 0%, #1e3a8a 100%);
        color: #ffffff; border-radius: 12px; padding: 1.3rem 1.6rem;
        margin-bottom: 1.2rem;
    }}
    .profile-name {{ font-size: 1.5rem; font-weight: 800; letter-spacing: -0.01em; color: #ffffff; }}
    .profile-meta {{ font-size: 0.88rem; color: #cbd5e1; margin-top: 0.25rem; }}
    .profile-badge {{
        display: inline-block; font-size: 0.72rem; font-weight: 700;
        padding: 0.22rem 0.65rem; border-radius: 999px; margin-right: 0.4rem;
        text-transform: uppercase; letter-spacing: 0.04em;
    }}

    /* Big score readout */
    .score-num {{ font-size: 3.8rem; font-weight: 800; line-height: 1; letter-spacing: -0.02em; }}
    .score-max {{ font-size: 1.15rem; color: {SLATE}; font-weight: 600; }}
    .score-band {{
        display: inline-block; font-size: 0.75rem; font-weight: 700;
        padding: 0.25rem 0.75rem; border-radius: 999px; margin-top: 0.5rem;
        letter-spacing: 0.04em; text-transform: uppercase;
    }}

    /* Component rows */
    .comp-row {{ margin-bottom: 0.85rem; }}
    .comp-head {{ display: flex; justify-content: space-between; font-size: 0.86rem; margin-bottom: 0.28rem; }}
    .comp-name {{ color: {INK}; font-weight: 600; }}
    .comp-val {{ color: {SLATE}; font-variant-numeric: tabular-nums; }}
    .bar-track {{ background: #e2e8f0; border-radius: 999px; height: 7px; overflow: hidden; }}
    .bar-fill {{ height: 7px; border-radius: 999px; }}

    /* Diagnostic chips */
    .chip {{
        display: inline-flex; align-items: center; gap: 0.35rem; background: #f1f5f9;
        border: 1px solid {LINE}; border-radius: 8px; padding: 0.35rem 0.65rem;
        font-size: 0.82rem; color: {INK}; margin: 0.2rem 0.35rem 0.2rem 0;
    }}
    .chip b {{ color: {BLUE}; font-weight: 700; }}

    /* Strength / gap list items */
    .li {{
        display: flex; gap: 0.6rem; padding: 0.6rem 0; border-bottom: 1px solid {LINE};
        font-size: 0.88rem; line-height: 1.45;
    }}
    .li:last-child {{ border-bottom: none; }}
    .li .mark {{ flex: none; font-weight: 800; }}

    /* Fix cards */
    .fix {{ border-left: 3px solid {AMBER}; background: #fffbeb; border-radius: 6px;
            padding: 0.75rem 0.95rem; margin-bottom: 0.75rem; }}
    .fix-sec {{ font-size: 0.7rem; font-weight: 700; letter-spacing: 0.06em;
                text-transform: uppercase; color: #b45309; margin-bottom: 0.3rem; }}
    .fix-bullet {{ font-size: 0.86rem; color: {INK}; margin-bottom: 0.45rem; font-style: italic; }}
    .fix-issue {{ font-size: 0.83rem; color: {SLATE}; padding-left: 0.9rem; position: relative; margin-bottom: 0.25rem; }}
    .fix-issue:before {{ content: "→"; position: absolute; left: 0; color: {AMBER}; }}

    .stButton>button {{
        background: {BLUE}; color: #fff; border: none; border-radius: 8px;
        font-weight: 600; padding: 0.55rem 1rem; width: 100%;
    }}
    .stButton>button:hover {{ background: #1557b0; color: #fff; }}

    div[data-testid="stFileUploaderDropzone"] {{ background: {CARD}; border: 1px dashed #cbd5e1; border-radius: 10px; }}
    section[data-testid="stSidebar"] {{ background: {CARD}; border-right: 1px solid {LINE}; }}
</style>
""", unsafe_allow_html=True)


def band(score):
    if score >= 65:
        return GREEN, "Strong Match"
    if score >= 40:
        return AMBER, "Moderate Match"
    return RED, "Needs Work"


def bar_color(v):
    if v >= 65:
        return GREEN
    if v >= 40:
        return AMBER
    return RED


def extract_candidate_profile(parsed, report):
    """Pulls candidate identity, demographics, academic details, and links from parsed resume."""
    raw = parsed.raw_text
    header_lines = parsed.sections.get("Header", [])
    name = header_lines[0].strip() if header_lines else "Candidate"
    name = re.sub(r"\s+", " ", name).title()

    # Email (inspect raw text and mailto: hyperlinks)
    emails = re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", raw)
    if not emails:
        for l in parsed.hyperlinks:
            url = l.get("url", "")
            m_mail = re.search(r"mailto:([\w\.-]+@[\w\.-]+\.\w+)", url, re.IGNORECASE)
            if m_mail:
                emails = [m_mail.group(1)]
                break
    email = emails[0] if emails else "Not detected"

    # Roll Number
    roll = "Not detected"
    roll_match = re.search(r"\b(?:roll\s*(?:no\.?|number)?\s*[:\-]?\s*)(\d{6,9})\b", raw, re.IGNORECASE)
    if roll_match:
        roll = roll_match.group(1)
    if roll == "Not detected":
        for h in header_lines[:3]:
            m_h = re.search(r"\b(2\d{5,7})\b", h)
            if m_h:
                roll = m_h.group(1)
                break

    # Phone
    phones = re.findall(r"(?:\+?91[\-\s]?)?[6-9]\d{9}\b", raw)
    if not phones:
        phones = re.findall(r"\b[6-9]\d{4}\s*\d{5}\b", raw)
    if not phones:
        for l in parsed.hyperlinks:
            url = l.get("url", "")
            m_tel = re.search(r"tel:(?:\+?91[\-\s]?)?([6-9]\d{9})", url, re.IGNORECASE)
            if m_tel:
                phones = [m_tel.group(1)]
                break
    phone = phones[0] if phones else "Not detected"

    # Department & Programme
    dept = "IIT Kanpur"
    dept_patterns = [
        r"(?:department of\s+|dept\.?\s+of\s+)([\w\s&]+?)(?=[,\(\*\n\|]|$)",
        r"(?:b\.?\s?tech|bs|major|minor)\s+in\s+([\w\s&]+?)(?=[,\(\*\n\|]|$)",
        r"(?:b\.?\s?tech|bs|dual degree|bachelor of technology)\s*[,:\-]?\s*([\w\s&]+?)(?=[,\(\*\n\|]|$)",
    ]
    for line in header_lines + parsed.sections.get("Education", []):
        for pat in dept_patterns:
            m = re.search(pat, line, re.IGNORECASE)
            if m:
                cand_dept = m.group(1).strip()
                if len(cand_dept) > 3 and not any(w in cand_dept.lower() for w in ["third", "undergraduate", "iitk", "technology"]):
                    dept = cand_dept.title()
                    break
        if dept != "IIT Kanpur":
            break

    # If still generic, check known IITK departments
    if dept == "IIT Kanpur":
        for known in [
            "Materials Science and Engineering", "Computer Science and Engineering", "Electrical Engineering",
            "Mathematics and Scientific Computing", "Mechanical Engineering", "Chemical Engineering",
            "Aerospace Engineering", "Civil Engineering", "Biological Sciences and Bioengineering",
            "Economic Sciences", "Statistics and Data Science", "Physics", "Chemistry"
        ]:
            if known.lower() in raw.lower():
                dept = known
                break

    # Programme
    programme = "B.Tech"
    if re.search(r"\bdouble\s*major\b", raw, re.IGNORECASE):
        programme = "Double Major"
    elif re.search(r"\bdual\s*degree\b", raw, re.IGNORECASE):
        programme = "Dual Degree (B.Tech - M.Tech)"
    elif re.search(r"\bBS\b|\bBachelor of Science\b", raw):
        programme = "BS"
    elif re.search(r"\bminor\b", raw, re.IGNORECASE):
        programme = "B.Tech with Minor"

    # Degree / Year Batch Calibration:
    # 3rd Years = Y24 | 2nd Years = Y25 | 4th Years = Y23 | Graduating = Y22
    year_str = "Undergraduate"
    low_all = (raw + " " + email + " " + " ".join(l.get("url", "") for l in parsed.hyperlinks)).lower()
    if re.search(r"\bthird[\s\-]year\b", raw, re.IGNORECASE) or "y24" in low_all or "24@iitk" in low_all or "2024-2028" in raw or "2024 - 2028" in raw:
        year_str = "3rd Year Undergraduate (Y24)"
    elif re.search(r"\bsecond[\s\-]year\b", raw, re.IGNORECASE) or "y25" in low_all or "25@iitk" in low_all or "2025-2029" in raw or "2025 - 2029" in raw:
        year_str = "2nd Year Undergraduate (Y25)"
    elif re.search(r"\bfourth[\s\-]year\b", raw, re.IGNORECASE) or "y23" in low_all or "23@iitk" in low_all or "2023-2027" in raw or "2023 - 2027" in raw:
        year_str = "4th Year Undergraduate (Y23)"
    elif "y22" in low_all or "22@iitk" in low_all or "2022-2026" in raw:
        year_str = "Graduating Batch (Y22)"
    elif "y26" in low_all or "26@iitk" in low_all or "2026-2030" in raw:
        year_str = "1st Year Undergraduate (Y26)"

    # Links (clean mailto out of web links)
    gh_links = [l["url"] for l in parsed.hyperlinks if "github" in (l.get("url") or "").lower()]
    li_links = [l["url"] for l in parsed.hyperlinks if "linkedin" in (l.get("url") or "").lower()]
    cf_links = [l["url"] for l in parsed.hyperlinks if "codeforces" in (l.get("url") or "").lower() or "codechef" in (l.get("url") or "").lower()]
    other_links = [l["url"] for l in parsed.hyperlinks if l["url"] not in gh_links and l["url"] not in li_links and l["url"] not in cf_links and not l["url"].lower().startswith("mailto:")]

    # Education rows
    edu_lines = parsed.sections.get("Education", [])

    return {
        "name": name,
        "roll": roll,
        "email": email,
        "phone": phone,
        "dept": dept,
        "programme": programme,
        "year": year_str,
        "cpi": parsed.cpi,
        "is_circuital": report.is_circuital,
        "github": gh_links[0] if gh_links else None,
        "linkedin": li_links[0] if li_links else None,
        "cp_profile": cf_links[0] if cf_links else None,
        "other_links": other_links,
        "edu_lines": edu_lines,
    }


# --- Header (Pool Aryans Branding) -------------------------------------------
st.markdown('<div class="app-title">Resume Diagnostic Engine</div>', unsafe_allow_html=True)
st.markdown('<div class="app-sub">IITK Context-Aware Resume Scorer · Pool Aryans · Career Development Wing</div>',
            unsafe_allow_html=True)

# --- Sidebar (inputs) -------------------------------------------------------
with st.sidebar:
    st.markdown(f'<div class="card-title" style="margin-top:0.5rem;">Upload Resume</div>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader("SPO-formatted PDF", type=["pdf"], label_visibility="collapsed")

    st.markdown(f'<div class="card-title" style="margin-top:1.2rem;">Target Evaluation Track</div>', unsafe_allow_html=True)
    track = st.radio("Track", TRACKS, label_visibility="collapsed")

    st.markdown('<div style="height:0.8rem;"></div>', unsafe_allow_html=True)
    run_btn = st.button("Analyze Resume")

    st.markdown(f'<div class="card-title" style="margin-top:1.6rem;">Scoring Weights · {track}</div>',
                unsafe_allow_html=True)
    weights = ROLE_BASELINES[track]["component_weights"]
    for comp, w in sorted(weights.items(), key=lambda kv: -kv[1]):
        if w > 0:
            pct = w / max(weights.values())
            st.markdown(
                f'<div style="font-size:0.78rem;color:{SLATE};margin-bottom:0.15rem;">'
                f'{comp.replace("_", " ").title()} <b style="color:{BLUE};float:right;">{w} pts</b></div>'
                f'<div class="bar-track" style="margin-bottom:0.5rem;">'
                f'<div class="bar-fill" style="width:{pct*100:.0f}%;background:{BLUE};opacity:0.65;"></div></div>',
                unsafe_allow_html=True)


# --- Empty state ------------------------------------------------------------
if not run_btn:
    st.markdown(f"""
    <div class="card">
        <div class="card-title">How the Diagnostic Engine Evaluates</div>
        <div style="font-size:0.92rem;line-height:1.75;color:{INK};">
        <b style="color:{BLUE};">1 · Layout-Aware Parse</b> &nbsp;Uses coordinate geometry and X-axis histograms to read multi-column SPO resumes without word-gluing.<br>
        <b style="color:{BLUE};">2 · Semantic Weighting</b> &nbsp;Evaluates achievements against IITK entities (SURGE, AnC/SnT/MnC/GnS Councils), quantifiable metric density, action verbs, and the 92-role PoR catalogue.<br>
        <b style="color:{BLUE};">3 · Role Baselines & Multipliers</b> &nbsp;Applies role-specific rubrics across SDE, Quant, Consulting, and Core, factoring in democratic election mandates, mentorship credit, and circuital branch synergy.<br>
        <b style="color:{BLUE};">4 · Actionable Advisory</b> &nbsp;Generates Top 3 Strengths, Critical Gaps, and line-by-line bullet rewrites.
        </div>
    </div>
    <div style="color:{SLATE};font-size:0.86rem;text-align:center;margin-top:1.5rem;">
        Upload an SPO-formatted PDF and select a target track, then click <b style="color:{BLUE};">Analyze Resume</b>.
    </div>
    """, unsafe_allow_html=True)
    st.stop()

if not uploaded_file:
    st.markdown(f'<div class="card" style="border-left:3px solid {RED};">'
                f'<b style="color:{RED};">No file uploaded.</b> '
                f'<span style="color:{SLATE};">Please upload a PDF resume in the sidebar to run analysis.</span></div>',
                unsafe_allow_html=True)
    st.stop()


# --- Processing sequence (staged, with deliberate pacing) -------------------
with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
    tmp.write(uploaded_file.read())
    tmp_path = tmp.name

status = st.empty()
stages = [
    "Reading PDF layout geometry and whitespace histograms…",
    "Reconstructing reading order and isolating sections…",
    "Extracting degree-table CPI, active hyperlinks, and bullet points…",
    "Running campus semantic weighting and action verb classifier…",
    "Matching Positions of Responsibility against 92-role catalogue…",
    "Calculating role match score and strategic council multipliers…",
]

parsed = None
report = None
for i, msg in enumerate(stages):
    status.markdown(
        f'<div class="card" style="border-left:3px solid {BLUE};">'
        f'<div style="font-size:0.9rem;color:{INK};">'
        f'<span style="color:{BLUE};font-weight:700;">●</span> &nbsp;{msg}</div>'
        f'<div class="bar-track" style="margin-top:0.7rem;">'
        f'<div class="bar-fill" style="width:{(i+1)/len(stages)*100:.0f}%;background:{BLUE};"></div></div>'
        f'</div>', unsafe_allow_html=True)
    if i == 2 and parsed is None:
        parsed = parse_resume(tmp_path)
    if i == 5 and report is None:
        if parsed is None:
            parsed = parse_resume(tmp_path)
        report = score_resume(parsed, track, use_llm=False)
    time.sleep(0.3)

os.unlink(tmp_path)
status.empty()

meta = ROLE_BASELINES[track]
bcolor, blabel = band(report.overall_score)
profile = extract_candidate_profile(parsed, report)

# =============================================================================
# 1. CANDIDATE PROFILE BANNER & EXTRACTED RESUME DETAILS
# =============================================================================
roll_str = f'<span style="font-size:1.05rem;font-weight:600;color:#93c5fd;margin-left:0.5rem;">(Roll: {profile["roll"]})</span>' if profile["roll"] != "Not detected" else ''
cpi_display = f"{profile['cpi']:.2f} / 10.0" if profile["cpi"] is not None else "Not Detected"

links_html = []
if profile["github"]:
    links_html.append(f'<a href="{profile["github"]}" target="_blank" style="color:#93c5fd;text-decoration:none;">🔗 GitHub</a>')
if profile["linkedin"]:
    links_html.append(f'<a href="{profile["linkedin"]}" target="_blank" style="color:#93c5fd;text-decoration:none;">🔗 LinkedIn</a>')
if profile["cp_profile"]:
    links_html.append(f'<a href="{profile["cp_profile"]}" target="_blank" style="color:#93c5fd;text-decoration:none;">⚡ CP Profile</a>')
for ol in profile["other_links"][:2]:
    links_html.append(f'<a href="{ol}" target="_blank" style="color:#93c5fd;text-decoration:none;">🔗 Web Link</a>')
links_str = " &nbsp;|&nbsp; ".join(links_html) if links_html else '<span style="color:#94a3b8;">No active hyperlinks attached</span>'

banner_html = f"""<div class="profile-banner">
<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:0.8rem;">
<div>
<div class="profile-name">{profile['name']}{roll_str}</div>
<div class="profile-meta">
<b>{profile['programme']}</b> in <b>{profile['dept']}</b> &nbsp;·&nbsp; {profile['year']}<br>
Email: <b>{profile['email']}</b> &nbsp;·&nbsp; Phone: <b>{profile['phone']}</b>
</div>
<div style="margin-top:0.6rem;">
<span class="profile-badge" style="background:rgba(255,255,255,0.2);">Cumulative CPI: <b>{cpi_display}</b></span>
<span class="profile-badge" style="background:rgba(255,255,255,0.15);">Target Track: <b>{track}</b></span>
</div>
</div>
<div style="text-align:right;font-size:0.86rem;margin-top:0.2rem;">
<div style="font-weight:700;color:#cbd5e1;text-transform:uppercase;font-size:0.72rem;letter-spacing:0.06em;margin-bottom:0.2rem;">Extracted Verified Links</div>
<div>{links_str}</div>
</div>
</div>
</div>"""
st.markdown(banner_html, unsafe_allow_html=True)


# =============================================================================
# 2. SCORE READOUT + DETAILED PARSE DIAGNOSTICS
# =============================================================================
left, right = st.columns([1, 1.35], gap="medium")

with left:
    score_html = f"""<div class="card" style="text-align:center;">
<div class="card-title">Target Match · {meta['display_name']}</div>
<div class="score-num" style="color:{bcolor};">{report.overall_score:.0f}<span class="score-max"> / 100</span></div>
<div class="score-band" style="background:{bcolor}1a;color:{bcolor};">{blabel}</div>
</div>"""
    st.markdown(score_html, unsafe_allow_html=True)

    # Detailed Parse Diagnostics
    cols_ok = parsed.column_layout_detected
    gh_ok = any("github" in (l.get("url") or "").lower() for l in parsed.hyperlinks)
    li_ok = any("linkedin" in (l.get("url") or "").lower() for l in parsed.hyperlinks)
    
    total_bullets = sum(len(b) for b in parsed.bullets.values())
    impact_stats = report.__dict__.get("_impact_stats", (0, total_bullets))
    metrics_count = impact_stats[0]
    metric_density_pct = (metrics_count / max(1, total_bullets)) * 100

    sections_detected = [s for s in parsed.sections if s != "Header"]
    total_words = len(parsed.raw_text.split())
    roll_chip = f'<span class="chip">Roll No <b>{profile["roll"]}</b></span>' if profile["roll"] != "Not detected" else ""
    branch_str = 'Circuital (CSE/EE/MTH/SDS)' if profile['is_circuital'] else 'Core / Applied Sciences'

    diag_html = f"""<div class="card">
<div class="card-title">Comprehensive Parse Diagnostics & Metadata</div>
<div style="margin-bottom:0.5rem;">
<span class="chip">Candidate <b>{profile['name']}</b></span>
{roll_chip}
<span class="chip">Dept <b>{profile['dept']}</b></span>
</div>
<div style="margin-bottom:0.5rem;">
<span class="chip">Programme <b>{profile['programme']}</b></span>
<span class="chip">Year <b>{profile['year']}</b></span>
<span class="chip">CPI <b>{cpi_display}</b></span>
<span class="chip">Branch <b>{branch_str}</b></span>
</div>
<div style="margin-bottom:0.5rem;">
<span class="chip">Layout <b>{'Multi-Column Gutter' if cols_ok else 'Single-Column'}</b></span>
<span class="chip">Total Words <b>{total_words}</b></span>
<span class="chip">Sections <b>{len(sections_detected)} Found</b></span>
<span class="chip">Links <b>{len(parsed.hyperlinks)} Total</b></span>
</div>
<div>
<span class="chip">Bullets <b>{total_bullets}</b></span>
<span class="chip">Metrics <b>{metrics_count} ({metric_density_pct:.0f}%)</b></span>
<span class="chip">Campus Entities <b>{len(report.entities_found)}</b></span>
</div>
</div>"""
    st.markdown(diag_html, unsafe_allow_html=True)

with right:
    rows = ""
    for comp, data in sorted(report.component_scores.items(), key=lambda kv: -kv[1]["weight"]):
        if data["weight"] == 0:
            continue
        v = data["score"]
        rows += (
            f'<div class="comp-row">'
            f'<div class="comp-head"><span class="comp-name">{comp.replace("_", " ").title()}</span>'
            f'<span class="comp-val">{v:.0f} / 100 &nbsp;·&nbsp; {data["contribution"]:.0f} of {data["weight"]} pts</span></div>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{min(100, v):.0f}%;background:{bar_color(v)};"></div></div>'
            f'</div>')
    st.markdown(f'<div class="card"><div class="card-title">Component Breakdown ({track})</div>{rows}</div>',
                unsafe_allow_html=True)


# =============================================================================
# 3. INTERACTIVE TABS: DIAGNOSTICS, FULL DETAILS, LINE FIXES, RAW TEXT
# =============================================================================
t1, t2, t3, t4 = st.tabs([
    "Strengths & Critical Gaps",
    "Full Candidate Resume Details",
    "Line-by-Line Analysis",
    "Extracted Text Stream"
])

with t1:
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        items = "".join(
            f'<div class="li"><span class="mark" style="color:{GREEN};">✓</span><span>{s}</span></div>'
            for s in report.strengths[:4])
        st.markdown(f'<div class="card"><div class="card-title">Top Profile Strengths</div>{items}</div>',
                    unsafe_allow_html=True)

    with c2:
        if report.critical_missing:
            items = "".join(
                f'<div class="li"><span class="mark" style="color:{RED};">!</span><span>{m}</span></div>'
                for m in report.critical_missing)
        else:
            items = f'<div style="color:{SLATE};font-size:0.88rem;">No critical disqualifying gaps detected for this track.</div>'
        st.markdown(f'<div class="card"><div class="card-title">Critical Missing Elements</div>{items}</div>',
                    unsafe_allow_html=True)

    # Penalties Applied breakdown
    if report.penalties_applied:
        p_html = "".join(
            f'<div class="li"><span class="mark" style="color:{RED};">-{p["points"]} pts</span>'
            f'<span><b>{p["rule"].replace("_", " ").title()}</b>: {p["description"]}</span></div>'
            for p in report.penalties_applied
        )
        st.markdown(f'<div class="card" style="border-left:3px solid {RED};"><div class="card-title">Track Penalties Applied</div>{p_html}</div>', unsafe_allow_html=True)


with t2:
    st.markdown('<div class="card-title" style="margin-top:0.4rem;">Complete Candidate Breakdown from Resume</div>', unsafe_allow_html=True)
    
    # Candidate Identity Overview Card
    roll_field = f"<div><b>Roll Number:</b> {profile['roll']}</div>" if profile['roll'] != "Not detected" else ""
    branch_field = "Circuital Branch (CSE/EE/MTH/SDS)" if profile["is_circuital"] else "Core / Applied Sciences"
    
    id_html = f"""<div class="card" style="border-left:3px solid {BLUE};">
<div class="card-title">Candidate Identity & Academic Standing</div>
<div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(220px, 1fr));gap:0.75rem;font-size:0.88rem;">
<div><b>Full Name:</b> {profile['name']}</div>
{roll_field}
<div><b>Email ID:</b> {profile['email']}</div>
<div><b>Contact Phone:</b> {profile['phone']}</div>
<div><b>Department:</b> {profile['dept']}</div>
<div><b>Programme:</b> {profile['programme']}</div>
<div><b>Current Year:</b> {profile['year']}</div>
<div><b>Cumulative CPI:</b> {cpi_display}</div>
<div><b>Branch Classification:</b> {branch_field}</div>
<div><b>GitHub Profile:</b> {profile['github'] if profile['github'] else 'None detected'}</div>
<div><b>LinkedIn Profile:</b> {profile['linkedin'] if profile['linkedin'] else 'None detected'}</div>
<div><b>CP Profile:</b> {profile['cp_profile'] if profile['cp_profile'] else 'None detected'}</div>
</div>
</div>"""
    st.markdown(id_html, unsafe_allow_html=True)

    col_a, col_b = st.columns(2, gap="medium")
    
    with col_a:
        # Technical Skills Extracted
        skills_lines = parsed.sections.get("Skills", [])
        if skills_lines:
            skills_content = "<br>".join(f"• {sl}" for sl in skills_lines)
        else:
            skills_content = "<i>No formal Skills section detected.</i>"
        st.markdown(f'<div class="card"><div class="card-title">Technical Skills & Tooling</div><div style="font-size:0.88rem;line-height:1.6;">{skills_content}</div></div>', unsafe_allow_html=True)

        # Relevant Coursework Extracted
        cw_lines = parsed.sections.get("Coursework", [])
        if cw_lines:
            cw_html = "<br>".join(f"• {cl}" for cl in cw_lines)
        else:
            cw_html = "<i>No explicit Coursework section listed.</i>"
        st.markdown(f'<div class="card"><div class="card-title">Coursework & Academic Curriculum</div><div style="font-size:0.88rem;line-height:1.6;">{cw_html}</div></div>', unsafe_allow_html=True)

        # Scholastic Achievements
        ach_lines = parsed.sections.get("Achievements", [])
        if ach_lines:
            ach_content = "<br>".join(f"• {al}" for al in ach_lines)
        else:
            ach_content = "<i>No formal Achievements section detected.</i>"
        st.markdown(f'<div class="card"><div class="card-title">Scholastic Achievements & Honors</div><div style="font-size:0.88rem;line-height:1.6;">{ach_content}</div></div>', unsafe_allow_html=True)

    with col_b:
        # Positions of Responsibility Breakdown
        if report.por_matches:
            por_html = ""
            for pm in report.por_matches:
                if pm["match"]:
                    m = pm["match"]
                    smode = m.get("selection_mode", "Appointed")
                    por_html += (
                        f'<div class="li"><span class="mark" style="color:{BLUE};">★</span>'
                        f'<span><b>{pm["line"]}</b><br>'
                        f'<span style="color:{SLATE};font-size:0.8rem;">{m["por"]} &nbsp;·&nbsp; {m["tier"]} Tier &nbsp;·&nbsp; Mode: <b>{smode}</b> &nbsp;·&nbsp; Rating: <b>{m["rating"]}/10</b></span></span></div>'
                    )
            if not por_html:
                por_html = "<i>No confident PoR catalogue matches found.</i>"
        else:
            por_html = "<i>No Positions of Responsibility section listed.</i>"
        st.markdown(f'<div class="card"><div class="card-title">Positions of Responsibility & Leadership</div>{por_html}</div>', unsafe_allow_html=True)

        # Projects Breakdown
        proj_bullets = parsed.bullets.get("Projects", [])
        proj_lines = parsed.sections.get("Projects", [])
        
        if proj_bullets:
            proj_content = "<div style='max-height:280px;overflow-y:auto;font-size:0.86rem;line-height:1.6;'>" + "<br>".join(f"• {b}" for b in proj_bullets) + "</div>"
        elif proj_lines:
            proj_content = "<div style='max-height:280px;overflow-y:auto;font-size:0.86rem;line-height:1.6;'>" + "<br>".join(f"• {pl}" for pl in proj_lines) + "</div>"
        else:
            proj_content = "<i>No formal Projects section detected.</i>"
        st.markdown(f'<div class="card"><div class="card-title">Projects & Technical Initiatives</div>{proj_content}</div>', unsafe_allow_html=True)


with t3:
    if report.formatting_fixes:
        fixes_html = ""
        for fix in report.formatting_fixes[:15]:
            issues = "".join(f'<div class="fix-issue">{i}</div>' for i in fix["issues"])
            bullet = fix["bullet"][:180] + ("…" if len(fix["bullet"]) > 180 else "")
            rewrite = fix.get("suggested_rewrite")
            rewrite_html = (
                f'<div style="margin-top:0.55rem;padding-top:0.5rem;border-top:1px dashed {LINE};">'
                f'<span style="font-size:0.68rem;font-weight:700;letter-spacing:0.05em;'
                f'text-transform:uppercase;color:{GREEN};">Suggested rewrite</span>'
                f'<div style="font-size:0.86rem;color:{INK};margin-top:0.2rem;">{rewrite}</div></div>'
                if rewrite else "")
            fixes_html += (
                f'<div class="fix"><div class="fix-sec">{fix["section"]}</div>'
                f'<div class="fix-bullet">“{bullet}”</div>{issues}{rewrite_html}</div>')
        st.markdown(f'<div class="card"><div class="card-title">Line-by-Line Bullet Analysis</div>{fixes_html}</div>',
                    unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="card"><div class="card-title">Line-by-Line Bullet Analysis</div>'
                    f'<div style="color:{GREEN};font-size:0.88rem;">No actionable bullet phrasing issues detected. All bullets open with strong action verbs and maintain active outcome phrasing.</div></div>',
                    unsafe_allow_html=True)


with t4:
    st.markdown('<div class="card-title" style="margin-top:0.4rem;">Clean Visual Reading Order Text Stream</div>', unsafe_allow_html=True)
    st.text_area("Extracted Resume Text", parsed.raw_text, height=450)
