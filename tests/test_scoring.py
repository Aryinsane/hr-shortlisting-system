"""tests/test_scoring.py — Scoring logic unit tests."""
import pytest
from app.schemas.score_schema import CandidateScore, DimensionScore, RankedCandidate
from app.agents.ranking_agent import RankingAgent


def make_dimension(key, score, weight):
    return DimensionScore(
        dimension=key, score=score, weight=weight,
        weighted_score=round(score * weight, 2),
        justification=f"Test justification for {key}"
    )


def make_score(candidate_id, skills=80, experience=70, education=60, projects=75, comm=65):
    sm = make_dimension("skills_match", skills, 0.30)
    er = make_dimension("experience_relevance", experience, 0.25)
    ec = make_dimension("education_certifications", education, 0.15)
    pp = make_dimension("projects_portfolio", projects, 0.20)
    cq = make_dimension("communication_quality", comm, 0.10)
    total = sm.weighted_score + er.weighted_score + ec.weighted_score + pp.weighted_score + cq.weighted_score
    rec = "Hire" if total >= 65 else "Review" if total >= 50 else "No-Hire"
    return CandidateScore(
        candidate_id=candidate_id,
        candidate_name=f"Candidate {candidate_id}",
        skills_match=sm, experience_relevance=er,
        education_certifications=ec, projects_portfolio=pp,
        communication_quality=cq,
        total_score=round(total, 2),
        recommendation=rec,
        overall_summary="Test summary",
    )


class TestScoringWeights:
    def test_weights_sum_to_one(self):
        weights = [0.30, 0.25, 0.15, 0.20, 0.10]
        assert abs(sum(weights) - 1.0) < 0.001

    def test_dimension_score_weighted(self):
        dim = make_dimension("skills_match", 80, 0.30)
        assert dim.weighted_score == 24.0

    def test_total_score_correct(self):
        score = make_score("c001", skills=80, experience=80, education=80, projects=80, comm=80)
        assert score.total_score == 80.0

    def test_hire_recommendation(self):
        score = make_score("c002", skills=90, experience=80, education=75, projects=85, comm=70)
        assert score.total_score >= 65
        assert score.recommendation == "Hire"

    def test_nohire_recommendation(self):
        score = make_score("c003", skills=30, experience=20, education=40, projects=25, comm=30)
        assert score.total_score < 50
        assert score.recommendation == "No-Hire"

    def test_review_recommendation(self):
        score = make_score("c004", skills=55, experience=55, education=50, projects=55, comm=50)
        assert 50 <= score.total_score < 65
        assert score.recommendation == "Review"

    def test_pydantic_validates_score_bounds(self):
        with pytest.raises(Exception):
            DimensionScore(dimension="x", score=150, weight=0.3, weighted_score=45, justification="test")


class TestRankingAgent:
    def setup_method(self):
        self.agent = RankingAgent()

    def test_ranking_order(self):
        scores = [
            make_score("c_low", skills=40, experience=40, education=40, projects=40, comm=40),
            make_score("c_high", skills=90, experience=90, education=90, projects=90, comm=90),
            make_score("c_mid", skills=70, experience=70, education=70, projects=70, comm=70),
        ]
        ranked = self.agent.rank(scores)
        assert ranked[0].candidate_id == "c_high"
        assert ranked[-1].candidate_id == "c_low"

    def test_rank_numbers_sequential(self):
        scores = [make_score(f"c{i}") for i in range(5)]
        ranked = self.agent.rank(scores)
        assert [r.rank for r in ranked] == [1, 2, 3, 4, 5]

    def test_override_applied(self):
        scores = [
            make_score("c_low", skills=20, experience=20, education=20, projects=20, comm=20),
            make_score("c_high", skills=90, experience=90, education=90, projects=90, comm=90),
        ]
        overrides = {"c_low": {"new_score": 95.0, "new_recommendation": "Hire", "reason": "Exceptional culture fit"}}
        ranked = self.agent.rank(scores, overrides=overrides)
        assert ranked[0].candidate_id == "c_low"
        assert ranked[0].override_applied is True
        assert ranked[0].total_score == 95.0

    def test_empty_scores(self):
        ranked = self.agent.rank([])
        assert ranked == []

    def test_shortlist_filter(self):
        scores = [
            make_score("c_hire", skills=90, experience=90, education=90, projects=90, comm=90),
            make_score("c_nohire", skills=20, experience=20, education=20, projects=20, comm=20),
        ]
        ranked = self.agent.rank(scores)
        shortlist = self.agent.get_shortlist(ranked)
        assert all(r.recommendation == "Hire" for r in shortlist)
