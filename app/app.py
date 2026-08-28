import os
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from config import setup_page, PRICES_PATH
from data_loader import load_prices, load_follow_list, save_follow_list
from ml_engine import LGB_AVAILABLE, get_predictions_for_card
from ui_components import (
    direction_for,
    render_badge,
    signal_for_prob,
    build_price_chart,
    render_ebay_posts_section,
)

setup_page()

if not LGB_AVAILABLE:
    st.sidebar.warning("lightgbm isn't installed — predictions will show as neutral placeholders.")

if not os.path.exists(PRICES_PATH):
    st.error(f"Couldn't find price data at `{PRICES_PATH}`. Add the file and reload the app.")
    st.stop()

df_prices = load_prices()
latest_day = int(df_prices["t"].max())
earliest_day = max(30, int(df_prices["t"].min()))

st.set_page_config(page_title="Pokémon Card Analysis", layout="wide", initial_sidebar_state="collapsed")
st.markdown(
    """
    <style>
        [data-testid="stSidebar"] {
            display: none;
        }
        [data-testid="stSidebarCollapsedControl"] {
            display: none;
        }
    </style>
    """,
    unsafe_allow_html=True
)

with st.expander("Controls", expanded=True):
    current_sim_day = st.slider(
        "Current day (T)",
        min_value=earliest_day,
        max_value=latest_day,
        value=latest_day,
        help="Move this back in time to see what the model would have predicted on an earlier day.",
    )
    st.sidebar.caption(f"Data available through day **{latest_day}**")

    if st.button("Reload Data"):
        st.cache_data.clear()
        st.rerun()

st.divider()

if "selected_card_id" not in st.session_state:
    st.session_state.selected_card_id = None
if "page_number" not in st.session_state:
    st.session_state.page_number = 0

tab1, tab2 = st.tabs(["Card Repository", "Watchlist"])

with tab1:
    df_latest_slice = df_prices[df_prices["t"] == current_sim_day].copy()
    selected_id = st.session_state.selected_card_id

    if selected_id is not None:
        selected_rows = df_latest_slice[df_latest_slice["card_id"] == selected_id]

        if len(selected_rows) == 0:
            st.session_state.selected_card_id = None
            st.rerun()

        card_row = selected_rows.iloc[0]
        selected_name = card_row["name"]

        top_col1, top_col2 = st.columns([6, 1])
        with top_col1:
            st.subheader(selected_name)
        with top_col2:
            if st.button("Back", use_container_width=True):
                st.session_state.selected_card_id = None
                st.rerun()

        detail_img_col, detail_info_col = st.columns([1, 3])

        with detail_img_col:
            image_val = card_row.get("image", "")
            if pd.notna(image_val) and str(image_val).strip() != "":
                st.image(image_val, use_container_width=True)
            else:
                st.markdown('<div class="no-image-placeholder">No Image</div>', unsafe_allow_html=True)

        with detail_info_col:
            info_col1, info_col2, info_col3, info_col4 = st.columns(4)
            with info_col1:
                st.metric("Series", str(card_row["seriesId"]))
            with info_col2:
                st.metric("Rarity", str(card_row["rarity"]))
            with info_col3:
                st.metric("Cardmarket Price", f"${card_row['cardmarket_price']:.2f}")
            with info_col4:
                st.metric("Demand", f"{card_row['current_demand']:.0f}")

            follow_data = load_follow_list()
            cid_str = str(selected_id)
            is_followed = cid_str in follow_data

            if is_followed:
                if st.button("Unfollow Card", use_container_width=True):
                    del follow_data[cid_str]
                    save_follow_list(follow_data)
                    st.rerun()
            else:
                if st.button("Follow & Track Card", use_container_width=True, type="primary"):
                    preds_for_follow = get_predictions_for_card(df_prices, selected_id, current_sim_day)
                    follow_data[cid_str] = {
                        "name": selected_name,
                        "image": card_row.get("image", ""),
                        "added_day": int(current_sim_day),
                        "added_price": float(card_row["cardmarket_price"]),
                        "predictions": {
                            h: {
                                "pred_up": bool(preds_for_follow[h] >= 0.55),
                                "prob": float(preds_for_follow[h]),
                                "checked": False,
                                "correct": None,
                            }
                            for h in ["14d", "30d", "60d"]
                        },
                    }
                    save_follow_list(follow_data)
                    st.success("Card added to Watchlist!")
                    st.rerun()

        st.markdown("---")

        df_card_hist = df_prices[
            (df_prices["card_id"] == selected_id) & (df_prices["t"] <= current_sim_day)
        ].sort_values("t")

        fig = build_price_chart(df_card_hist, selected_name)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        render_ebay_posts_section(selected_id)

        st.markdown("---")
        st.subheader("Model Outlook")

        with st.spinner("Scoring latest features..."):
            preds = get_predictions_for_card(df_prices, selected_id, current_sim_day)

        pred_cols = st.columns(3)
        for column, horizon in zip(pred_cols, ["14d", "30d", "60d"]):
            prob = preds[horizon]
            direction, css_class = direction_for(prob)
            with column:
                st.markdown(f"**{horizon} outlook**")
                render_badge(direction, css_class)
                st.progress(min(max(prob, 0.0), 1.0), text=f"{prob:.1%} probability of increase")

        st.markdown("#### Trading Signal (14-day)")
        label, bg, fg = signal_for_prob(preds["14d"])
        st.markdown(
            f"""<div class="signal-box" style="background-color:{bg}; color:{fg}; border-color:{fg}33;">
            {label} - {preds['14d']:.1%} probability of a price increase within 14 days
            </div>""",
            unsafe_allow_html=True,
        )

    else:
        st.title("Card Repository")

        with st.expander("Search, Filter & Sort", expanded=True):
            search_col, sort_col = st.columns([2, 1])

            with search_col:
                search_query = st.text_input(
                    "Search by card name",
                    placeholder="e.g. Charizard",
                    key="repository_search",
                )

            with sort_col:
                sort_by = st.selectbox(
                    "Sort by",
                    ["Card Name", "Highest Price", "Lowest Price", "Recent Demand"],
                    key="repository_sort",
                )

            f_col1, f_col2, f_col3 = st.columns(3)

            with f_col1:
                rarity_filter = st.multiselect(
                    "Rarity",
                    df_prices["rarity"].dropna().unique(),
                    key="repository_rarity",
                )

            with f_col2:
                series_filter = st.multiselect(
                    "Series ID",
                    df_prices["seriesId"].dropna().unique(),
                    key="repository_series",
                )

            with f_col3:
                cards_per_row = st.selectbox(
                    "Cards per row",
                    [3, 4, 5, 6],
                    index=1,
                    key="repository_cards_per_row",
                )
                
        if rarity_filter:
            df_latest_slice = df_latest_slice[df_latest_slice["rarity"].isin(rarity_filter)]
            st.session_state.page_number = 0
            
        if series_filter:
            df_latest_slice = df_latest_slice[df_latest_slice["seriesId"].isin(series_filter)]
            st.session_state.page_number = 0
        if search_query:
            df_latest_slice = df_latest_slice[
                df_latest_slice["name"].str.contains(search_query, case=False, na=False)
            ]
            st.session_state.page_number = 0 

        sort_map = {
            "Card Name": ("name", True),
            "Highest Price": ("cardmarket_price", False),
            "Lowest Price": ("cardmarket_price", True),
            "Recent Demand": ("current_demand", False),
        }
        sort_col_name, ascending = sort_map[sort_by]
        df_latest_slice = df_latest_slice.sort_values(sort_col_name, ascending=ascending)

        st.caption(f"{len(df_latest_slice)} card(s) match your filters")

        if len(df_latest_slice) == 0:
            st.warning("No cards match the active filter criteria. Try widening your search.")
        else:
            page_size = 20
            n_pages = max(1, int(np.ceil(len(df_latest_slice) / page_size)))
            st.session_state.page_number = min(st.session_state.page_number, n_pages - 1)

            page_df = df_latest_slice.iloc[
                st.session_state.page_number * page_size : (st.session_state.page_number + 1) * page_size
            ]

            rows = list(page_df.groupby(np.arange(len(page_df)) // cards_per_row))

            for _, row_group in rows:
                cols = st.columns(cards_per_row)
                for col, (_, card) in zip(cols, row_group.iterrows()):
                    with col:
                        with st.container(border=True):
                            image_val = card.get("image", "")
                            if pd.notna(image_val) and str(image_val).strip() != "":
                                st.image(image_val, use_container_width=True)
                            else:
                                st.markdown('<div class="no-image-placeholder">No Image</div>', unsafe_allow_html=True)

                            st.markdown(f"**{card['name']}**")
                            st.caption(f"Series {card['seriesId']} · {card['rarity']}")
                            st.markdown(f"**${card['cardmarket_price']:.2f}**")

                            if st.button("View Card", key=f"view_{card['card_id']}", use_container_width=True):
                                st.session_state.selected_card_id = card["card_id"]
                                st.rerun()

            if n_pages > 1:
                nav_col1, nav_col2, nav_col3 = st.columns([1, 2, 1])
                with nav_col1:
                    if st.button("Prev", disabled=st.session_state.page_number == 0):
                        st.session_state.page_number -= 1
                        st.rerun()
                with nav_col2:
                    st.markdown(
                        f"<div style='text-align:center;'>Page {st.session_state.page_number + 1} of {n_pages}</div>",
                        unsafe_allow_html=True,
                    )
                with nav_col3:
                    if st.button("Next", disabled=st.session_state.page_number >= n_pages - 1):
                        st.session_state.page_number += 1
                        st.rerun()

with tab2:
    st.title("Watchlist & Accuracy Tracker")

    follow_data = load_follow_list()

    if not follow_data:
        st.info("No cards followed yet. Select a card in the Repository tab and click Follow & Track Card.")
    else:
        updated = False
        table_rows = []

        for cid_str, info in list(follow_data.items()):
            cid = int(cid_str)
            added_day = info["added_day"]
            added_price = info["added_price"]

            for h_days, h_key in [(14, "14d"), (30, "30d"), (60, "60d")]:
                target_day = added_day + h_days
                pred_info = info["predictions"][h_key]

                if not pred_info["checked"] and current_sim_day >= target_day:
                    price_target = df_prices[
                        (df_prices["card_id"] == cid) & (df_prices["t"] == target_day)
                    ]["cardmarket_price"]

                    if len(price_target) > 0:
                        actual_price = price_target.values[0]
                        price_went_up = actual_price > added_price
                        pred_info["correct"] = price_went_up == pred_info["pred_up"]
                        pred_info["checked"] = True
                        pred_info["target_price"] = float(actual_price)
                        updated = True

            def fmt_status(pred_dict, day_offset, added_day=added_day):
                if pred_dict["correct"] is True:
                    return "Correct"
                if pred_dict["correct"] is False:
                    return "Incorrect"
                return f"Pending (Day {added_day + day_offset})"

            table_rows.append({
                "Card ID": cid,
                "Image": info.get("image", ""),
                "Card Name": info["name"],
                "Added Day": added_day,
                "Start Price": added_price,
                "14d Status": fmt_status(info["predictions"]["14d"], 14),
                "30d Status": fmt_status(info["predictions"]["30d"], 30),
                "60d Status": fmt_status(info["predictions"]["60d"], 60),
            })

        if updated:
            save_follow_list(follow_data)

        all_checked = [
            info["predictions"][h]
            for info in follow_data.values()
            for h in ["14d", "30d", "60d"]
            if info["predictions"][h]["checked"]
        ]
        n_correct = sum(1 for p in all_checked if p["correct"])
        accuracy = (n_correct / len(all_checked)) if all_checked else None

        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric("Cards followed", len(follow_data))
        m_col2.metric("Predictions evaluated", len(all_checked))
        m_col3.metric("Accuracy", f"{accuracy:.0%}" if accuracy is not None else "-")

        st.markdown("---")

        df_watchlist = pd.DataFrame(table_rows)

        w_col1, w_col2 = st.columns(2)
        with w_col1:
            w_filter = st.selectbox("Filter by evaluation status", ["All", "Fully Evaluated", "Pending Evaluations"])
        with w_col2:
            w_sort = st.selectbox("Sort by", ["Added Day (Newest)", "Added Day (Oldest)", "Card Name"])

        status_cols = ["14d Status", "30d Status", "60d Status"]
        fully_evaluated_mask = ~df_watchlist[status_cols].apply(lambda c: c.str.contains("Pending")).any(axis=1)

        if w_filter == "Fully Evaluated":
            df_watchlist = df_watchlist[fully_evaluated_mask]
        elif w_filter == "Pending Evaluations":
            df_watchlist = df_watchlist[~fully_evaluated_mask]

        if w_sort == "Added Day (Newest)":
            df_watchlist = df_watchlist.sort_values("Added Day", ascending=False)
        elif w_sort == "Added Day (Oldest)":
            df_watchlist = df_watchlist.sort_values("Added Day", ascending=True)
        elif w_sort == "Card Name":
            df_watchlist = df_watchlist.sort_values("Card Name")

        st.dataframe(
            df_watchlist,
            column_config={
                "Image": st.column_config.ImageColumn("Card Image", width="small"),
                "Start Price": st.column_config.NumberColumn("Start Price", format="$%.2f"),
            },
            hide_index=True,
            use_container_width=True,
        )

        st.markdown("---")
        st.subheader("Manage Watchlist")
        st.caption("Remove cards permanently from the watchlist.")

        for cid_str, info in list(follow_data.items()):
            delete_col1, delete_col2, delete_col3 = st.columns([1, 5, 1])

            with delete_col1:
                image_val = info.get("image", "")
                if pd.notna(image_val) and str(image_val).strip() != "":
                    st.image(image_val, width=60)

            with delete_col2:
                st.markdown(f"**{info['name']}**")
                st.caption(
                    f"Card ID: {cid_str} · Added Day: {info['added_day']} · "
                    f"Start Price: ${info['added_price']:.2f}"
                )

            with delete_col3:
                if st.button("Delete", key=f"delete_{cid_str}", use_container_width=True):
                    del follow_data[cid_str]
                    save_follow_list(follow_data)
                    st.rerun()