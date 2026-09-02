"""
Test suite for the IITK Resume Diagnostic Engine.

Run with:  pytest tests/test_engine.py -v
(or:       python -m pytest tests/ -v   from the repo root)

Tests use the mock resumes in tests/mock_resumes/ — regenerate them from
the .html sources with wkhtmltopdf if you need to tweak a fixture:

    wkhtmltopdf --enable-local-file-access mock_sde.html mock_sde.pdf
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from engine import parse_resume, score_resume, TRACKS

FIXTURES = os.path.join(os.path.dirname(__file__), "mock_resumes")


def fixture(name):
    return os.path.join(FIXTURES, name)


# ---------------------------------------------------------------------
# Module A: PDF Parsing
# ---------------------------------------------------------------------

class TestPDFParsing:
    def test_single_column_resume_parses_all_sections(self):
        parsed = parse_resume(fixture("mock_sde.pdf"))
        expected_sections = {"Education", "Experience", "Projects",
                              "Positions of Responsibility", "Achievements",
                              "Coursework", "Skills"}
        assert expected_sections.issubset(set(parsed.sections.keys()))

    def test_two_column_resume_reading_order_is_column_major(self):
        """The classic multi-column-scramble failure mode: a naive parser would
        interleave 'EDUCATION' (left col) with 'POSITIONS OF RESPONSIBILITY' (right
        col) mid-line because they sit at the same vertical height. We assert the
        engine instead finishes the entire left column before starting the right."""
        parsed = parse_resume(fixture("mock_2col.pdf"))
        assert parsed.column_layout_detected is True
        lines = parsed.raw_text.split("\n")
        edu_idx = next(i for i, l in enumerate(lines) if "EDUCATION" in l)
        skills_idx = next(i for i, l in enumerate(lines) if "SKILLS" in l)
        por_idx = next(i for i, l in enumerate(lines) if "POSITIONS OF RESPONSIBILITY" in l)
        # Left column (Education, Skills, Coursework) must all precede the
        # right column (PoR, Projects, Achievements) in reading order.
        assert edu_idx < por_idx
        assert skills_idx < por_idx

    def test_cpi_extraction(self):
        parsed = parse_resume(fixture("mock_sde.pdf"))
        assert parsed.cpi == pytest.approx(8.7)

    def test_hyperlink_extraction(self):
        parsed = parse_resume(fixture("mock_sde.pdf"))
        urls = [l["url"] for l in parsed.hyperlinks]
        assert any("github.com" in u for u in urls)
        assert any("linkedin.com" in u for u in urls)

    def test_bullet_extraction_from_marked_lines(self):
        parsed = parse_resume(fixture("mock_sde.pdf"))
        assert len(parsed.bullets["Experience"]) == 3
        assert len(parsed.bullets["Projects"]) == 3

    def test_plaintext_github_not_counted_as_hyperlink(self):
        """A resume that pastes 'github.com/x' as plain text (no PDF link
        annotation) should NOT be credited with a real hyperlink — this is
        exactly the gap the engine should catch and flag to the student."""
        parsed = parse_resume(fixture("mock_quant_weak.pdf"))
        github_links = [l for l in parsed.hyperlinks if "github" in (l["url"] or "").lower()]
        assert len(github_links) == 0


# ---------------------------------------------------------------------
# Module B: NLP / Semantic Weighting
# ---------------------------------------------------------------------

class TestNLPEngine:
    def test_entity_recognition_finds_iitk_jargon(self):
        parsed = parse_resume(fixture("mock_sde.pdf"))
        report = score_resume(parsed, "SDE")
        assert "GSoC" in report.entities_found
        assert "Codeforces" in report.entities_found

    def test_impact_detection_flags_missing_metrics(self):
        from engine.nlp_engine import has_quantifiable_metric, analyze_bullet
        assert has_quantifiable_metric("Reduced latency by 45% using Redis caching") is True
        assert has_quantifiable_metric("Deployed application on Kubernetes cluster") is False
        b1 = analyze_bullet("Scaled infrastructure to handle 10k+ concurrent users")
        assert b1.has_metric is True
        b2 = analyze_bullet("Implemented user authentication with JWT")
        assert b2.has_metric is False

    def test_weak_verb_flagged(self):
        parsed = parse_resume(fixture("mock_sde.pdf"))
        report = score_resume(parsed, "SDE")
        weak_flagged = [f for f in report.formatting_fixes
                         if any("weak verb" in i for i in f["issues"])]
        assert any("Worked on the checkout" in f["bullet"] for f in weak_flagged)

    def test_por_matching_prefers_specific_over_generic_title(self):
        """Regression test for a real bug found during development: token-overlap
        matching without Jaccard normalization scored a short generic entry
        ('Council Secretary') higher than the correct, longer, specific one
        ('General Secretary (any Council)') purely because it had fewer tokens."""
        parsed = parse_resume(fixture("mock_sde.pdf"))
        report = score_resume(parsed, "SDE")
        gs_match = next(m for m in report.por_matches if "General Secretary" in m["line"])
        assert gs_match["match"] is not None
        assert gs_match["match"]["tier"] == "Apex"
        assert "General Secretary" in gs_match["match"]["por"]

    def test_por_no_duplicate_matches(self):
        parsed = parse_resume(fixture("mock_2col.pdf"))
        report = score_resume(parsed, "Management Consulting")
        lines = [m["line"] for m in report.por_matches]
        assert len(lines) == len(set(lines)), "PoR lines should not be matched twice"


# ---------------------------------------------------------------------
# Scoring / Role Baselines
# ---------------------------------------------------------------------

class TestScoring:
    @pytest.mark.parametrize("track", TRACKS)
    def test_all_tracks_produce_a_bounded_score(self, track):
        parsed = parse_resume(fixture("mock_sde.pdf"))
        report = score_resume(parsed, track)
        assert 0.0 <= report.overall_score <= 100.0

    def test_strong_sde_resume_scores_reasonably_high_on_sde_track(self):
        parsed = parse_resume(fixture("mock_sde.pdf"))
        report = score_resume(parsed, "SDE")
        # Threshold is 50 (not 60) after empirical recalibration against placed
        # resumes: component scoring was rescaled so scores track the real
        # placed distribution rather than an idealized quantify-everything bar.
        assert report.overall_score >= 50.0

    def test_weak_generic_resume_scores_low_on_quant_finance(self):
        parsed = parse_resume(fixture("mock_quant_weak.pdf"))
        report = score_resume(parsed, "Quant Finance")
        assert report.overall_score <= 35.0
        assert any("CPI" in p["description"] for p in report.penalties_applied)

    def test_weak_generic_resume_triggers_web_dev_penalty_on_core_engineering(self):
        parsed = parse_resume(fixture("mock_quant_weak.pdf"))
        report = score_resume(parsed, "Core Engineering")
        assert any(p["rule"] == "generic_web_dev_dominant" for p in report.penalties_applied)

    def test_score_shifts_dynamically_across_tracks_for_same_resume(self):
        """Same resume, different target track, must produce materially
        different scores — this is the PS's core 'Role-Targeted analysis'
        requirement (Section 5, Diagnostic Accuracy)."""
        parsed = parse_resume(fixture("mock_sde.pdf"))
        sde_score = score_resume(parsed, "SDE").overall_score
        quant_score = score_resume(parsed, "Quant Finance").overall_score
        assert abs(sde_score - quant_score) > 10.0

    def test_top_3_strengths_capped_at_three(self):
        parsed = parse_resume(fixture("mock_sde.pdf"))
        report = score_resume(parsed, "SDE")
        assert len(report.strengths) <= 3

    def test_consulting_resume_rewards_apex_por(self):
        parsed = parse_resume(fixture("mock_2col.pdf"))
        report = score_resume(parsed, "Management Consulting")
        # The mock's "President, Students' Gymkhana" matches an Apex-tier PoR;
        # the leadership component should reward it strongly.
        assert report.component_scores["por_leadership"]["score"] >= 60.0


# ---------------------------------------------------------------------
# Real-world resume regression tests (anonymized samples with permission)
# ---------------------------------------------------------------------

class TestRealResumes:
    """
    These are real SPO-style IITK resumes (not synthetic mocks) used to catch
    the kind of parsing failures mock fixtures don't surface: table-based
    Academic Qualifications blocks, "Objective/Approach/Results" structured
    project bullets, headings not covered by a fixed alias list, and PDF
    word-gluing from tight kerning.
    """

    def test_shantanu_resume_finds_all_expected_sections(self):
        parsed = parse_resume(fixture("real_shantanu.pdf"))
        expected = {"Education", "Achievements", "Experience", "Projects",
                    "Skills", "Coursework", "Extracurricular"}
        assert expected.issubset(set(parsed.sections.keys()))

    def test_shantanu_cpi_from_table_row(self):
        parsed = parse_resume(fixture("real_shantanu.pdf"))
        assert parsed.cpi == pytest.approx(8.9)

    def test_shantanu_no_word_gluing(self):
        parsed = parse_resume(fixture("real_shantanu.pdf"))
        assert "ReceivedAcademicExcellenceAward" not in parsed.raw_text
        assert "Received Academic Excellence Award" in parsed.raw_text

    def test_shantanu_objective_approach_results_bullets_captured(self):
        parsed = parse_resume(fixture("real_shantanu.pdf"))
        exp_bullets = " ".join(parsed.bullets.get("Experience", []))
        assert "multichannel fraud detection pipeline" in exp_bullets.lower()
        assert "unsupervised learning via isolation forest" in exp_bullets.lower()

    def test_harshvardhan_resume_finds_all_expected_sections(self):
        parsed = parse_resume(fixture("real_harshvardhan.pdf"))
        expected = {"Education", "Achievements", "Projects", "Skills",
                    "Positions of Responsibility", "Coursework", "Extracurricular"}
        assert expected.issubset(set(parsed.sections.keys()))

    def test_harshvardhan_cpi_from_table_row(self):
        parsed = parse_resume(fixture("real_harshvardhan.pdf"))
        assert parsed.cpi == pytest.approx(7.9)

    def test_harshvardhan_por_leadership_bullets_captured(self):
        parsed = parse_resume(fixture("real_harshvardhan.pdf"))
        por_bullets = " ".join(parsed.bullets.get("Positions of Responsibility", []))
        assert "budget of over 80k inr" in por_bullets.lower()
        assert "200%" in por_bullets

    def test_no_project_title_fragmented_into_its_own_section(self):
        """Regression test: an earlier version of the font-based heading
        heuristic treated any short bold phrase (same size as body text) as
        a new section, which fragmented bolded project/company titles like
        'Personal Portfolio Website' into their own top-level sections."""
        parsed = parse_resume(fixture("mock_quant_weak.pdf"))
        assert "Personal Portfolio Website" not in parsed.sections.keys()
        assert "Todo List App" not in parsed.sections.keys()
        assert len(parsed.bullets.get("Projects", [])) >= 2


# ---------------------------------------------------------------------
# Calibration regression tests (lock in empirically-tuned behavior)
# ---------------------------------------------------------------------

class TestCalibration:
    """
    These lock in the behavior established by calibrating against ~74 real
    placed IITK resumes (see CALIBRATION.md). If someone later changes a
    weight, threshold, or coverage target, these tests flag whether the change
    moved the scoring away from the placed-resume-anchored calibration.
    """

    def test_cpi_thresholds_ordered_by_track_selectivity(self):
        from engine.data.role_baselines import ROLE_BASELINES
        # Quant is the most CPI-selective track in the placed data; its "good"
        # threshold must be the highest of the four.
        goods = {t: ROLE_BASELINES[t]["cpi_threshold"]["good"] for t in ROLE_BASELINES}
        assert goods["Quant Finance"] == max(goods.values())

    def test_list_sections_excluded_from_impact_analysis(self):
        """Skills/Coursework list lines must not count as achievement bullets;
        otherwise impact-density and action-verb scores are diluted toward 0."""
        parsed = parse_resume(fixture("mock_sde.pdf"))
        report = score_resume(parsed, "SDE")
        # No formatting fix should be raised against a Skills/Coursework line.
        fix_sections = {f["section"] for f in report.formatting_fixes}
        assert "Skills" not in fix_sections
        assert "Coursework" not in fix_sections

    def test_keyword_word_boundary_no_false_positive(self):
        """'cad' must not match inside 'academic' — a calibration bug that
        made every resume look CAD-proficient."""
        from engine.nlp_engine import _keyword_present
        assert not _keyword_present("cad", "strong academic record")
        assert _keyword_present("cad", "used cad software for design")

    def test_impact_density_rewards_realistic_quantification(self):
        """A resume quantifying ~20% of bullets should score well on impact
        density, not be punished for not quantifying 100%."""
        from engine.scoring import _impact_density
        from engine.nlp_engine import BulletAnalysis
        bullets = [BulletAnalysis(text="x", has_metric=(i < 2)) for i in range(10)]  # 20% density
        score, _, _ = _impact_density(bullets)
        assert score >= 80.0


# ---------------------------------------------------------------------
# Hybrid LLM feedback layer (mocked — no real API calls)
# ---------------------------------------------------------------------

class TestHybridFeedback:
    """
    The hybrid layer must (a) never alter the numeric score, and (b) degrade
    gracefully to rule-based text when the LLM is off or errors. These tests
    mock the Anthropic client so they run fully offline and deterministically.
    """

    def _install_fake_anthropic(self, monkeypatch, rewrite_json=None, summary_text=None):
        import types
        fake = types.ModuleType("anthropic")

        class FakeBlock:
            def __init__(self, text): self.type = "text"; self.text = text

        class FakeResp:
            def __init__(self, text): self.content = [FakeBlock(text)]

        class FakeMessages:
            def create(self, model, max_tokens, messages):
                prompt = messages[0]["content"]
                if "array of objects" in prompt:
                    return FakeResp(rewrite_json or "[]")
                return FakeResp(summary_text or "")

        class FakeAnthropic:
            def __init__(self, api_key=None): self.messages = FakeMessages()

        fake.Anthropic = FakeAnthropic
        monkeypatch.setitem(sys.modules, "anthropic", fake)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("RESUME_ENGINE_USE_LLM", "1")

    def test_llm_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv("RESUME_ENGINE_USE_LLM", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        from engine.llm_feedback import llm_enabled
        assert llm_enabled() is False

    def test_score_identical_with_and_without_llm(self, monkeypatch):
        parsed = parse_resume(fixture("mock_sde.pdf"))
        baseline_score = score_resume(parsed, "SDE", use_llm=False).overall_score

        self._install_fake_anthropic(
            monkeypatch,
            rewrite_json='[{"i":0,"rewrite":"Engineered X, cutting Y by [X]%."}]',
            summary_text="Solid profile.")
        hybrid_score = score_resume(parsed, "SDE", use_llm=True).overall_score
        assert hybrid_score == baseline_score

    def test_hybrid_adds_rewrite_and_summary(self, monkeypatch):
        self._install_fake_anthropic(
            monkeypatch,
            rewrite_json='[{"i":0,"rewrite":"Engineered checkout tests, cutting defects by [X]%."}]',
            summary_text="Strong SDE profile; quantify a few more bullets.")
        parsed = parse_resume(fixture("mock_sde.pdf"))
        report = score_resume(parsed, "SDE", use_llm=True)
        assert report.llm_used is True
        assert report.summary.startswith("Strong SDE profile")
        assert any(f.get("suggested_rewrite") for f in report.formatting_fixes)

    def test_malformed_llm_json_falls_back_gracefully(self, monkeypatch):
        self._install_fake_anthropic(
            monkeypatch, rewrite_json="not valid json at all", summary_text="")
        parsed = parse_resume(fixture("mock_sde.pdf"))
        report = score_resume(parsed, "SDE", use_llm=True)
        # No rewrites attached, but scoring and rule-based issues still intact.
        assert not any(f.get("suggested_rewrite") for f in report.formatting_fixes)
        assert all("issues" in f for f in report.formatting_fixes)

    def test_use_llm_false_forces_rule_based(self, monkeypatch):
        self._install_fake_anthropic(
            monkeypatch, rewrite_json='[{"i":0,"rewrite":"X"}]', summary_text="Y")
        parsed = parse_resume(fixture("mock_sde.pdf"))
        report = score_resume(parsed, "SDE", use_llm=False)
        assert report.summary == ""
        assert report.llm_used is False


# ---------------------------------------------------------------------
# Mentorship & Elected Position Weightage Tests
# ---------------------------------------------------------------------

class TestElectedAndMentorshipLeadership:
    def test_elected_position_receives_significant_boost(self):
        from engine.data.por_ratings import PoRCatalogue
        from engine.scoring import _por_subscore
        from engine.nlp_engine import match_por_lines
        
        # Test elected role: Senator (Elected by batch)
        lines = ["Senator, Students' Senate"]
        matches = match_por_lines(lines)
        score_elected, is_elected, is_mentor = _por_subscore(matches, weight_multiplier=1.0)
        assert is_elected is True
        # Base rating for Senator is 7.0 -> base raw 70 -> with elected boost min(100, 70*1.3+10) = 100
        assert score_elected >= 90.0

    def test_mentorship_role_receives_dedicated_boost(self):
        from engine.scoring import _por_subscore
        from engine.nlp_engine import match_por_lines
        
        # Test mentorship role: Academic Departmental Mentor
        lines = ["Academic Departmental Mentor | Academics & Career Council"]
        matches = match_por_lines(lines)
        score_mentor, is_elected, is_mentor = _por_subscore(matches, weight_multiplier=1.0)
        assert is_mentor is True
        # Base rating for Entry mentor is 3.0 (30 pts) -> with mentorship boost min(100, 30*1.2+8) = 44 pts
        assert score_mentor > 40.0

    def test_mentorship_action_verb_classified_as_strong(self):
        from engine.data.action_verbs import classify_verb
        assert classify_verb("Mentored") == "strong"
        assert classify_verb("Guided") == "strong"
        assert classify_verb("Tutored") == "strong"


# ---------------------------------------------------------------------
# Circuital Boot-Start & Council Coordinator Strategic Edges Tests
# ---------------------------------------------------------------------

class TestCircuitalAndCouncilCoordinatorEdges:
    def test_circuital_branch_detection(self):
        from engine.scoring import _detect_circuital_branch
        assert _detect_circuital_branch("Department of Computer Science and Engineering, IIT Kanpur") is True
        assert _detect_circuital_branch("B.Tech in Electrical Engineering (EE)") is True
        assert _detect_circuital_branch("BS Mathematics and Scientific Computing (MnC)") is True
        assert _detect_circuital_branch("Statistics and Data Science (SDS)") is True
        assert _detect_circuital_branch("Mechanical Engineering") is False

    def test_snt_coordinator_detection(self):
        from engine.scoring import _detect_snt_coordinator
        from engine.nlp_engine import match_por_lines
        
        # Test Programming Club Coordinator
        lines = ["Coordinator | Programming Club, Science and Technology Council"]
        matches = match_por_lines(lines)
        assert _detect_snt_coordinator("Coordinator, Programming Club", matches) is True
        
        # Test Team Vision Lead
        lines2 = ["Team Lead | Team Vision, SnT Council"]
        matches2 = match_por_lines(lines2)
        assert _detect_snt_coordinator("Team Lead, Team Vision", matches2) is True

    def test_other_council_coordinator_detection(self):
        from engine.scoring import _detect_other_council_coordinator
        from engine.nlp_engine import match_por_lines
        
        # Test CDW / AnC Wing Manager
        lines = ["Wing Manager | Career Development Wing, Academics and Career Council"]
        matches = match_por_lines(lines)
        has_coord, cname = _detect_other_council_coordinator("Wing Manager, CDW", matches)
        assert has_coord is True
        assert "AnC" in cname or "Career" in cname


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
