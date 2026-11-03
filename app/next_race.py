"""Next race strategy: the fastest pit strategy for each team at the next race."""

import pandas as pd
import plotly.express as px
import streamlit as st

from common import load

race = load("next_race")
recs = load("strategy_next_race")
curves = load("strategy_curves")
if race is None or recs is None or curves is None:
    st.info("Strategy for the next race appears here after the weekly pipeline runs.")
    st.stop()

race = race.iloc[0]
when = pd.to_datetime(race["date"]).strftime("%B %-d, %Y") if pd.notna(race["date"]) else ""
st.title(f"Strategy for the {race['event']}")
st.caption(" · ".join(x for x in [when, "simulated for every team", "updated weekly"] if x))

c1, c2, c3, c4 = st.columns(4)
c1.metric("Race laps", int(race["laps"]))
c2.metric("Time lost per pit stop", f"{race['pit_loss']:.1f} s",
          help="Measured from real stops here: pit-in lap + pit-out lap, vs two normal laps."
          if race["pit_loss_measured"] else "Not enough stops measured here; using 22 s.")
c3.metric("Tire wear vs average circuit", f"{race['wear_factor']:.2f}×",
          help="From past races here, pulled toward 1.0× when there are few of them.")
c4.metric("Past races here in our data", int(race["past_races"]))

# ---------------------------------------------------------------------------
# The soft-tire assumption
# ---------------------------------------------------------------------------
labels = {"historical": "Softs behave like past seasons",
          "this season": "Softs behave like this season's data"}
source = st.radio(
    "Soft tire assumption", list(labels), format_func=labels.get, horizontal=True,
    help="This season's data says a new soft is no faster than a new medium and wears "
         "less, which is hard to believe and very uncertain. Past seasons show softs "
         "behaving normally. Switch to see how much the answer depends on it.")
r = recs[recs["soft_source"] == source].set_index("team")

# ---------------------------------------------------------------------------
# Headline, written from the numbers
# ---------------------------------------------------------------------------
common_plan = r["best_plan"].mode().iloc[0]
n_common = (r["best_plan"] == common_plan).sum()
one_stop = (r["stops"] == 1).mean() >= 0.5
gap = r["one_vs_two_stop_s"].median()
other = recs[recs["soft_source"] != source].set_index("team")["best_plan"]
agree = (other.reindex(r.index) == r["best_plan"]).mean()

headline = (f"**{n_common} of {len(r)} teams:** {common_plan}"
            f" ({'one stop' if one_stop else 'two stops'}). ")
if pd.notna(gap) and one_stop and gap > 0:
    headline += f"Two-stopping costs about {gap:.0f} s. "
headline += ("The other soft-tire assumption gives the same plans." if agree == 1 else
             f"With the other soft-tire assumption, {int(round((1 - agree) * len(r)))} "
             "teams get a different plan, so the choice of compounds depends on how "
             "this season's softs really behave.")
st.info(headline)

# ---------------------------------------------------------------------------
# Recommendations table
# ---------------------------------------------------------------------------
st.subheader("Best plan by team")
table = pd.DataFrame({
    "Best plan": r["best_plan"],
    "Order": r["order"],
    "Stop lap(s)": r["pit_laps"],
    "Pit window": r["window"].replace("", "—"),
    "Next best": r["next_best"],
    "Margin (s)": r["margin_s"].round(1),
    "Holds across wear range": r["robust"].map({True: "✓", False: "✗"}),
})
st.dataframe(table, width="stretch")
st.caption("**Pit window:** every stop lap within 1 s of the best. **Margin:** how much slower "
           "the next-best plan is; under ~3 s the plans are effectively tied. **Holds across "
           "wear range:** the best plan stays the same at both ends of the team's uncertainty.")

# ---------------------------------------------------------------------------
# Interactive chart for one team
# ---------------------------------------------------------------------------
st.subheader("When to stop")
team = st.selectbox("Team", r.index.tolist())
c = curves[(curves["team"] == team) & (curves["soft_source"] == source)]
fig = px.line(c, x="pit_lap", y="vs_best", color="plan",
              labels={"pit_lap": "Stop on lap", "vs_best": "Seconds slower than the best plan",
                      "plan": "One-stop plan"},
              title=f"{team}: race time for every one-stop plan and stop lap")
fig.update_traces(line=dict(width=3), hovertemplate="Stop on lap %{x}: +%{y:.1f} s")
two = c["best_two_stop"].iloc[0]
if pd.notna(two):
    fig.add_hline(y=two, line_dash="dash", line_color="#444",
                  annotation_text="best two-stop", annotation_position="top left")
fig.update_yaxes(range=[-0.5, 15])
fig.update_layout(height=480, hovermode="x unified")
st.plotly_chart(fig, width="stretch")
st.caption("The flat bottom of each curve is the pit window: stopping anywhere in it costs "
           "less than a second. Stint order doesn't change the total in this model, so each "
           "plan appears twice, mirrored.")

with st.expander("What this model leaves out"):
    st.markdown("""
- **Safety cars,** which make pit stops much cheaper and often decide strategy.
- **Track position and traffic:** each car is simulated alone, so undercuts and getting stuck behind slower cars aren't modeled.
- **Tire cliffs:** wear is a straight line, capped at stint lengths teams actually run.
- **Weather and track temperature.**
- **Starting tires:** every stint starts on a fresh set.
""")
