"""Shared settings and data loading for every page of the app."""

from pathlib import Path

import pandas as pd
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


@st.cache_data  # read each file once, not every time the user clicks something
def load(name: str) -> pd.DataFrame | None:
    """Read app/data/<name>.parquet, or None if the pipeline hasn't made it yet."""
    path = DATA_DIR / f"{name}.parquet"
    return pd.read_parquet(path) if path.exists() else None
