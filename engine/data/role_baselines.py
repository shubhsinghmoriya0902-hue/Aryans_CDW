"""
Role-Specific Evaluation Baselines (Problem Statement, Section 3).

Each track defines:
- component_weights: how the 100-point Profile Match Score is split across
  scoring components (must sum to 100).
- keywords: terms/tech that should appear in Projects/Experience/Skills;
  weighted by importance (1.0 = core, 0.5 = nice-to-have).
- coursework_keywords: courses that matter for this track.
- cpi_threshold: (good, excellent) CPI cutoffs used for the CPI sub-score.
- por_weight_multiplier: how much leadership PoRs matter for this track.
- penalties: rule -> (description, point deduction) triggered by scoring.py.
"""

TRACKS = ["SDE", "Quant Finance", "Management Consulting", "Core Engineering"]

ROLE_BASELINES = {
    "SDE": {
        "display_name": "Software Engineering (SDE)",
        "component_weights": {
            "cpi": 8,
            "coursework": 10,
            "projects": 32,
            "competitive_programming": 15,
            "por_leadership": 8,
            "impact_density": 15,
            "action_verbs": 7,
            "links_formatting": 5,
        },
        "keywords": {
            "c++": 1.0, "java": 1.0, "python": 0.85, "golang": 0.9, "rust": 0.8,
            "dsa": 1.0, "data structures": 1.0, "algorithms": 1.0,
            "system design": 0.95, "distributed systems": 0.95, "multithreading": 0.9, "concurrency": 0.9,
            "socket programming": 0.85, "client-server": 0.8, "grpc": 0.85, "rest api": 0.8,
            "react": 0.65, "node": 0.65, "django": 0.55, "flask": 0.55, "fastapi": 0.7,
            "sql": 0.6, "postgresql": 0.8, "database": 0.55, "redis": 0.75, "api": 0.6, "docker": 0.8,
            "kubernetes": 0.85, "aws": 0.75, "microservices": 0.85, "ci/cd": 0.75,
            "github": 0.7, "open source": 0.85, "gsoc": 1.0,
            "html": 0.4, "css": 0.4,
        },
        "coursework_keywords": {
            "data structures and algorithms": 1.0, "dsa": 1.0, "eso207": 1.0, "cs210": 1.0,
            "operating systems": 0.9, "cs330": 0.9,
            "computer networks": 0.8, "cs425": 0.8,
            "database management systems": 0.8, "dbms": 0.8, "cs315": 0.8,
            "compilers": 0.7, "cs335": 0.7,
            "distributed systems": 0.8, "computer organization": 0.7, "cs220": 0.7,
            "machine learning": 0.8, "cs771": 0.8, "artificial intelligence": 0.7,
            "algorithms": 0.9, "linear algebra": 0.7, "probability": 0.7,
        },
        # Calibrated to 42 placed SDE resumes: CPI median 8.30, p25 7.65, min 6.50.
        # "good" set near the placed p25 so a typical placed candidate clears it.
        "cpi_threshold": {"good": 7.65, "excellent": 8.80},
        # Coverage targets = placed p75 of the weighted keyword pool (full marks
        # at ~p75 so a top-quartile-realistic resume can max the component).
        "keyword_target": 0.21,
        "coursework_target": 0.12,
        "por_weight_multiplier": 0.7,
        "penalties": {
            "missing_github": ("No GitHub/portfolio link found for a technical profile", 8),
            "no_recognized_language": ("No mainstream language (C++/Java/Python/Go) detected in projects", 10),
            "generic_project_no_impact": ("Projects lack any quantifiable impact metric", 6),
        },
    },
    "Quant Finance": {
        "display_name": "Quantitative Finance",
        "component_weights": {
            "cpi": 28,
            "coursework": 22,
            "projects": 18,
            "competitive_programming": 12,
            "por_leadership": 1,
            "impact_density": 10,
            "action_verbs": 4,
            "links_formatting": 5,
        },
        "keywords": {
            "probability": 1.0, "stochastic calculus": 1.0, "statistics": 1.0,
            "linear algebra": 0.95, "optimization": 0.85, "machine learning": 0.65,
            "time series": 0.95, "monte carlo": 0.95, "black-scholes": 0.95,
            "quantitative": 1.0, "c++": 0.9, "python": 0.8, "r programming": 0.65,
            "backtesting": 0.85, "algorithmic trading": 0.95, "derivatives": 0.85,
            "risk management": 0.8, "numerical analysis": 0.9, "krylov": 0.9,
            "sparse matrix": 0.85, "bayesian": 0.85, "statistical arbitrage": 0.9,
            "kaggle": 0.55,
        },
        "coursework_keywords": {
            "probability": 1.0, "stochastic calculus": 1.0, "real analysis": 0.9,
            "linear algebra": 1.0, "measure theory": 0.8, "statistics": 1.0,
            "numerical methods": 0.8, "convex optimization": 0.8, "time series": 0.9,
            "mathematical finance": 0.9, "mth101": 0.7, "mth102": 0.7, "mth415": 0.9,
            "sds201": 0.9, "statistical inference": 0.8, "algorithms": 0.8, "dsa": 0.8,
        },
        # Calibrated to 17 placed Quant resumes: CPI median 8.80, p25 8.40, p75 9.20.
        # Quant is the most CPI-sensitive track in the placed data —
        # nearly all cleared 8.5+ — so "good" sits higher here than any other track.
        "cpi_threshold": {"good": 8.40, "excellent": 9.20},
        "keyword_target": 0.15,
        "coursework_target": 0.12,
        "por_weight_multiplier": 0.2,
        "penalties": {
            "low_cpi": ("CPI below the competitive threshold for quant roles", 12),
            "no_math_project": ("No math/stat-heavy project or coursework signal found", 10),
            "no_algorithmic_signal": ("No competitive programming / algorithmic proficiency signal", 6),
        },
    },
    "Management Consulting": {
        "display_name": "Management Consulting",
        "component_weights": {
            "cpi": 10,
            "coursework": 5,
            "projects": 15,
            "competitive_programming": 0,
            "por_leadership": 30,
            "impact_density": 20,
            "action_verbs": 12,
            "links_formatting": 8,
        },
        "keywords": {
            "case study": 0.85, "consulting": 1.0, "market research": 0.85,
            "business analysis": 0.9, "strategy": 0.95, "operations": 0.75,
            "revenue": 0.95, "cost reduction": 0.95, "stakeholder": 0.8,
            "market entry": 0.95, "unit economics": 0.9, "due diligence": 0.9,
            "growth": 0.75, "client": 0.65, "presentation": 0.6, "excel": 0.5, "powerpoint": 0.5,
        },
        "coursework_keywords": {
            "economics": 1.0, "eco101": 0.9, "eco201": 0.9,
            "management": 1.0, "principles of management": 1.0, "mba600": 0.9,
            "game theory": 0.8, "operations research": 0.8, "finance": 0.8,
            "corporate finance": 0.8, "marketing": 0.7, "microeconomics": 0.8,
            "macroeconomics": 0.8, "business analysis": 0.8,
        },
        # Calibrated to 19 placed Consulting resumes: CPI median 8.70, p25 8.55, min 8.00.
        # Consulting candidates consistently have solid CPI + heavy leadership PoRs.
        "cpi_threshold": {"good": 8.00, "excellent": 8.85},
        # Consulting resumes rarely list a formal Coursework section (only 18%
        # of placed did), so coursework carries little weight and an easy target.
        "keyword_target": 0.29,
        "coursework_target": 0.12,
        "por_weight_multiplier": 1.5,
        "penalties": {
            "no_leadership_por": ("No significant (Mid-tier or above) Position of Responsibility found", 15),
            "no_business_impact_metric": ("Bullet points lack business-impact metrics (revenue, %, cost, users)", 10),
            "poor_bullet_formatting": ("Bullet points read as unstructured paragraphs, not concise impact statements", 6),
        },
    },
    "Core Engineering": {
        "display_name": "Core Engineering",
        "component_weights": {
            "cpi": 12,
            "coursework": 18,
            "projects": 25,
            "competitive_programming": 0,
            "por_leadership": 6,
            "impact_density": 14,
            "action_verbs": 7,
            "links_formatting": 5,
            "research_publications": 13,
        },
        "keywords": {
            "surge": 1.0, "matlab": 0.9, "cad": 0.85, "solidworks": 0.85,
            "ansys": 0.9, "autocad": 0.65, "simulation": 0.85, "fea": 0.9,
            "cfd": 0.9, "control systems": 0.85, "embedded systems": 0.85,
            "vlsi": 0.95, "verilog": 0.9, "fpga": 0.9, "robotics": 0.85,
            "ros": 0.9, "gazebo": 0.85, "signal processing": 0.85, "thermodynamics": 0.65,
            "publication": 1.0, "research paper": 0.95, "conference": 0.7,
            "patent": 0.95,
        },
        "coursework_keywords": {
            "core elective": 0.8, "thermodynamics": 0.9, "fluid mechanics": 0.9,
            "solid mechanics": 0.9, "heat transfer": 0.9, "control systems": 0.9,
            "vlsi design": 0.9, "signal processing": 0.8, "microelectronics": 0.8,
            "material science": 0.7, "manufacturing processes": 0.8,
            "finite element": 0.8, "fea": 0.8, "cfd": 0.8,
            "aerodynamics": 0.8, "circuit theory": 0.8, "power systems": 0.8,
        },
        # Calibrated to 10 placed Core resumes: CPI median 8.15, p25 7.55, p75 8.55.
        "cpi_threshold": {"good": 7.55, "excellent": 8.60},
        # Core keyword hits are sparse in the placed data (p75 only ~0.08) —
        # the keyword pool is broad and few candidates hit many terms. A low
        # target reflects that, but is floored at 0.12 so the component isn't
        # trivially maxed by one lucky keyword.
        "keyword_target": 0.12,
        "coursework_target": 0.10,
        "por_weight_multiplier": 0.5,
        "penalties": {
            "generic_web_dev_dominant": ("Generic web-dev projects dominate space that should showcase core-domain work", 12),
            "no_surge_or_core_internship": ("No SURGE/core-domain internship or research experience found", 8),
            "missing_core_electives": ("No recognizable core-domain elective coursework listed", 8),
        },
    },
}
