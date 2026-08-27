import streamlit as st

COLORS = {
    "bg": "#F8FAFC",
    "surface": "#FFFFFF",
    "border": "#E2E8F0",
    "text": "#0F172A",
    "muted": "#64748B",
    "primary": "#0284C7",
    "up": "#10B981",
    "up_bg": "#ECFDF5",
    "down": "#EF4444",
    "down_bg": "#FEF2F2",
    "neutral": "#94A3B8",
    "neutral_bg": "#F1F5F9",
    "tcg": "#94A3B8",
}

FOLLOW_LIST_PATH = "appdata/follow_list.json"
PRICES_PATH = "livedata/price_history.csv"
EBAY_POSTS_PATH = "livedata/ebay_posts.csv"

def setup_page():
    st.set_page_config(
        page_title="Card Trading Insights",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        f"""
        <style>
            #MainMenu {{visibility: hidden;}}
            header {{visibility: hidden;}}
            footer {{visibility: hidden;}}
            .stApp {{
                background-color: {COLORS['bg']};
                color: {COLORS['text']};
            }}
            .main .block-container {{
                padding-top: 1.5rem;
                padding-bottom: 3rem;
                max-width: 1500px;
            }}
            div[data-testid="stMetricValue"] {{
                color: {COLORS['primary']};
            }}
            section[data-testid="stSidebar"] {{
                background-color: {COLORS['surface']};
                border-right: 1px solid {COLORS['border']};
            }}
            div[data-testid="stExpander"] {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
            }}
            div[data-baseweb="select"] > div {{
                background-color: {COLORS['surface']};
            }}
            .stButton > button {{
                border-radius: 8px;
            }}
            div[data-testid="stVerticalBlockBorderWrapper"] {{
                transition: box-shadow 0.15s ease, transform 0.15s ease;
                border-radius: 12px !important;
            }}
            div[data-testid="stVerticalBlockBorderWrapper"]:hover {{
                box-shadow: 0 6px 16px rgba(15, 23, 42, 0.08);
                transform: translateY(-2px);
            }}
            .badge {{
                display: inline-block;
                padding: 3px 10px;
                border-radius: 999px;
                font-weight: 600;
                font-size: 0.8rem;
            }}
            .badge-up {{ background-color: {COLORS['up_bg']}; color: {COLORS['up']}; }}
            .badge-down {{ background-color: {COLORS['down_bg']}; color: {COLORS['down']}; }}
            .badge-neutral {{ background-color: {COLORS['neutral_bg']}; color: {COLORS['muted']}; }}
            .signal-box {{
                border-radius: 12px;
                padding: 16px 20px;
                font-size: 1.05rem;
                font-weight: 600;
                border: 1px solid transparent;
            }}
            .no-image-placeholder {{
                height: 220px;
                background: {COLORS['neutral_bg']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                display: flex;
                align-items: center;
                justify-content: center;
                color: {COLORS['neutral']};
                font-size: 0.85rem;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )