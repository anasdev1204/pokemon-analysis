import pandas as pd
import streamlit as st

try:
    import lightgbm as lgb
    LGB_AVAILABLE = True
except ImportError:
    LGB_AVAILABLE = False

@st.cache_resource
def load_models():
    if not LGB_AVAILABLE:
        return None, None, None
    m14 = lgb.Booster(model_file="models/model_14.txt")
    m30 = lgb.Booster(model_file="models/model_30.txt")
    m60 = lgb.Booster(model_file="models/model_60.txt")
    return m14, m30, m60

def extract_features_at_T(df_source, T):
    df_hist = df_source[df_source["t"] <= T].copy()
    df_hist = df_hist.sort_values(["card_id", "t"])
    df_hist["daily_return"] = df_hist.groupby("card_id")["cardmarket_price"].pct_change()

    def _extract_single(group):
        latest = group.iloc[-1]
        price_t = latest["cardmarket_price"]
        tcg_price_t = latest["tcgplayer_price"]
        card_id_value = group.name

        def safe_get_price(days_back):
            target_t = T - days_back
            sub = group[group["t"] == target_t]["cardmarket_price"]
            if len(sub) > 0:
                return sub.values[0]
            return group["cardmarket_price"].iloc[0]

        price_7 = safe_get_price(7)
        price_14 = safe_get_price(14)
        price_30 = safe_get_price(30)

        return pd.Series({
            "card_id": card_id_value,
            "seriesId": latest["seriesId"],
            "rarity": latest["rarity"],
            "hype_level": latest["hype_level"],
            "age_level": latest["age_level"],
            "current_offer": latest["current_offer"],
            "current_demand": latest["current_demand"],
            "demand_to_offer_ratio": latest["current_demand"] / (latest["current_offer"] + 1e-5),
            "price_T": price_t,
            "cross_market_ratio": price_t / (tcg_price_t + 1e-5),
            "return_7d": (price_t - price_7) / price_7,
            "return_14d": (price_t - price_14) / price_14,
            "return_30d": (price_t - price_30) / price_30,
            "volatility_14d": group.tail(14)["daily_return"].std(),
            "volatility_30d": group.tail(30)["daily_return"].std(),
            "sma_7_ratio": price_t / group.tail(7)["cardmarket_price"].mean(),
            "sma_30_ratio": price_t / group.tail(30)["cardmarket_price"].mean(),
        })

    grouped = df_hist.groupby("card_id", group_keys=False)
    try:
        result = grouped.apply(_extract_single, include_groups=False)
    except TypeError:
        result = grouped.apply(_extract_single)
    return result.reset_index(drop=True)

def get_predictions_for_card(df_prices, card_id, current_t):
    if not LGB_AVAILABLE:
        return {"14d": 0.5, "30d": 0.5, "60d": 0.5}

    df_card_sub = df_prices[(df_prices["card_id"] == card_id) & (df_prices["t"] <= current_t)]
    if len(df_card_sub) < 1:
        return {"14d": 0.5, "30d": 0.5, "60d": 0.5}

    feats = extract_features_at_T(df_card_sub, T=current_t)
    if len(feats) == 0:
        return {"14d": 0.5, "30d": 0.5, "60d": 0.5}

    for col in ["seriesId", "rarity"]:
        if col in feats.columns:
            feats[col] = feats[col].astype("category")

    feature_cols = [c for c in feats.columns if c != "card_id"]
    m14, m30, m60 = load_models()

    prob_14 = m14.predict(feats[feature_cols])[0]
    prob_30 = m30.predict(feats[feature_cols])[0]
    prob_60 = m60.predict(feats[feature_cols])[0]

    return {"14d": float(prob_14), "30d": float(prob_30), "60d": float(prob_60)}