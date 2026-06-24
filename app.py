"""
SQL Analyst Agent — Streamlit entry point.
Ask business questions in plain English; get SQL, a result table, and a chart.
"""

from __future__ import annotations
import textwrap
import time
from pathlib import Path

import pandas as pd
import streamlit as st

from agent.llm_client import default_client
from agent.prompt     import build_system, build_user
from agent.schema     import get_schema
from agent.sql_runner import run as run_sql, SQLError, UnsafeQueryError, validate
from data.seed        import DISCLAIMER, seed as rebuild_db
from ui.chart         import auto_chart

DB_PATH = Path(__file__).parent / "bank.db"

SAMPLE_QUESTIONS = [
    "What is the total exposure and average RAROC by country?",
    "Show me the top 10 companies by capital consumption",
    "What is the non-performing loan ratio by sector?",
    "Compare cost of risk between working capital, term loans, and revolving credit",
    "Which relationship managers have the highest average PD across their portfolio?",
    "Show the distribution of credit ratings by client segment",
    "Which companies have PD above 10% and total loan exposure above 5M EUR?",
    "What is the expected loss trend by loan origination year?",
    "Top 15 loans by RAROC in the active portfolio",
    "Show average Altman Z-score and default rate by country and sector",
    "What share of payments are late or missed, grouped by credit rating?",
    "Show exposure breakdown by product type and collateral type",
]


# ─────────────────────────── Page config ────────────────────────────────────
st.set_page_config(
    page_title="SQL Analyst Agent",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ─────────────────────────── CSS tweaks ─────────────────────────────────────
st.markdown("""
<style>
    .sql-box {
        background: #1e1e2e;
        color: #cdd6f4;
        padding: 1rem 1.2rem;
        border-radius: 8px;
        font-family: 'Fira Code', monospace;
        font-size: 0.85rem;
        white-space: pre-wrap;
        border-left: 3px solid #89b4fa;
    }
    .disclaimer {
        background: #fff3cd;
        color: #856404;
        padding: 0.6rem 1rem;
        border-radius: 6px;
        font-size: 0.78rem;
        margin-bottom: 0.5rem;
    }
    .metric-card {
        background: #f8f9fa;
        border-radius: 8px;
        padding: 0.7rem 1rem;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────── Sidebar ────────────────────────────────────────
with st.sidebar:
    st.title("🏦 SQL Analyst Agent")
    st.caption("Natural-language analytics on a synthetic SME credit portfolio.")

    st.divider()
    st.subheader("Database")

    if not DB_PATH.exists():
        st.warning("bank.db not found — rebuild required.")

    if st.button("🔄 Rebuild bank.db", use_container_width=True):
        with st.spinner("Seeding database (2 000 companies, ~8 k loans) …"):
            try:
                rebuild_db(DB_PATH)
                st.cache_data.clear()
                st.success("Database rebuilt.")
            except Exception as exc:
                st.error(f"Seed failed: {exc}")

    st.divider()
    st.subheader("Sample questions")
    for q in SAMPLE_QUESTIONS:
        if st.button(q, use_container_width=True, key=f"sq_{q[:30]}"):
            st.session_state["question_input"] = q

    st.divider()
    with st.expander("ℹ️ About"):
        st.markdown("""
**Stack:** Python 3.11 · Streamlit · SQLite · Pandas · Plotly · Groq (Llama 3.3 70B)

**Tables:** `companies`, `loans`, `payments`

**Views:** `v_portfolio_summary`, `v_loan_performance`, `v_risk_by_manager`

**Key metrics available:** RAROC, Expected Loss, PD, LGD, EAD, Capital Consumption, Altman Z-score, Cost of Risk, NPL ratio

[GitHub](https://github.com/rubenfm77/sql-analyst-agent)
        """)


# ─────────────────────────── Schema (cached) ────────────────────────────────
@st.cache_data(show_spinner=False)
def _get_schema() -> str:
    if not DB_PATH.exists():
        return ""
    return get_schema(DB_PATH)


# ─────────────────────────── LLM client (cached) ────────────────────────────
@st.cache_resource(show_spinner=False)
def _get_client():
    return default_client()


# ─────────────────────────── Main area ──────────────────────────────────────
st.markdown(f'<div class="disclaimer">⚠️ {DISCLAIMER}</div>', unsafe_allow_html=True)

col_title, col_status = st.columns([5, 1])
with col_title:
    st.header("Ask a business question")
with col_status:
    db_ok = DB_PATH.exists()
    st.metric("DB", "✅ Ready" if db_ok else "❌ Missing")

question = st.text_area(
    "Question",
    value=st.session_state.get("question_input", ""),
    placeholder="e.g. What is the total exposure and average RAROC by country?",
    height=80,
    label_visibility="collapsed",
    key="question_input",
)

col_run, col_clear = st.columns([2, 1])
with col_run:
    run_clicked = st.button("▶  Generate & Run", type="primary", use_container_width=True, disabled=not db_ok)
with col_clear:
    if st.button("✕  Clear", use_container_width=True):
        st.session_state["question_input"] = ""
        st.rerun()

# ─────────────────────────── Execution ──────────────────────────────────────
if run_clicked and question.strip():
    schema = _get_schema()
    if not schema:
        st.error("Database not found. Use **Rebuild bank.db** in the sidebar.")
        st.stop()

    # ── Step 1: Generate SQL ─────────────────────────────────────────────
    with st.status("Calling LLM…", expanded=True) as status:
        t0 = time.perf_counter()
        try:
            client   = _get_client()
            system_p = build_system(schema)
            user_p   = build_user(question)
            raw_sql  = client.complete(system_p, user_p)
            elapsed  = time.perf_counter() - t0
            status.update(label=f"SQL generated in {elapsed:.1f}s", state="complete")
        except Exception as exc:
            status.update(label="LLM call failed", state="error")
            st.error(f"LLM error: {exc}")
            st.stop()

    # ── Step 2: Validate & display SQL ──────────────────────────────────
    try:
        clean_sql = validate(raw_sql)
    except UnsafeQueryError as exc:
        st.error(f"Unsafe query blocked: {exc}")
        st.markdown(f'<div class="sql-box">{raw_sql}</div>', unsafe_allow_html=True)
        st.stop()

    with st.expander("Generated SQL", expanded=True):
        st.markdown(f'<div class="sql-box">{clean_sql}</div>', unsafe_allow_html=True)
        st.caption(f"Model: llama-3.3-70b-versatile · Groq · {elapsed:.2f}s")

    # ── Step 3: Run SQL ──────────────────────────────────────────────────
    with st.spinner("Running query…"):
        try:
            t1  = time.perf_counter()
            df  = run_sql(clean_sql, DB_PATH)
            qt  = time.perf_counter() - t1
        except SQLError as exc:
            st.error(f"SQL error: {exc}")
            st.stop()

    # ── Step 4: Results ──────────────────────────────────────────────────
    st.divider()
    r_col, c_col = st.columns([3, 5])

    with r_col:
        st.subheader(f"Results — {len(df):,} rows  ({qt*1000:.0f} ms)")
        if df.empty:
            st.info("Query returned no rows.")
        else:
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                height=min(400, 40 + len(df) * 35),
            )
            csv = df.to_csv(index=False).encode()
            st.download_button("⬇ Download CSV", csv, "results.csv", "text/csv")

    with c_col:
        st.subheader("Chart")
        if not df.empty:
            fig = auto_chart(df)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No suitable chart for this result shape.")

    # ── Step 5: History ──────────────────────────────────────────────────
    if "history" not in st.session_state:
        st.session_state["history"] = []
    st.session_state["history"].insert(0, {
        "question": question,
        "sql": clean_sql,
        "rows": len(df),
        "cols": list(df.columns),
    })
    st.session_state["history"] = st.session_state["history"][:10]

elif not db_ok:
    st.info("No database found. Click **Rebuild bank.db** in the sidebar to generate the synthetic dataset.")

# ─────────────────────────── Query history ──────────────────────────────────
history = st.session_state.get("history", [])
if history:
    st.divider()
    with st.expander(f"Query history ({len(history)} recent)", expanded=False):
        for i, h in enumerate(history):
            st.markdown(f"**Q{i+1}:** {h['question']}")
            st.markdown(
                f'<div class="sql-box">{textwrap.shorten(h["sql"], 300)}</div>',
                unsafe_allow_html=True,
            )
            st.caption(f"{h['rows']} rows · columns: {', '.join(h['cols'][:8])}")
            st.divider()
