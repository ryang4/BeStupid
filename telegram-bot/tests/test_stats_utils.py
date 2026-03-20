"""Tests for v2.infra.stats_utils — pure statistical functions."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from v2.infra.stats_utils import compute_linear_trend, compute_streak, pearson_correlation


class TestPearsonCorrelation:
    def test_perfect_positive(self):
        pairs = [(1, 1), (2, 2), (3, 3), (4, 4)]
        r = pearson_correlation(pairs)
        assert r == 1.0

    def test_perfect_negative(self):
        pairs = [(1, 4), (2, 3), (3, 2), (4, 1)]
        r = pearson_correlation(pairs)
        assert r == -1.0

    def test_no_correlation(self):
        pairs = [(1, 2), (2, 4), (3, 1), (4, 3)]
        r = pearson_correlation(pairs)
        assert r is not None
        assert abs(r) < 0.5

    def test_too_few_pairs(self):
        assert pearson_correlation([(1, 2), (3, 4)]) is None
        assert pearson_correlation([]) is None

    def test_zero_variance(self):
        pairs = [(1, 5), (2, 5), (3, 5)]
        assert pearson_correlation(pairs) is None


class TestComputeLinearTrend:
    def test_positive_slope(self):
        data = [(0, 1), (1, 2), (2, 3), (3, 4)]
        result = compute_linear_trend(data)
        assert result["slope"] == 1.0
        assert result["r_squared"] == 1.0

    def test_negative_slope(self):
        data = [(0, 4), (1, 3), (2, 2), (3, 1)]
        result = compute_linear_trend(data)
        assert result["slope"] == -1.0

    def test_too_few_points(self):
        assert compute_linear_trend([(0, 1), (1, 2)]) == {}
        assert compute_linear_trend([]) == {}

    def test_flat_line(self):
        data = [(0, 5), (1, 5), (2, 5)]
        result = compute_linear_trend(data)
        assert result["slope"] == 0.0


class TestComputeStreak:
    def test_positive_streak(self):
        # Most recent first: all done
        result = compute_streak([True, True, True, False])
        assert result["current"] == 3
        assert result["direction"] == "positive"

    def test_negative_streak(self):
        result = compute_streak([False, False, True])
        assert result["current"] == -2
        assert result["direction"] == "negative"

    def test_longest_streak(self):
        result = compute_streak([True, True, False, True, True, True])
        assert result["longest"] == 3  # 3 consecutive in oldest section

    def test_empty(self):
        result = compute_streak([])
        assert result["current"] == 0
        assert result["direction"] == "none"
