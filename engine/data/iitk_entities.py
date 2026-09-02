"""
IITK-specific jargon and entity list used for Entity Recognition (Module B).

Each entity maps to a category so the scoring engine can reward resumes
that correctly reference IITK-specific programs, bodies, and terminology
that a generic (non-IITK-aware) resume parser would not understand.
"""

# category -> list of (canonical_name, [regex-safe aliases/patterns])
IITK_ENTITIES = {
    "academic": [
        ("CPI", [r"\bCPI\b"]),
        ("SPI", [r"\bSPI\b"]),
        ("DUGC", [r"\bDUGC\b"]),
        ("DPGC", [r"\bDPGC\b"]),
    ],
    "research_internship": [
        ("SURGE", [r"\bSURGE\b"]),
        ("GSoC", [r"\bGSoC\b", r"Google Summer of Code"]),
        ("MITACS", [r"\bMITACS\b"]),
        ("DAAD WISE", [r"\bDAAD\s*WISE\b"]),
    ],
    "governance": [
        ("AnC Council", [r"\bAnC Council\b", r"Academics and Career Council", r"\bAnC\b"]),
        ("SnT Council", [r"\bSnT Council\b", r"\bSnT\b", r"Science and Technology Council"]),
        ("MnC Council", [r"\bMnC Council\b", r"Media and Cultural Council"]),
        ("GnS Council", [r"\bGnS Council\b", r"\bGnC Council\b", r"Games and Sports Council"]),
        ("Students' Senate", [r"Students'?\s*Senate", r"\bSenator\b"]),
        ("Gymkhana", [r"\bGymkhana\b"]),
        ("SPO", [r"\bSPO\b", r"Students'? Placement Office"]),
        ("Company Coordinator", [r"Company Coordinator", r"\bCoCo\b"]),
        ("Hall Executive Committee", [r"\bHEC\b", r"Hall Executive Committee", r"\bHall President\b"]),
        ("DoRA", [r"\bDoRA\b", r"Dean of Resource"]),
    ],
    "anc_wings": [
        ("UG Academics Wing", [r"UG Academics", r"UG Academics Wing"]),
        ("Research Wing", [r"Research Wing", r"AnC Research"]),
        ("International Relations Wing", [r"International Relations Wing", r"IR Wing"]),
        ("Career Development Wing", [r"Career Development Wing", r"\bCDW\b"]),
    ],
    "mnc_clubs_societies": [
        ("Book Club", [r"\bBook Club\b"]),
        ("Dance Club", [r"\bDance Club\b"]),
        ("Design and Animation Club", [r"Design and Animation Club", r"\bDnAC\b", r"\bDAC\b"]),
        ("Dramatics Club", [r"\bDramatics Club\b"]),
        ("Fine Arts Club", [r"\bFine Arts Club\b", r"\bFAC\b"]),
        ("Film Club", [r"\bFilm Club\b"]),
        ("Hindi Sahitya Sabha", [r"\bHindi Sahitya Sabha\b", r"\bHSS\b"]),
        ("Humour House", [r"\bHumour House\b"]),
        ("Music Club", [r"\bMusic Club\b"]),
        ("Photography Club", [r"\bPhotography Club\b", r"\bPhoto Club\b"]),
        ("Quiz Club", [r"\bQuiz Club\b"]),
        ("Anime Society", [r"\bAnime Society\b"]),
        ("Debate and Discussion Society", [r"Debate and Discussion", r"\bDDS\b", r"\bDebating Society\b"]),
        ("English Literary Society", [r"English Literary Society", r"\bELS\b"]),
        ("Student Film Society", [r"Student Film Society", r"\bSFS\b"]),
    ],
    "snt_clubs_societies_teams": [
        ("Aeromodelling Club", [r"Aeromodelling Club", r"Aeromodelling"]),
        ("Astronomy Club", [r"Astronomy Club", r"Astro Club"]),
        ("Electronics Club", [r"Electronics Club", r"E-Club"]),
        ("Finance & Analytics Club", [r"Finance & Analytics Club", r"Finance and Analytics Club", r"\bFnA\b", r"\bFAC\b"]),
        ("Programming Club", [r"Programming Club", r"\bP-?Club\b"]),
        ("Robotics Club", [r"Robotics Club", r"Robo Club"]),
        ("Speedcubing Club", [r"Speedcubing Club", r"Cube Club"]),
        ("Brain & Cognitive Society", [r"Brain & Cognitive Society", r"Brain and Cognitive", r"\bBCS\b"]),
        ("Descon Society", [r"\bDescon\b", r"Design and Construction"]),
        ("Game Development Society", [r"Game Development Society", r"Game Dev Society", r"\bGDS\b"]),
        ("IITK Consulting Group", [r"IITK Consulting Group", r"\bICG\b"]),
        ("Science Coffee House", [r"Science Coffee House", r"\bSCH\b"]),
        ("Aerial Robotics", [r"Aerial Robotics", r"Team Aerial"]),
        ("Team AUV", [r"\bAUV\b", r"Autonomous Underwater Vehicle"]),
        ("ERA", [r"\bERA\b", r"Equipe de Robotique Autonome"]),
        ("Team Humanoid", [r"\bHumanoid\b", r"Team Humanoid"]),
        ("IITK Motorsports", [r"IITK Motorsports", r"Motorsports", r"\bSAE\b"]),
        ("Team Vision", [r"Team Vision", r"Team VISION"]),
        ("Outreach & Connect Wing", [r"Outreach & Connect Wing", r"Outreach and Connect Wing"]),
        ("Web Division", [r"SnT Web Division", r"Web Division SnT"]),
    ],
    "gns_clubs_societies_teams": [
        ("Adventure Sports Club", [r"Adventure Sports Club"]),
        ("Archery Club", [r"Archery Club"]),
        ("Bicycling Club", [r"Bicycling Club"]),
        ("Card & Board Games Club", [r"Card & Board Games", r"Card and Board Games"]),
        ("Boxing Society", [r"Boxing Society"]),
        ("Chess Club", [r"Chess Club"]),
        ("Shooting Club", [r"Shooting Club"]),
        ("Skating Club", [r"Skating Club"]),
        ("Taekwondo Club", [r"Taekwondo Club", r"Taekwando"]),
        ("Ultimate Frisbee Society", [r"Ultimate Frisbee", r"Frisbee Society"]),
        ("E-sports Society", [r"E-sports Society", r"Esports Society"]),
        ("Athletics", [r"\bAthletics\b"]),
        ("Aquatics", [r"\bAquatics\b", r"\bSwimming\b"]),
        ("Badminton", [r"\bBadminton\b"]),
        ("Basketball", [r"\bBasketball\b"]),
        ("Cricket", [r"\bCricket\b"]),
        ("Football", [r"\bFootball\b"]),
        ("Hockey", [r"\bHockey\b"]),
        ("Lawn Tennis", [r"Lawn Tennis", r"\bTennis\b"]),
        ("Squash", [r"\bSquash\b"]),
        ("Table Tennis", [r"Table Tennis"]),
        ("Volleyball", [r"\bVolleyball\b"]),
        ("Weightlifting", [r"\bWeightlifting\b"]),
    ],
    "cells_bodies": [
        ("Community Welfare Cell", [r"Community Welfare Cell", r"\bCWC\b", r"\bPrakriti\b", r"\bPragati\b", r"\bPrayas\b", r"\bRaktarpan\b", r"\bUnmukt\b", r"Vivekananda Samiti"]),
        ("Election Commission", [r"Election Commission", r"\bEC\b", r"Chief Election Officer"]),
        ("Entrepreneurship Cell", [r"Entrepreneurship Cell", r"\bE-?Cell\b", r"E-Summit"]),
        ("Outreach Cell", [r"Outreach Cell"]),
        ("Public Policy And Opinion Cell", [r"Public Policy And Opinion Cell", r"Public Policy & Opinion Cell", r"\bPPOC\b"]),
        ("Vox Populi", [r"Vox Populi", r"\bVox\b"]),
    ],
    "festivals": [
        ("Antaragni", [r"\bAntaragni\b", r"Cultural Fest"]),
        ("Techkriti", [r"\bTechkriti\b", r"Technological Fest", r"Technical Fest"]),
        ("Udghosh", [r"\bUdghosh\b", r"Sports Fest"]),
    ],
    "competitive_programming": [
        ("Codeforces", [r"\bCodeforces\b", r"\bCF\b"]),
        ("Codechef", [r"\bCodeChef\b"]),
        ("LeetCode", [r"\bLeetCode\b"]),
        ("ICPC", [r"\bICPC\b"]),
        ("Kaggle", [r"\bKaggle\b"]),
    ],
    "sports_tech_teams": [
        ("Inter IIT Tech", [r"Inter\s*IIT\s*Tech", r"Inter-IIT\s*Tech", r"Inter\s*IIT\s*Technical"]),
        ("Inter IIT Sports", [r"Inter\s*IIT\s*Sports", r"Inter-IIT\s*Sports", r"Inter\s*IIT\s*Aquatics", r"Inter\s*IIT\s*Athletics", r"Inter\s*IIT\s*Cricket", r"Inter\s*IIT\s*Football", r"Inter\s*IIT\s*Badminton", r"Inter\s*IIT\s*Basketball", r"Inter\s*IIT\s*Tennis", r"Inter\s*IIT\s*Volleyball", r"Inter\s*IIT\s*Hockey", r"Inter\s*IIT\s*Squash", r"Inter\s*IIT\s*Weightlifting", r"Inter\s*IIT\s*Table\s*Tennis"]),
        ("Inter IIT Cult", [r"Inter\s*IIT\s*Cult", r"Inter-IIT\s*Cult", r"Inter\s*IIT\s*Cultural"]),
        ("Inter IIT", [r"Inter\s*IIT", r"Inter-IIT"]),
    ],
}

# Flattened list of (canonical, pattern) for quick iteration
def flatten_entities():
    flat = []
    for category, items in IITK_ENTITIES.items():
        for canonical, patterns in items:
            flat.append((category, canonical, patterns))
    return flat
