"""
streamlit_app.py - Interactive F1 strategy dashboard.

Run locally from the repo root (with your .venv active):
    streamlit run app/streamlit_app.py

This file only sets up the pages; each page lives in its own file.
"""

import streamlit as st

from common import load

st.set_page_config(page_title="F1 Pit Strategy", page_icon="🏁", layout="wide")

page = st.navigation([
    st.Page("race_explorer.py", title="Race explorer", icon="🏁", default=True),
    st.Page("team_wear.py", title="Team tire wear", icon="📉"),
    st.Page("next_race.py", title="Next race strategy", icon="🧭"),
])

st.sidebar.title("F1 Pit Strategy")
laps = load("laps")
if laps is not None:
    latest = laps.sort_values(["SEASON", "RACE_ROUND"]).iloc[-1]
    st.sidebar.caption(f"Data through the {latest['SEASON']} {latest['EVENT_NAME']} · "
                       "updated weekly")

page.run()
