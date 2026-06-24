"""
Auto-selects and renders the most appropriate Plotly chart for a query result.
"""

from __future__ import annotations
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

_PALETTE = px.colors.qualitative.Pastel


def _classify_cols(df: pd.DataFrame):
    num_cols  = df.select_dtypes(include="number").columns.tolist()
    cat_cols  = [c for c in df.columns if c not in num_cols]
    date_cols = [c for c in cat_cols if _looks_like_date(df, c)]
    cat_cols  = [c for c in cat_cols if c not in date_cols]
    return num_cols, cat_cols, date_cols


def _looks_like_date(df: pd.DataFrame, col: str) -> bool:
    if df[col].dtype == object and len(df) > 0:
        sample = str(df[col].iloc[0])
        return len(sample) >= 7 and sample[:4].isdigit() and sample[4] in ("-", "/")
    return False


def auto_chart(df: pd.DataFrame) -> go.Figure | None:
    """Return a Plotly figure or None if the data isn't chart-friendly."""
    if df.empty or len(df.columns) < 2:
        return None

    num_cols, cat_cols, date_cols = _classify_cols(df)

    # ── 1. Single numeric → histogram / single metric ─────────────────────
    if len(num_cols) == 1 and not cat_cols and not date_cols:
        if len(df) == 1:
            return None   # single cell — just show the table
        return px.histogram(
            df, x=num_cols[0],
            title=f"Distribution of {num_cols[0]}",
            color_discrete_sequence=_PALETTE,
            template="plotly_white",
        )

    # ── 2. Date + numeric → line chart ────────────────────────────────────
    if date_cols and num_cols:
        x = date_cols[0]
        y = num_cols[0]
        color = cat_cols[0] if cat_cols else None
        dfp = df.sort_values(x)
        return px.line(
            dfp, x=x, y=y, color=color,
            title=f"{y} over time",
            markers=True,
            color_discrete_sequence=_PALETTE,
            template="plotly_white",
        )

    # ── 3. Categorical + one numeric → bar chart ──────────────────────────
    if cat_cols and num_cols:
        x = cat_cols[0]
        y = num_cols[0]
        color = cat_cols[1] if len(cat_cols) > 1 else None

        # If too many categories, show only top-20 by y
        if df[x].nunique() > 25:
            df = df.nlargest(20, y)

        orientation = "h" if df[x].nunique() > 10 else "v"
        if orientation == "h":
            fig = px.bar(
                df.sort_values(y), x=y, y=x, color=color,
                orientation="h",
                title=f"{y} by {x} (top 20)",
                color_discrete_sequence=_PALETTE,
                template="plotly_white",
            )
        else:
            fig = px.bar(
                df, x=x, y=y, color=color,
                title=f"{y} by {x}",
                color_discrete_sequence=_PALETTE,
                template="plotly_white",
            )
        fig.update_layout(xaxis_tickangle=-35)
        return fig

    # ── 4. Two numerics → scatter ─────────────────────────────────────────
    if len(num_cols) >= 2:
        color = cat_cols[0] if cat_cols else None
        return px.scatter(
            df, x=num_cols[0], y=num_cols[1], color=color,
            title=f"{num_cols[1]} vs {num_cols[0]}",
            color_discrete_sequence=_PALETTE,
            template="plotly_white",
            opacity=0.7,
        )

    return None
