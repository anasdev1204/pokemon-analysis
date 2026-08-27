import json
import os
import pandas as pd
import streamlit as st
from config import PRICES_PATH, FOLLOW_LIST_PATH, EBAY_POSTS_PATH

@st.cache_data
def load_prices():
    return pd.read_csv(PRICES_PATH)

def load_follow_list():
    if os.path.exists(FOLLOW_LIST_PATH):
        with open(FOLLOW_LIST_PATH, "r") as f:
            return json.load(f)
    return {}

def save_follow_list(follow_data):
    os.makedirs(os.path.dirname(FOLLOW_LIST_PATH), exist_ok=True)
    with open(FOLLOW_LIST_PATH, "w") as f:
        json.dump(follow_data, f, indent=4)

@st.cache_data
def load_ebay_posts(card_id=None):
    if not os.path.exists(EBAY_POSTS_PATH):
        return pd.DataFrame(columns=["post_title", "type", "price", "date", "url"])
    
    df = pd.read_csv(
        EBAY_POSTS_PATH,
    )

    if card_id is not None and "card_id" in df.columns:
        df = df[df["card_id"] == str(card_id)]

    return df