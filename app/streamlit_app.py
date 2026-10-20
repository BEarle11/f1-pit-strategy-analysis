"""
streamlit_app.py - Interactive F1 strategy dashboard.

Run locally from the repo root (with your .venv active):
    streamlit run app/streamlit_app.py
"""

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

DATA_DIR = Path(__file__).parent / "data"

# Pirelli's official compound colors, so charts read like F1 TV graphics
COMPOUND_COLORS = {
    "SOFT": "#E10600",
    "MEDIUM": "#F5C400",
    "HARD": "#C8C8C8",
    "INTERMEDIATE": "#2BB24C",
    "WET": "#1E7BD9",
}

st.set_page_config(page_title="F1 Pit Strategy", page_icon="🏁", layout="wide")


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
@st.cache_data  # load the file once, not every time the user clicks something
def load_laps() -> pd.DataFrame:
    return pd.read_parquet(DATA_DIR / "laps.parquet")


laps = load_laps()

# ---------------------------------------------------------------------------
# Sidebar: pick a race
# ---------------------------------------------------------------------------
st.sidebar.title("🏁 F1 Pit Strategy")

seasons = sorted(laps["SEASON"].unique(), reverse=True)
season = st.sidebar.selectbox("Season", seasons)

races = (laps[laps["SEASON"] == season][["RACE_ROUND", "EVENT_NAME"]]
         .drop_duplicates().sort_values("RACE_ROUND"))
race_label = st.sidebar.selectbox(
    "Race",
    races["RACE_ROUND"],
    index=len(races) - 1,  # default to the most recent race
    format_func=lambda r: f"R{r} · {races.set_index('RACE_ROUND').loc[r, 'EVENT_NAME']}",
)
race = laps[(laps["SEASON"] == season) & (laps["RACE_ROUND"] == race_label)]
event_name = race["EVENT_NAME"].iloc[0]

st.title(f"{season} {event_name}")

# ---------------------------------------------------------------------------
# Chart 1: tire strategy (one bar per driver, split into stints)
# ---------------------------------------------------------------------------
st.subheader("Tire strategy")

stints = (race.dropna(subset=["STINT"])
          .groupby(["DRIVER_CODE", "TEAM", "STINT", "COMPOUND"], as_index=False)
          .agg(START=("LAP_NUMBER", "min"), END=("LAP_NUMBER", "max")))
stints["LAPS"] = stints["END"] - stints["START"] + 1

# Order drivers by laps completed, so finishers are at the top
order = (race.groupby("DRIVER_CODE")["LAP_NUMBER"].max()
         .sort_values(ascending=True).index.tolist())

fig = px.bar(
    stints, x="LAPS", y="DRIVER_CODE", base="START", color="COMPOUND",
    orientation="h", color_discrete_map=COMPOUND_COLORS,
    category_orders={"DRIVER_CODE": order},
    hover_data={"TEAM": True, "START": True, "END": True, "LAPS": True,
                "DRIVER_CODE": False},
    labels={"DRIVER_CODE": "", "LAPS": "Lap"},
)
fig.update_traces(marker_line_color="#111", marker_line_width=1.5)
fig.update_layout(height=620, bargap=0.25, legend_title_text="Compound")
st.plotly_chart(fig, width="stretch")

# ---------------------------------------------------------------------------
# Chart 2: animated tire wear (each dot is a driver; press play)
# ---------------------------------------------------------------------------
st.subheader("Tire wear, lap by lap")
st.caption("Each dot is a driver. As tires age, dots slide right and usually rise "
           "(slower laps). After a pit stop, they jump back to the left on fresh tires. "
           "Press ▶ to play the race.")

anim = race.dropna(subset=["LAP_TIME_SEC", "TYRE_LIFE", "COMPOUND"]).copy()
anim = anim[anim["LAP_NUMBER"] > 1]

# Fix the axes so they don't jump around between frames.
# The y-range ignores the slowest laps (safety cars), which would squash the chart.
y_lo = anim["LAP_TIME_SEC"].quantile(0.01) - 0.5
y_hi = anim["LAP_TIME_SEC"].quantile(0.90) + 1.0

# Built with plotly.graph_objects rather than plotly.express: express splits colors
# into separate traces, and a compound missing from lap 2 (e.g. HARD) would be
# drawn in the wrong color later in the race. Here every dot carries its own color.
def lap_trace(lap_df: pd.DataFrame) -> go.Scatter:
    return go.Scatter(
        x=lap_df["TYRE_LIFE"], y=lap_df["LAP_TIME_SEC"],
        ids=lap_df["DRIVER_CODE"],  # lets Plotly glide each driver between frames
        mode="markers+text", text=lap_df["DRIVER_CODE"], textposition="top center",
        marker=dict(size=16, color=lap_df["COMPOUND"].map(COMPOUND_COLORS),
                    line=dict(width=1, color="#111")),
        customdata=lap_df[["DRIVER_NAME", "TEAM", "COMPOUND"]],
        hovertemplate=("<b>%{customdata[0]}</b><br>%{customdata[1]}<br>"
                       "%{customdata[2]}, %{x} laps old<br>Lap time %{y:.3f}s"
                       "<extra></extra>"),
        showlegend=False,
    )


laps_in_race = sorted(anim["LAP_NUMBER"].unique())
first = anim[anim["LAP_NUMBER"] == laps_in_race[0]]

fig2 = go.Figure(
    data=[lap_trace(first)],
    frames=[go.Frame(name=str(n), data=[lap_trace(anim[anim["LAP_NUMBER"] == n])],
                     traces=[0])
            for n in laps_in_race],
)

# Legend: one fixed entry per compound used in this race
for compound in [c for c in COMPOUND_COLORS if c in set(anim["COMPOUND"])]:
    fig2.add_trace(go.Scatter(x=[None], y=[None], mode="markers", name=compound,
                              marker=dict(size=12, color=COMPOUND_COLORS[compound],
                                          line=dict(width=1, color="#111"))))

play = dict(frame=dict(duration=350, redraw=False), transition=dict(duration=250),
            fromcurrent=True, mode="immediate")
fig2.update_layout(
    height=600, legend_title_text="Compound",
    xaxis=dict(title="Laps on this set of tires", range=[0, anim["TYRE_LIFE"].max() + 2]),
    yaxis=dict(title="Lap time (s)", range=[y_lo, y_hi]),
    updatemenus=[dict(type="buttons", direction="left", x=0, y=-0.12,
                      xanchor="left", yanchor="top", showactive=False,
                      buttons=[dict(label="▶ Play", method="animate", args=[None, play]),
                               dict(label="❚❚ Pause", method="animate",
                                    args=[[None], dict(mode="immediate",
                                                       frame=dict(duration=0))])])],
    sliders=[dict(x=0.15, y=-0.08, len=0.85, currentvalue=dict(prefix="Lap ", xanchor="right", font=dict(size=16)),
                  steps=[dict(label=str(n), method="animate",
                              args=[[str(n)], dict(mode="immediate",
                                                   frame=dict(duration=0, redraw=False),
                                                   transition=dict(duration=0))])
                         for n in laps_in_race])],
    margin=dict(b=120),
)
st.plotly_chart(fig2, width="stretch")

st.caption("Data: OpenF1 · Pipeline: Python → Snowflake, updated weekly")
