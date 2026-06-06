"""
tests/test_narrative.py
Tests unitaires — backend.report.narrative
"""
import pytest
pytestmark = pytest.mark.unit


def _metrics(sharpe=1.2, cagr=0.12, vol=0.15, max_dd=-0.10, total_ret=0.35,
             sortino=1.5, calmar=1.2, var_95=-0.02, cvar_95=-0.03,
             hit_rate=0.55, profit_factor=1.3, beta=0.9, alpha_jensen=0.02,
             recovery=2.5, omega=1.4, skewness=0.1, excess_kurtosis=0.5,
             average_drawdown=-0.05, information_ratio=0.8):
    return {
        "sharpe_ratio": sharpe, "cagr": cagr, "annualised_volatility": vol,
        "max_drawdown": max_dd, "total_return": total_ret, "sortino_ratio": sortino,
        "calmar_ratio": calmar, "var_95": var_95, "cvar_95": cvar_95,
        "hit_rate": hit_rate, "profit_factor": profit_factor, "beta": beta,
        "alpha_jensen": alpha_jensen, "recovery_factor": recovery,
        "omega_ratio": omega, "skewness": skewness, "excess_kurtosis": excess_kurtosis,
        "average_drawdown": average_drawdown, "information_ratio": information_ratio,
    }


def _meta(strategy="buy_hold", period="5y"):
    return {"strategy": strategy, "period": period}


class TestHelpers:
    def test_pct_normal(self):
        from backend.report.narrative import _pct
        assert _pct(0.12) == "+12.0%"

    def test_pct_none(self):
        from backend.report.narrative import _pct
        assert _pct(None) == "N/A"

    def test_f_normal(self):
        from backend.report.narrative import _f
        assert _f(1.234) == "1.23"

    def test_f_none(self):
        from backend.report.narrative import _f
        assert _f(None) == "N/A"

    def test_eur_normal(self):
        from backend.report.narrative import _eur
        result = _eur(10000)
        assert "10" in result and "€" in result

    def test_eur_none(self):
        from backend.report.narrative import _eur
        assert _eur(None) == "N/A"


class TestPerfLabelComment:
    def test_exceptional(self):
        from backend.report.narrative import _perf_label_comment
        label, comment = _perf_label_comment(2.5, 0.20)
        assert "exceptionnel" in label

    def test_solid(self):
        from backend.report.narrative import _perf_label_comment
        label, _ = _perf_label_comment(1.6, 0.12)
        assert "solid" in label.lower() or "régulier" in label

    def test_satisfactory(self):
        from backend.report.narrative import _perf_label_comment
        label, _ = _perf_label_comment(1.1, 0.06)
        assert "satisfaisant" in label

    def test_modest(self):
        from backend.report.narrative import _perf_label_comment
        label, _ = _perf_label_comment(0.6, 0.03)
        assert "modest" in label.lower() or "positif" in label

    def test_below_expectations(self):
        from backend.report.narrative import _perf_label_comment
        label, _ = _perf_label_comment(0.2, 0.01)
        assert "attentes" in label or "deçà" in label


class TestDdComment:
    def test_small_dd(self):
        from backend.report.narrative import _dd_comment
        c = _dd_comment(-0.05)
        assert "remarquable" in c or "protection" in c

    def test_medium_dd(self):
        from backend.report.narrative import _dd_comment
        c = _dd_comment(-0.15)
        assert "acceptable" in c or "limits" in c.lower()

    def test_large_dd(self):
        from backend.report.narrative import _dd_comment
        c = _dd_comment(-0.30)
        assert "significative" in c or "correction" in c

    def test_very_large_dd(self):
        from backend.report.narrative import _dd_comment
        c = _dd_comment(-0.50)
        assert "vigilance" in c or "principal" in c


class TestNarrativeExecutiveSummary:
    def test_returns_string(self):
        from backend.report.narrative import narrative_executive_summary
        result = narrative_executive_summary(_metrics(), _meta())
        assert isinstance(result, str) and len(result) > 50

    def test_contains_strategy(self):
        from backend.report.narrative import narrative_executive_summary
        result = narrative_executive_summary(_metrics(), _meta(strategy="momentum"))
        assert "momentum" in result

    def test_handles_none_values(self):
        from backend.report.narrative import narrative_executive_summary
        m = {k: None for k in _metrics()}
        result = narrative_executive_summary(m, _meta())
        assert isinstance(result, str)


class TestNarrativePerformance:
    def test_returns_string(self):
        from backend.report.narrative import narrative_performance
        result = narrative_performance(_metrics(), _meta())
        assert isinstance(result, str) and len(result) > 20

    def test_with_none_alpha(self):
        from backend.report.narrative import narrative_performance
        m = _metrics()
        m["alpha_jensen"] = None
        result = narrative_performance(m, _meta())
        assert isinstance(result, str)


class TestNarrativeDrawdown:
    def test_returns_string(self):
        from backend.report.narrative import narrative_drawdown
        result = narrative_drawdown(_metrics())
        assert isinstance(result, str) and len(result) > 20

    def test_good_drawdown(self):
        from backend.report.narrative import narrative_drawdown
        result = narrative_drawdown(_metrics(max_dd=-0.04))
        assert isinstance(result, str)


class TestNarrativeRisk:
    def test_returns_string(self):
        from backend.report.narrative import narrative_risk
        result = narrative_risk(_metrics())
        assert isinstance(result, str) and len(result) > 20


class TestNarrativeStressTests:
    def test_empty_stress(self):
        from backend.report.narrative import narrative_stress_tests
        result = narrative_stress_tests([])
        assert isinstance(result, str)

    def test_with_scenarios(self):
        from backend.report.narrative import narrative_stress_tests
        stress = [
            {"name": "Covid crash", "total_return": -0.35, "max_drawdown": -0.40,
             "volatility": 0.50, "sharpe": -1.2, "n_days": 30,
             "start": "2020-02-20", "end": "2020-03-23"},
            {"name": "2022 bear", "total_return": -0.20, "max_drawdown": -0.25,
             "volatility": 0.30, "sharpe": -0.8, "n_days": 60,
             "start": "2022-01-01", "end": "2022-06-01"},
        ]
        result = narrative_stress_tests(stress)
        assert isinstance(result, str) and len(result) > 20


class TestNarrativeCosts:
    def test_returns_string(self):
        from backend.report.narrative import narrative_costs
        cost_summary = {"total_costs": 500.0, "commission": 300.0,
                        "slippage": 100.0, "taxes": 100.0}
        cost_breakdown = {"AAPL": {"total": 200.0}, "MSFT": {"total": 300.0}}
        result = narrative_costs(cost_summary, cost_breakdown)
        assert isinstance(result, str) and len(result) > 20

    def test_empty_breakdown(self):
        from backend.report.narrative import narrative_costs
        result = narrative_costs({}, {})
        assert isinstance(result, str)


class TestNarrativeMlPerformance:
    def test_returns_string(self):
        from backend.report.narrative import narrative_ml_performance
        ml_info = {"accuracy": 0.62, "features": 8, "model": "RandomForest"}
        result = narrative_ml_performance(ml_info)
        assert isinstance(result, str)

    def test_empty_ml_info(self):
        from backend.report.narrative import narrative_ml_performance
        result = narrative_ml_performance({})
        assert isinstance(result, str)


class TestGenerateAllNarratives:
    def test_returns_dict(self):
        from backend.report.narrative import generate_all_narratives
        tearsheet = {
            "metrics": _metrics(),
            "meta": _meta(),
            "stress_tests": [],
            "cost_summary": {},
            "cost_breakdown": {},
            "ml_info": {},
        }
        result = generate_all_narratives(tearsheet)
        assert isinstance(result, dict)
        assert len(result) > 3

    def test_all_values_are_strings(self):
        from backend.report.narrative import generate_all_narratives
        tearsheet = {"metrics": _metrics(), "meta": _meta(),
                     "stress_tests": [], "cost_summary": {}, "cost_breakdown": {}, "ml_info": {}}
        result = generate_all_narratives(tearsheet)
        for k, v in result.items():
            assert isinstance(v, str), f"narrative '{k}' is not a string"


class TestInterpretMetric:
    def test_sharpe_good(self):
        from backend.report.narrative import interpret_metric
        result = interpret_metric("sharpe_ratio", 1.5)
        assert isinstance(result, str) and len(result) > 5

    def test_max_drawdown(self):
        from backend.report.narrative import interpret_metric
        result = interpret_metric("max_drawdown", -0.15)
        assert isinstance(result, str)

    def test_unknown_metric(self):
        from backend.report.narrative import interpret_metric
        result = interpret_metric("unknown_xyz", 42.0)
        assert isinstance(result, str)

    def test_none_value(self):
        from backend.report.narrative import interpret_metric
        result = interpret_metric("sharpe_ratio", None)
        assert isinstance(result, str)


class TestGenerateMetricInterpretations:
    def test_returns_dict(self):
        from backend.report.narrative import generate_metric_interpretations
        result = generate_metric_interpretations(_metrics())
        assert isinstance(result, dict)

    def test_keys_are_metric_names(self):
        from backend.report.narrative import generate_metric_interpretations
        m = _metrics()
        result = generate_metric_interpretations(m)
        for k in result:
            assert isinstance(k, str)
