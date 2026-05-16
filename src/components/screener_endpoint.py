# ─── Screener endpoint — à ajouter à la fin de backend/index.py ───────────────


class ScreenerIn(BaseModel):
    method: str = "magic_formula"  # magic_formula | momentum | low_vol | ml | combined
    top_n: int = 20  # nombre de tickers à retourner
    require_ethical: bool = False
    require_sharia: bool = False
    min_market_cap: float = 1e9  # filtre taille minimale (1 Md$ par défaut)
    universe: str = "all"  # all | sp500 | cac40


@app.post("/api/screener")
async def screener(payload: ScreenerIn):
    """
    Rank the full universe of tickers by the chosen method and return top N.
    Results can be fed directly into the backtest panel.
    """
    import asyncio
    import os

    import numpy as np
    import sqlalchemy as sa

    loop = asyncio.get_event_loop()

    def _run_screener():
        database_url = os.environ.get("DATABASE_URL", "")
        sync_url = database_url.replace("postgresql://", "postgresql+psycopg2://")
        engine = sa.create_engine(sync_url, pool_pre_ping=True)

        # 1. Load fundamentals
        with engine.connect() as conn:
            rows = conn.execute(
                sa.text("""
                SELECT ticker, name, sector, industry, market_cap,
                       total_debt, total_revenue, beta, dividend_yield
                FROM ticker_fundamentals
                WHERE market_cap >= :min_cap
                ORDER BY market_cap DESC
            """),
                {"min_cap": payload.min_market_cap},
            ).fetchall()

        if not rows:
            return []

        import pandas as pd

        df = pd.DataFrame(
            rows,
            columns=[
                "ticker",
                "name",
                "sector",
                "industry",
                "market_cap",
                "total_debt",
                "total_revenue",
                "beta",
                "dividend_yield",
            ],
        )

        # 2. Ethical / Sharia filter
        if payload.require_ethical:
            ethical_blacklist = ["weapons", "tobacco", "gambling", "fossil", "coal", "oil"]
            mask = ~df["sector"].str.lower().apply(lambda s: any(b in s for b in ethical_blacklist))
            df = df[mask]

        if payload.require_sharia:
            sharia_blacklist = ["bank", "insurance", "financial", "alcohol", "casino", "tobacco"]
            mask = ~df["sector"].str.lower().apply(lambda s: any(b in s for b in sharia_blacklist))
            df = df[mask]
            # Debt ratio filter
            df["debt_ratio"] = df["total_debt"] / (df["market_cap"] + 1)
            df = df[df["debt_ratio"] <= 0.33]

        if df.empty:
            return []

        tickers = df["ticker"].tolist()

        # 3. Load recent prices for technical scoring
        with engine.connect() as conn:
            price_rows = conn.execute(
                sa.text("""
                SELECT ticker, date, adj_close
                FROM ohlcv
                WHERE ticker = ANY(:tickers)
                  AND date >= CURRENT_DATE - INTERVAL '300 days'
                ORDER BY ticker, date
            """),
                {"tickers": tickers},
            ).fetchall()

        price_df = pd.DataFrame(price_rows, columns=["ticker", "date", "price"])
        price_pivot = price_df.pivot(index="date", columns="ticker", values="price")

        # 4. Compute scores per method
        scores = {}

        for ticker in tickers:
            row = df[df["ticker"] == ticker].iloc[0]
            market_cap = float(row["market_cap"] or 1)
            total_debt = float(row["total_debt"] or 0)
            total_revenue = float(row["total_revenue"] or 0)
            beta = float(row["beta"] or 1.0)

            ev = market_cap + total_debt
            ebit = total_revenue * 0.15
            net_assets = max(market_cap * 0.5, 1)

            earning_yield = (ebit / ev) if ev > 0 else 0.0
            roic = (ebit / net_assets) if net_assets > 0 else 0.0

            # Price series
            if ticker in price_pivot.columns:
                ser = price_pivot[ticker].dropna()
            else:
                ser = pd.Series(dtype=float)

            # Technical metrics
            ret_1m = float(ser.pct_change(21).iloc[-1]) if len(ser) >= 22 else 0.0
            ret_6m = float(ser.pct_change(126).iloc[-1]) if len(ser) >= 127 else 0.0
            ret_12m = float(ser.pct_change(252).iloc[-1]) if len(ser) >= 253 else 0.0
            vol_20 = float(ser.pct_change().iloc[-20:].std()) if len(ser) >= 21 else 1.0

            scores[ticker] = {
                "ticker": ticker,
                "name": str(row["name"]),
                "sector": str(row["sector"]),
                "market_cap": market_cap,
                "earning_yield": round(earning_yield, 4),
                "roic": round(roic, 4),
                "beta": round(beta, 2),
                "ret_1m": round(ret_1m * 100, 2),
                "ret_6m": round(ret_6m * 100, 2),
                "ret_12m": round(ret_12m * 100, 2),
                "vol_20": round(vol_20 * 100, 2),
                "dividend_yield": round(float(row["dividend_yield"] or 0), 2),
            }

        scores_df = pd.DataFrame(list(scores.values()))
        if scores_df.empty:
            return []

        # 5. Ranking by method
        if payload.method == "magic_formula":
            scores_df["rank_ey"] = scores_df["earning_yield"].rank(ascending=False)
            scores_df["rank_roic"] = scores_df["roic"].rank(ascending=False)
            scores_df["score"] = scores_df["rank_ey"] + scores_df["rank_roic"]
            scores_df = scores_df.sort_values("score")

        elif payload.method == "momentum":
            scores_df["score"] = (
                scores_df["ret_12m"] * 0.5 + scores_df["ret_6m"] * 0.3 + scores_df["ret_1m"] * 0.2
            )
            scores_df = scores_df.sort_values("score", ascending=False)

        elif payload.method == "low_vol":
            scores_df["score"] = scores_df["vol_20"]
            scores_df = scores_df.sort_values("score")

        elif payload.method == "ml":
            # RandomForest scoring
            try:
                from sklearn.preprocessing import StandardScaler

                features = [
                    "earning_yield",
                    "roic",
                    "ret_1m",
                    "ret_6m",
                    "ret_12m",
                    "vol_20",
                    "beta",
                ]
                X = scores_df[features].fillna(0).values

                # Simple unsupervised scoring: distance from ideal (high ey, roic, momentum, low vol)
                scaler = StandardScaler()
                X_scaled = scaler.fit_transform(X)

                # Ideal vector: max ey, roic, momentum; min vol, beta
                ideal = np.array([1, 1, 1, 1, 1, -1, -1], dtype=float)
                ml_scores = X_scaled @ ideal
                scores_df["score"] = ml_scores
                scores_df = scores_df.sort_values("score", ascending=False)
            except Exception:
                scores_df["score"] = scores_df["earning_yield"]
                scores_df = scores_df.sort_values("score", ascending=False)

        elif payload.method == "combined":
            scores_df["rank_ey"] = scores_df["earning_yield"].rank(ascending=False)
            scores_df["rank_roic"] = scores_df["roic"].rank(ascending=False)
            scores_df["rank_mom"] = (scores_df["ret_6m"] + scores_df["ret_12m"]).rank(
                ascending=False
            )
            scores_df["rank_vol"] = scores_df["vol_20"].rank(ascending=True)
            scores_df["score"] = (
                scores_df["rank_ey"]
                + scores_df["rank_roic"]
                + scores_df["rank_mom"] * 0.5
                + scores_df["rank_vol"] * 0.3
            )
            scores_df = scores_df.sort_values("score")

        # 6. Add rank column and return top N
        scores_df = scores_df.head(payload.top_n).reset_index(drop=True)
        scores_df["rank"] = scores_df.index + 1
        scores_df["score"] = scores_df["score"].round(2)

        return scores_df.to_dict(orient="records")

    results = await loop.run_in_executor(None, _run_screener)
    return {"results": results, "method": payload.method, "count": len(results)}
