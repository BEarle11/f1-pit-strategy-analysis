"""Team tire wear: how hard each team's car is on its tires this season."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from common import load

wear = load("team_wear")
if wear is None:
    st.info("Team tire wear appears here after the weekly pipeline runs.")
    st.stop()

season, races = int(wear["season"].iloc[0]), int(wear["races"].iloc[0])
st.title("Team tire wear")
st.caption(f"{season} season · {races} races · updated weekly")
st.markdown("How much lap time each team loses for every lap a set of tires gets older, "
            "after removing the effect of fuel burning off. Lower is gentler on tires.")

# ---------------------------------------------------------------------------
# Headline numbers
# ---------------------------------------------------------------------------
wear["vs_field_pct"] = (wear["pooled"] / wear["field_wear"] - 1) * 100
wear["clearly"] = ((wear["high"] < wear["field_wear"]).map({True: "gentler"})
                   .fillna((wear["low"] > wear["field_wear"]).map({True: "harsher"})))
ranking = (wear.pivot(index="team", columns="compound", values="vs_field_pct")
           .assign(Average=lambda d: d.mean(axis=1)).sort_values("Average"))

c1, c2, c3 = st.columns(3)
c1.metric("Gentlest on tires", ranking.index[0], f"{ranking['Average'].iloc[0]:+.0f}% vs field",
          delta_color="inverse")
c2.metric("Hardest on tires", ranking.index[-1], f"{ranking['Average'].iloc[-1]:+.0f}% vs field",
          delta_color="inverse")
clear = wear.dropna(subset=["clearly"])
c3.metric("Clearly different from the field", f"{clear['team'].nunique()} teams",
          help="Teams whose 95% range doesn't include the field average, on either compound.")

if clear.empty:
    st.info(f"After {races} races, no team's tire wear is clearly different from the field. "
            "The rankings below are leanings, and the ranges will narrow as the season goes on.")

# ---------------------------------------------------------------------------
# Chart: each team's wear with its 95% range
# ---------------------------------------------------------------------------
compounds = [c for c in ["MEDIUM", "HARD"] if c in set(wear["compound"])]
colors = {"MEDIUM": "#C99A00", "HARD": "#6E6E6E"}
order = ranking.index[::-1].tolist()      # gentlest at the top

fig = make_subplots(rows=1, cols=len(compounds), shared_yaxes=True,
                    subplot_titles=[f"{c.title()} tires" for c in compounds])
for i, c in enumerate(compounds, 1):
    d = wear[wear["compound"] == c].set_index("team").reindex(order).dropna(subset=["pooled"])
    fig.add_trace(go.Scatter(
        x=d["pooled"], y=d.index, mode="markers", name=f"{c.title()}",
        marker=dict(size=13, color=colors[c], line=dict(width=1, color="#222")),
        error_x=dict(type="data", symmetric=False, array=d["high"] - d["pooled"],
                     arrayminus=d["pooled"] - d["low"], color=colors[c]),
        customdata=d[["vs_field_pct", "weight"]],
        hovertemplate=("<b>%{y}</b><br>%{x:.3f} s lost per lap of tire age<br>"
                       "%{customdata[0]:+.0f}% vs field<extra></extra>"),
        showlegend=False), row=1, col=i)
    fig.add_vline(x=d["field_wear"].iloc[0], line_dash="dot", line_color="gray",
                  annotation_text="field average", annotation_position="bottom right",
                  row=1, col=i)
    fig.update_xaxes(title_text="Seconds lost per lap of tire age", row=1, col=i)
fig.update_layout(height=520, margin=dict(t=60))
st.plotly_chart(fig, width="stretch")
st.caption("Dots are each team's estimate; bars are 95% ranges. A team whose bar doesn't "
           "cross the dotted line is clearly different from the field.")

# ---------------------------------------------------------------------------
# Ranking table
# ---------------------------------------------------------------------------
st.subheader("Ranking")
table = ranking.rename(columns={"MEDIUM": "Medium vs field", "HARD": "Hard vs field",
                                "Average": "Average vs field"})
st.dataframe(table, width="stretch",
             column_config={c: st.column_config.NumberColumn(format="%+.1f%%")
                            for c in table.columns})
st.caption("Negative = loses less time per lap of tire age than an average car.")

with st.expander("How this is calculated"):
    st.markdown("""
- **Model:** every clean racing lap is explained by the car's baseline pace in that race, fuel burning off (the car gets faster), and tire age (each compound gets slower at its own rate). Each team gets its own medium and hard wear rate; softs share one rate because there's too little soft data per team.
- **Clean laps only:** no lap 1, no laps 2–6 (start-of-race traffic distorts tire wear), no pit laps, no safety car or incident laps, dry tires only.
- **Partial pooling:** teams with less data are pulled toward the field average, so a few unusual laps can't make a team look extreme.
- **Ranges:** from refitting the model on 200 resampled sets of races.
- **"Team" means the car, the drivers, and their choices together.** A team that deliberately manages its tires to make a one-stop work will look gentle on tires.
""")
