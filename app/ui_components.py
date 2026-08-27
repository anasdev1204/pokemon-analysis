import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from config import COLORS
from data_loader import load_ebay_posts

def direction_for(prob):
    if prob >= 0.55:
        return "UP", "badge-up"
    if prob <= 0.45:
        return "DOWN", "badge-down"
    return "NEUTRAL", "badge-neutral"

def render_badge(label, css_class):
    st.markdown(f'<span class="badge {css_class}">{label}</span>', unsafe_allow_html=True)

def signal_for_prob(prob):
    if prob >= 0.70:
        return "STRONG BUY", COLORS["up_bg"], COLORS["up"]
    if prob >= 0.55:
        return "BUY", COLORS["up_bg"], COLORS["up"]
    if prob <= 0.30:
        return "AVOID", COLORS["down_bg"], COLORS["down"]
    return "HOLD / NO SIGNAL", COLORS["neutral_bg"], COLORS["muted"]

def build_price_chart(df_card_hist, card_name, added_day=None, added_price=None):
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.7, 0.3],
        vertical_spacing=0.06,
        subplot_titles=("Price History", "Demand vs. Offer"),
    )

    fig.add_trace(
        go.Scatter(
            x=df_card_hist["t"],
            y=df_card_hist["cardmarket_price"],
            mode="lines",
            name="Cardmarket",
            line=dict(color=COLORS["up"], width=2.5),
            fill="tozeroy",
            fillcolor="rgba(16, 185, 129, 0.08)",
            hovertemplate="Day %{x}<br>Cardmarket: $%{y:.2f}<extra></extra>",
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=df_card_hist["t"],
            y=df_card_hist["tcgplayer_price"],
            mode="lines",
            name="TCGPlayer",
            line=dict(color=COLORS["tcg"], width=1.5, dash="dash"),
            hovertemplate="Day %{x}<br>TCGPlayer: $%{y:.2f}<extra></extra>",
        ),
        row=1,
        col=1,
    )

    if added_day is not None and added_price is not None:
        fig.add_vline(
            x=added_day,
            line_width=1.5,
            line_dash="dot",
            line_color=COLORS["primary"],
            row=1,
            col=1,
        )
        fig.add_annotation(
            x=added_day,
            y=added_price,
            text="Followed here",
            showarrow=True,
            arrowhead=2,
            font=dict(color=COLORS["primary"], size=11),
            row=1,
            col=1,
        )

    if "current_demand" in df_card_hist.columns:
        fig.add_trace(
            go.Bar(
                x=df_card_hist["t"],
                y=df_card_hist["current_demand"],
                name="Demand",
                marker_color=COLORS["primary"],
                opacity=0.75,
                hovertemplate="Day %{x}<br>Demand: %{y}<extra></extra>",
            ),
            row=2,
            col=1,
        )

    if "current_offer" in df_card_hist.columns:
        fig.add_trace(
            go.Bar(
                x=df_card_hist["t"],
                y=df_card_hist["current_offer"],
                name="Offer",
                marker_color=COLORS["neutral"],
                opacity=0.6,
                hovertemplate="Day %{x}<br>Offer: %{y}<extra></extra>",
            ),
            row=2,
            col=1,
        )

    fig.update_layout(
        title=f"{card_name}",
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,0)",
        height=560,
        barmode="group",
        margin=dict(l=40, r=20, t=70, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1),
        hovermode="x unified",
    )
    fig.update_yaxes(title_text="Price ($)", row=1, col=1)
    fig.update_yaxes(title_text="Units", row=2, col=1)
    fig.update_xaxes(title_text="Day (T)", row=2, col=1)
    fig.update_xaxes(
        rangeslider=dict(visible=True, thickness=0.06),
        row=2,
        col=1,
    )

    return fig

def render_ebay_posts_section(card_id):

    st.subheader("eBay Posts")

    df_ebay = load_ebay_posts(card_id)

    if df_ebay.empty:
        st.info("No eBay posts available for this card.")
        return

    for _, row in df_ebay.iterrows():

        title = str(row["post_title"])
        url = str(row["url"])
        post_type = str(row["type"])
        price = float(row["price"])
        date = str(row["date"])

        st.markdown(
            f'<a href="{url}" target="_blank">{title}</a>',
            unsafe_allow_html=True
        )

        st.caption(
            f"{post_type}  |  ${price:.2f}  |  {date}"
        )