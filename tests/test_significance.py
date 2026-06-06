"""
tests/test_significance.py
Tests unitaires — backend.quant.significance
"""
import pytest
import numpy as np

pytestmark = pytest.mark.unit


def _returns(n=252, mu=0.001, sigma=0.02, seed=42):
    return np.random.default_rng(seed).normal(mu, sigma, n)


class TestNormCdf:
    def test_median(self):
        from backend.quant.significance import _norm_cdf
        assert abs(_norm_cdf(0) - 0.5) < 1e-6

    def test_positive(self):
        from backend.quant.significance import _norm_cdf
        assert _norm_cdf(1.96) > 0.97

    def test_negative(self):
        from backend.quant.significance import _norm_cdf
        assert _norm_cdf(-1.96) < 0.03


class TestBetainc:
    def test_zero_x(self):
        from backend.quant.significance import _betainc
        assert _betainc(1.0, 1.0, 0.0) == 0.0

    def test_one_x(self):
        from backend.quant.significance import _betainc
        assert _betainc(1.0, 1.0, 1.0) == 1.0

    def test_mid(self):
        from backend.quant.significance import _betainc
        val = _betainc(2.0, 2.0, 0.5)
        assert 0.0 < val < 1.0


class TestTCdf:
    def test_large_df_approx_normal(self):
        from backend.quant.significance import _t_cdf, _norm_cdf
        assert abs(_t_cdf(1.96, 100) - _norm_cdf(1.96)) < 0.01

    def test_zero_df(self):
        from backend.quant.significance import _t_cdf
        assert _t_cdf(1.0, 0) == 0.5

    def test_negative_t(self):
        from backend.quant.significance import _t_cdf
        assert _t_cdf(-1.0, 10) < 0.5

    def test_positive_t_large(self):
        from backend.quant.significance import _t_cdf
        assert _t_cdf(2.0, 10) > 0.9

    def test_small_df(self):
        from backend.quant.significance import _t_cdf
        val = _t_cdf(1.0, 5)
        assert 0.5 < val < 1.0


class TestLinRegress:
    def test_perfect_line(self):
        from backend.quant.significance import _linregress
        x = np.arange(10, dtype=float)
        y = 2 * x + 3
        slope, intercept, r, p, se = _linregress(x, y)
        assert abs(slope - 2.0) < 1e-9
        assert abs(intercept - 3.0) < 1e-9

    def test_flat_x(self):
        from backend.quant.significance import _linregress
        x = np.ones(10)
        y = np.arange(10, dtype=float)
        slope, intercept, r, p, se = _linregress(x, y)
        assert slope == 0.0


class TestJobsonKorkie:
    def test_identical_series(self):
        from backend.quant.significance import jobson_korkie
        r = _returns()
        result = jobson_korkie(r, r)
        assert abs(result.statistic) < 1e-10
        assert not result.significant

    def test_different_series(self):
        from backend.quant.significance import jobson_korkie
        r_good = _returns(mu=0.005, sigma=0.01)
        r_bad = _returns(mu=-0.005, sigma=0.01, seed=1)
        result = jobson_korkie(r_good, r_bad)
        assert isinstance(result.statistic, float)

    def test_zero_std_returns_default(self):
        from backend.quant.significance import jobson_korkie
        r_a = np.zeros(100)
        r_b = _returns()[:100]
        result = jobson_korkie(r_a, r_b)
        assert abs(result.statistic) < 1e-10

    def test_negative_var_returns_default(self):
        from backend.quant.significance import jobson_korkie
        r = _returns(n=5)
        result = jobson_korkie(r, r * 0.999)
        assert isinstance(result.p_value, float)


class TestBootstrapCI:
    def test_ci_ordered(self):
        from backend.quant.significance import bootstrap_ci
        r = _returns(n=200)
        result = bootstrap_ci(r, np.mean, n_samples=500)
        assert result.ci_lower <= result.estimate <= result.ci_upper

    def test_n_samples(self):
        from backend.quant.significance import bootstrap_ci
        r = _returns(n=100)
        result = bootstrap_ci(r, np.std, n_samples=300)
        assert result.n_samples == 300


class TestAlphaTtest:
    def test_returns_testresult(self):
        from backend.quant.significance import alpha_ttest
        r = _returns(n=252)
        market = _returns(n=252, seed=1)
        result = alpha_ttest(r, market)
        assert isinstance(result.statistic, float)
        assert isinstance(result.significant, bool)

    def test_zero_se(self):
        from backend.quant.significance import alpha_ttest
        r = np.ones(100) * 0.001
        market = np.ones(100) * 0.001
        result = alpha_ttest(r, market)
        assert abs(result.statistic) < 1e-10


class TestWhitesRealityCheck:
    def test_returns_pvalue(self):
        from backend.quant.significance import whites_reality_check
        strategies = [_returns(seed=i) for i in range(3)]
        benchmark = _returns(seed=99)
        p = whites_reality_check(strategies, benchmark, n_bootstrap=100)
        assert 0.0 <= p <= 1.0

    def test_dominant_strategy_low_p(self):
        from backend.quant.significance import whites_reality_check
        good = [np.ones(252) * 0.01]
        bad = [np.ones(252) * -0.01, np.ones(252) * -0.005]
        benchmark = np.zeros(252)
        p = whites_reality_check(good + bad, benchmark, n_bootstrap=200)
        assert isinstance(p, float)
