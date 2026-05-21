"""
:file: backend/strategies/builtin/lstm_scorer.py
:brief: LSTM TensorFlow scorer pour EPR5.

Architecture :
    - Input  : séquence de 30 jours de features techniques normalisées
    - LSTM   : 64 units → 32 units (2 couches stackées)
    - Dense  : 16 units ReLU → Dropout 0.3 → output sigmoid
    - Output : probabilité que le rendement à 5j > +2%

Walk-forward safe : entraîné uniquement sur données passées,
prédit uniquement sur le dernier timestep.

:copyright: 2024 Sauhabah — Ethical Finance Platform
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

SEQ_LEN = 30  # jours de lookback pour la séquence LSTM
FORECAST_DAYS = 5  # horizon de prédiction
THRESHOLD = 0.02  # seuil rendement positif (+2%)
MIN_SAMPLES = 200  # minimum d'exemples pour entraîner
EPOCHS = 10  # epochs d'entraînement (rapide)
BATCH_SIZE = 32


# ─── Feature builder ─────────────────────────────────────────────────────────


def _build_feature_matrix(prices: pd.Series) -> np.ndarray | None:
    """
    Construit une matrice (T, N_features) de features techniques normalisées.
    Retourne None si pas assez de données.
    """
    p = prices.dropna()
    if len(p) < SEQ_LEN + FORECAST_DAYS + 10:
        return None

    try:
        ret_1 = p.pct_change(1)
        ret_5 = p.pct_change(5)
        ret_20 = p.pct_change(20)

        # Volatilité réalisée rolling
        vol_10 = ret_1.rolling(10).std()
        vol_20 = ret_1.rolling(20).std()

        # RSI-14
        delta = ret_1
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rsi = 100 - (100 / (1 + gain / (loss + 1e-9)))
        rsi_n = rsi / 100.0  # normalise [0,1]

        # EMA ratio (tendance)
        ema20 = p.ewm(span=20).mean()
        ema50 = p.ewm(span=50).mean()
        ema_ratio = ema20 / (ema50 + 1e-9) - 1

        # MACD histogram normalisé
        ema12 = p.ewm(span=12).mean()
        ema26 = p.ewm(span=26).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9).mean()
        macd_hist = (macd - signal) / (p + 1e-9)

        # Bollinger position [0,1]
        sma20 = p.rolling(20).mean()
        std20 = p.rolling(20).std()
        bb_upper = sma20 + 2 * std20
        bb_lower = sma20 - 2 * std20
        bb_pos = (p - bb_lower) / (bb_upper - bb_lower + 1e-9)
        bb_pos = bb_pos.clip(0, 1)

        # Momentum 20j et 60j
        mom_20 = ret_20
        mom_60 = p.pct_change(60)

        feat = pd.DataFrame(
            {
                "ret_1": ret_1,
                "ret_5": ret_5,
                "ret_20": ret_20,
                "vol_10": vol_10,
                "vol_20": vol_20,
                "rsi": rsi_n,
                "ema_ratio": ema_ratio,
                "macd_hist": macd_hist,
                "bb_pos": bb_pos,
                "mom_20": mom_20,
                "mom_60": mom_60,
            }
        ).dropna()

        return feat.values.astype(np.float32)

    except Exception as e:
        log.warning("LSTM feature build error: %s", e)
        return None


def _normalize(X: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    return (X - mean) / (std + 1e-9)


# ─── Dataset builder ──────────────────────────────────────────────────────────


def _build_ticker_sequences(series, feat_mat) -> tuple[list, list]:
    """Build X/y sequences for a single ticker."""
    X_list, y_list = [], []
    price_series = series.dropna()
    n = len(feat_mat)
    for i in range(SEQ_LEN, n - FORECAST_DAYS):
        seq = feat_mat[i - SEQ_LEN: i]
        if i >= len(price_series):
            continue
        try:
            cur_price = float(price_series.iloc[i])
            fut_price = float(price_series.iloc[i + FORECAST_DAYS])
            label = 1 if fut_price / cur_price - 1 > THRESHOLD else 0
            X_list.append(seq)
            y_list.append(label)
        except Exception:
            continue
    return X_list, y_list


def _build_dataset(
    past_prices: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None:
    """
    Construit X (séquences) et y (labels) pour entraînement LSTM.
    Retourne (X_train, y_train, mean, std) ou None.
    """
    all_X, all_y = [], []

    for ticker, series in past_prices.items():
        if ticker.startswith("^"):
            continue
        feat_mat = _build_feature_matrix(series)
        if feat_mat is None or len(feat_mat) < SEQ_LEN + FORECAST_DAYS:
            continue
        X_t, y_t = _build_ticker_sequences(series, feat_mat)
        all_X.extend(X_t)
        all_y.extend(y_t)

    if len(all_X) < MIN_SAMPLES:
        log.info("LSTM: pas assez d'exemples (%d < %d)", len(all_X), MIN_SAMPLES)
        return None

    X = np.array(all_X, dtype=np.float32)  # (N, SEQ_LEN, features)
    y = np.array(all_y, dtype=np.float32)

    # Normalisation sur l'axe temporel + features
    mean = X.mean(axis=(0, 1), keepdims=True)
    std = X.std(axis=(0, 1), keepdims=True)
    X = _normalize(X, mean, std)

    return X, y, mean.squeeze(), std.squeeze()


# ─── Model builder ────────────────────────────────────────────────────────────


def _build_lstm_model(n_features: int):
    """Construit le modèle LSTM TensorFlow."""
    try:
        import tensorflow as tf
        from tensorflow.keras import layers, models

        tf.get_logger().setLevel("ERROR")

        model = models.Sequential(
            [
                layers.Input(shape=(SEQ_LEN, n_features)),
                layers.LSTM(64, return_sequences=True),
                layers.Dropout(0.2),
                layers.LSTM(32, return_sequences=False),
                layers.Dropout(0.2),
                layers.Dense(16, activation="relu"),
                layers.Dropout(0.3),
                layers.Dense(1, activation="sigmoid"),
            ]
        )

        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
            loss="binary_crossentropy",
            metrics=["accuracy"],
        )
        return model

    except Exception as e:
        log.warning("LSTM model build error: %s", e)
        return None


# ─── Public API ──────────────────────────────────────────────────────────────


def train_lstm(
    past_prices: pd.DataFrame,
) -> dict | None:
    """
    Entraîne le LSTM sur les données historiques.
    Retourne un dict {model, mean, std} ou None si échec.
    """
    try:
        import tensorflow as tf

        tf.get_logger().setLevel("ERROR")
    except ImportError:
        log.warning("TensorFlow non disponible — LSTM scorer désactivé")
        return None

    dataset = _build_dataset(past_prices)
    if dataset is None:
        return None

    X, y, mean, std = dataset
    n_features = X.shape[2]

    model = _build_lstm_model(n_features)
    if model is None:
        return None

    try:
        # Shuffle temporellement safe (pas de look-ahead : labels basés sur futur)
        idx = np.random.permutation(len(X))
        X, y = X[idx], y[idx]

        model.fit(
            X,
            y,
            epochs=EPOCHS,
            batch_size=BATCH_SIZE,
            validation_split=0.15,
            verbose=0,
        )
        log.info("LSTM entraîné sur %d exemples (%d features)", len(X), n_features)
        return {"model": model, "mean": mean, "std": std, "n_features": n_features}

    except Exception as e:
        log.warning("LSTM training error: %s", e)
        return None


def score_ticker(
    lstm_state: dict,
    prices: pd.Series,
) -> float:
    """
    Score LSTM pour un ticker. Retourne probabilité [0,1].
    Retourne 0.5 (neutre) en cas d'erreur.
    """
    if lstm_state is None:
        return 0.5

    try:
        feat_mat = _build_feature_matrix(prices)
        if feat_mat is None or len(feat_mat) < SEQ_LEN:
            return 0.5

        seq = feat_mat[-SEQ_LEN:]  # dernière séquence
        mean = lstm_state["mean"]
        std = lstm_state["std"]
        seq_norm = _normalize(seq, mean, std)

        model = lstm_state["model"]
        prob = float(model.predict(seq_norm[np.newaxis], verbose=0)[0][0])
        return prob

    except Exception as e:
        log.warning("LSTM score error: %s", e)
        return 0.5
