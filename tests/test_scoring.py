"""Tests: transparent signal scoring rubric."""

from strategy_engine.scoring import DEFAULT_WEIGHTS, ScoreCard


def test_default_weights_sum_to_100():
    assert sum(DEFAULT_WEIGHTS.values()) == 100


def test_award_fraction_and_total():
    card = ScoreCard()
    card.award("trend", 1.0, "full trend")  # 20
    card.award("momentum", 0.5, "half")  # 7.5
    assert card.total == 28  # round(27.5)


def test_total_capped_at_100():
    card = ScoreCard()
    for name in DEFAULT_WEIGHTS:
        card.award(name, 1.0, "max")
    # Extra bogus award cannot exceed 100.
    card.award("trend", 1.0, "again")
    assert card.total == 100


def test_unknown_component_scores_zero():
    card = ScoreCard()
    card.award("does_not_exist", 1.0, "typo")
    assert card.total == 0


def test_bands():
    def band_for(points):
        card = ScoreCard(weights={"x": 100})
        card.award("x", points / 100, "")
        return card.band()

    assert band_for(10) == "weak"
    assert band_for(50) == "developing"
    assert band_for(70) == "moderate"
    assert band_for(80) == "strong"
    assert band_for(95) == "very_strong"


def test_to_dict_has_disclaimer():
    d = ScoreCard().to_dict()
    assert "NOT a probability" in d["disclaimer"]
