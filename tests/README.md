# Test suite

## Run all tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

## Run only unit tests (fast, no network)

```bash
pytest tests/ -m "not integration" -v
```

## Run with coverage

```bash
pytest tests/ --cov=api --cov-report=html
open htmlcov/index.html
```

## Test organisation

| File | What it tests |
|------|---------------|
| `test_metrics.py` | All 25+ quant metrics — pure function unit tests |
| `test_costs.py` | Broker fees (Degiro, Fortuneo, IBKR), slippage, FX, French taxes (PFU, PEA, TTF) |
| `test_engine.py` | **The CRITICAL no-look-ahead test** + smoke tests on the event-driven engine |
| `test_strategies.py` | Contract tests parametrised over EVERY registered strategy |
| `test_screening.py` | Ethical + Sharia screening logic |

## The most important test

`test_engine.py::TestNoLookAhead::test_past_prices_never_contains_future`

If this test fails, **every backtest result in the system is invalid**. Run it on every change to `engine.py`.

## CI

GitHub Actions runs the unit suite on every push. See `.github/workflows/tests.yml`.
