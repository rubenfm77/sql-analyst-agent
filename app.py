"""
SQL Analyst Agent — Streamlit entry point.
Ask business questions in plain English; get SQL, a result table, and a chart.
"""

from __future__ import annotations
import textwrap
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

import pandas as pd
import streamlit as st

from agent.llm_client import make_client
from agent.prompt     import build_system, build_user
from agent.schema     import get_schema
from agent.sql_runner import run as run_sql, SQLError, UnsafeQueryError, validate
from data.seed        import DISCLAIMER, seed as rebuild_db
from ui.chart         import auto_chart

DB_PATH = Path(__file__).parent / "bank.db"

# ─── Auto-seed on first run (handles Streamlit Cloud cold starts) ─────────────
if not DB_PATH.exists():
    with st.spinner("Building synthetic banking database — this takes ~10 seconds on first run …"):
        rebuild_db(DB_PATH)
    st.cache_data.clear()

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

# ─────────────────────────── Page config ─────────────────────────────────────
st.set_page_config(
    page_title="SQL Analyst Agent · SME Credit Portfolio",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────── CSS ─────────────────────────────────────────────
st.markdown("""
<style>
    /* Dark SQL code block */
    .sql-box {
        background: #0d1117;
        color: #79c0ff;
        padding: 1rem 1.2rem;
        border-radius: 8px;
        font-family: 'Fira Code', 'Cascadia Code', monospace;
        font-size: 0.82rem;
        white-space: pre-wrap;
        border-left: 4px solid #1f6feb;
        line-height: 1.6;
    }
    /* Disclaimer banner */
    .disclaimer {
        background: #fff8e1;
        color: #7d5a00;
        padding: 0.5rem 1rem;
        border-radius: 6px;
        font-size: 0.76rem;
        border-left: 3px solid #f9a825;
        margin-bottom: 1rem;
    }
    /* KPI cards */
    .kpi-card {
        background: #f0f4ff;
        border: 1px solid #d0d9f5;
        border-radius: 10px;
        padding: 0.9rem 1rem;
        text-align: center;
    }
    .kpi-val  { font-size: 1.6rem; font-weight: 700; color: #1a237e; }
    .kpi-lbl  { font-size: 0.75rem; color: #546e7a; margin-top: 2px; }
    /* Hide Streamlit branding on sample-Q buttons */
    div[data-testid="stVerticalBlock"] button { font-size: 0.8rem !important; }
    /* Step badges */
    .step-badge {
        display: inline-block;
        background: #1f6feb;
        color: white;
        border-radius: 50%;
        width: 22px; height: 22px;
        line-height: 22px;
        text-align: center;
        font-size: 0.75rem;
        font-weight: bold;
        margin-right: 6px;
    }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────── Helpers ─────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=300)
def _get_schema() -> str:
    return get_schema(DB_PATH) if DB_PATH.exists() else ""


@st.cache_data(show_spinner=False, ttl=60)
def _portfolio_kpis() -> dict:
    if not DB_PATH.exists():
        return {}
    try:
        df = run_sql("""
            SELECT
                COUNT(DISTINCT c.company_id)             AS n_companies,
                COUNT(l.loan_id)                         AS n_loans,
                ROUND(SUM(l.amount)/1e6, 1)              AS exposure_meur,
                ROUND(AVG(l.raroc)*100, 2)               AS avg_raroc_pct,
                ROUND(SUM(l.expected_loss)/1e6, 2)       AS total_el_meur,
                ROUND(SUM(l.capital_consumption)/1e6, 2) AS total_capital_meur,
                ROUND(AVG(c.pd_estimate)*100, 3)         AS avg_pd_pct,
                ROUND(SUM(c.default_flag)*100.0/COUNT(DISTINCT c.company_id), 1) AS default_rate_pct
            FROM companies c
            JOIN loans l ON l.company_id = c.company_id
        """, DB_PATH)
        return df.iloc[0].to_dict() if not df.empty else {}
    except Exception:
        return {}


def _kpi(col, value, label, prefix="", suffix=""):
    with col:
        st.markdown(
            f'<div class="kpi-card">'
            f'<div class="kpi-val">{prefix}{value}{suffix}</div>'
            f'<div class="kpi-lbl">{label}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ─────────────────────────── Sidebar ─────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏦 SQL Analyst Agent")
    st.caption("Ask banking questions in plain English.\nPowered by Groq · Llama 3.3 70B.")
    st.divider()

    # ── API Key ──────────────────────────────────────────────────────────
    st.subheader("🔑 Groq API Key")
    import os
    env_key = os.environ.get("GROQ_API_KEY", "")
    if env_key:
        st.success("Key loaded from environment ✓")
        st.session_state["api_key"] = env_key
    else:
        typed_key = st.text_input(
            "Paste your key (free at console.groq.com)",
            value=st.session_state.get("api_key", ""),
            type="password",
            placeholder="gsk_...",
            label_visibility="collapsed",
        )
        if typed_key:
            st.session_state["api_key"] = typed_key
            st.success("Key saved for this session ✓")
        else:
            st.warning("No key — LLM calls will fail.")

    st.divider()

    # ── Database ─────────────────────────────────────────────────────────
    st.subheader("🗄️ Database")
    db_ok = DB_PATH.exists()
    if db_ok:
        size_kb = DB_PATH.stat().st_size // 1024
        st.success(f"bank.db ready · {size_kb:,} KB")
    else:
        st.error("bank.db missing")

    if st.button("🔄 Reset & Rebuild", use_container_width=True, help="Drops and regenerates bank.db from scratch"):
        with st.spinner("Generating 2 000 companies · ~6 k loans · ~120 k payments …"):
            try:
                rebuild_db(DB_PATH)
                st.cache_data.clear()
                st.rerun()
            except Exception as exc:
                st.error(f"Seed error: {exc}")

    st.divider()

    # ── Sample questions ──────────────────────────────────────────────────
    st.subheader("💡 Try a question")
    for q in SAMPLE_QUESTIONS:
        if st.button(q, use_container_width=True, key=f"sq_{q[:32]}"):
            st.session_state["_pending_q"] = q
            st.rerun()

    st.divider()
    with st.expander("ℹ️ Schema & metrics"):
        st.markdown("""
**Tables:** `companies` · `loans` · `payments`

**Views:** `v_portfolio_summary` · `v_loan_performance` · `v_risk_by_manager`

**Risk metrics (loans):**
`ead` · `lgd` · `pd_estimate` · `expected_loss` · `capital_consumption` · `raroc` · `cost_of_risk` · `net_revenue`

**Company metrics:**
`altman_z_score` · `pd_estimate` · `credit_rating` · `default_flag`

All amounts in EUR · dates ISO-8601
        """)

# ─────────────────────────── Main — Header ───────────────────────────────────
st.markdown(f'<div class="disclaimer">⚠️ {DISCLAIMER}</div>', unsafe_allow_html=True)
st.markdown("# 🏦 SME Credit Portfolio — NL Analytics")

# ─────────────────────────── Portfolio KPIs ──────────────────────────────────
kpis = _portfolio_kpis()
if kpis:
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    _kpi(k1, f"{kpis.get('n_companies', 0):,.0f}",     "Companies",          suffix="")
    _kpi(k2, f"{kpis.get('exposure_meur', 0):,.0f}",   "Total Exposure",     suffix=" M€")
    _kpi(k3, f"{kpis.get('avg_raroc_pct', 0):,.1f}",   "Avg RAROC",          suffix="%")
    _kpi(k4, f"{kpis.get('total_el_meur', 0):,.1f}",   "Total Exp. Loss",    suffix=" M€")
    _kpi(k5, f"{kpis.get('avg_pd_pct', 0):,.2f}",      "Avg PD",             suffix="%")
    _kpi(k6, f"{kpis.get('default_rate_pct', 0):,.1f}","Default Rate",       suffix="%")
    st.markdown("")   # spacer

elif not db_ok:
    st.info("👈 Click **Rebuild bank.db** in the sidebar to generate the dataset, then come back here.")
    st.stop()

st.divider()

# ─────────────────────────── Question input ───────────────────────────────────
# Apply pending question from sample-question buttons
if "_pending_q" in st.session_state:
    st.session_state["question_input"] = st.session_state.pop("_pending_q")

st.markdown("### Ask a question in plain English")

question = st.text_area(
    "question",
    value=st.session_state.get("question_input", ""),
    placeholder="e.g.  Which relationship managers have the highest average PD across their portfolio?",
    height=80,
    label_visibility="collapsed",
    key="question_input",
)

col_run, col_clear, col_gap = st.columns([2, 1, 4])
with col_run:
    api_key_ok = bool(st.session_state.get("api_key", ""))
    run_clicked = st.button(
        "▶  Generate & Run",
        type="primary",
        use_container_width=True,
        disabled=not (db_ok and api_key_ok),
    )
with col_clear:
    if st.button("✕ Clear", use_container_width=True):
        st.session_state["question_input"] = ""
        st.rerun()

if not api_key_ok and db_ok:
    st.caption("⚠️ Paste your Groq API key in the sidebar to enable query generation.")

# ─────────────────────────── Execution ───────────────────────────────────────
if run_clicked and question.strip():

    schema = _get_schema()

    # Step 1 — LLM
    st.markdown("---")
    st.markdown('<span class="step-badge">1</span> **Generating SQL…**', unsafe_allow_html=True)
    t0 = time.perf_counter()
    with st.spinner("Calling Groq · Llama 3.3 70B …"):
        try:
            client   = make_client(api_key=st.session_state.get("api_key"))
            raw_sql  = client.complete(build_system(schema), build_user(question))
            elapsed  = time.perf_counter() - t0
        except Exception as exc:
            st.error(f"LLM error: {exc}")
            st.stop()

    st.caption(f"Generated in {elapsed:.2f}s · model: llama-3.3-70b-versatile · Groq")

    # Step 2 — Validate
    try:
        clean_sql = validate(raw_sql)
    except UnsafeQueryError as exc:
        st.error(f"Blocked unsafe query: {exc}")
        st.markdown(f'<div class="sql-box">{raw_sql}</div>', unsafe_allow_html=True)
        st.stop()

    with st.expander("📋 Generated SQL", expanded=True):
        st.markdown(f'<div class="sql-box">{clean_sql}</div>', unsafe_allow_html=True)

    # Step 3 — Run SQL
    st.markdown('<span class="step-badge">2</span> **Running query…**', unsafe_allow_html=True)
    try:
        t1 = time.perf_counter()
        df = run_sql(clean_sql, DB_PATH)
        qt = time.perf_counter() - t1
    except SQLError as exc:
        st.error(f"SQL error: {exc}")
        st.stop()

    # Step 4 — Show results + chart
    st.markdown('<span class="step-badge">3</span> **Results**', unsafe_allow_html=True)
    st.caption(f"{len(df):,} rows · {qt*1000:.0f} ms")

    if df.empty:
        st.info("Query returned no rows.")
    else:
        tab_table, tab_chart = st.tabs(["📊 Table", "📈 Chart"])

        with tab_table:
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                height=min(500, 45 + len(df) * 36),
            )
            csv = df.to_csv(index=False).encode()
            st.download_button(
                "⬇ Download CSV",
                csv,
                file_name="query_result.csv",
                mime="text/csv",
            )

        with tab_chart:
            fig = auto_chart(df)
            if fig:
                fig.update_layout(margin=dict(t=40, b=20, l=10, r=10), height=420)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(
                    "No chart available for this result shape. "
                    "Try a query with at least one category and one number."
                )

    # Step 5 — History
    hist = st.session_state.setdefault("history", [])
    hist.insert(0, {"q": question, "sql": clean_sql, "rows": len(df), "cols": list(df.columns)})
    st.session_state["history"] = hist[:10]

# ─────────────────────────── Query history ───────────────────────────────────
hist = st.session_state.get("history", [])
if hist:
    st.divider()
    with st.expander(f"🕑 Query history ({len(hist)} recent)", expanded=False):
        for i, h in enumerate(hist):
            c1, c2 = st.columns([1, 10])
            c1.markdown(f"**Q{i+1}**")
            c2.markdown(f"*{h['q']}*")
            st.markdown(
                f'<div class="sql-box">{textwrap.shorten(h["sql"], 400, placeholder=" …")}</div>',
                unsafe_allow_html=True,
            )
            st.caption(f"{h['rows']:,} rows · columns: {', '.join(h['cols'][:8])}")
            if i < len(hist) - 1:
                st.divider()
