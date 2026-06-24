# SQL Analyst Agent 🏦

> **⚠️ DISCLAIMER: All data in this project is entirely fictional and randomly generated. No real companies, financial institutions, or individuals are represented.**

A deploy-ready Streamlit app that translates plain-English business questions into SQL queries, executes them against a synthetic SME credit portfolio, and renders an auto-selected chart — demonstrating LLM tooling, SQL, and BI for regulated banking.

---

## Demo

| Ask a question | Get SQL + results + chart |
|---|---|
| *"What is the total exposure and average RAROC by country?"* | Bar chart of RAROC across 15 European countries |
| *"Which relationship managers have the highest average PD?"* | Ranked table + horizontal bar |
| *"Show NPL ratio by sector"* | Sector-level non-performing loan breakdown |

---

## Stack

| Layer | Technology |
|---|---|
| UI | Streamlit 1.35+ |
| LLM | Groq API · Llama 3.3 70B Versatile (free tier) |
| Database | SQLite (stdlib `sqlite3`) |
| Data processing | Pandas 2.x |
| Charts | Plotly Express |
| Python | 3.11+ |

---

## Architecture

```
sql-analyst-agent/
├── app.py                  # Streamlit UI
├── agent/
│   ├── llm_client.py       # LLMClient protocol + GroqClient implementation
│   ├── prompt.py           # System / user prompt builders
│   ├── schema.py           # DB introspection → compact schema string
│   └── sql_runner.py       # Safe SELECT execution (validation + timeout)
├── ui/
│   └── chart.py            # Auto-chart selection logic
├── data/
│   └── seed.py             # Synthetic data generator (reproducible, idempotent)
└── bank.db                 # Generated at runtime (git-ignored)
```

The LLM backend is hidden behind an `LLMClient` protocol — swap Groq for any OpenAI-compatible provider by implementing `.complete(system, user) → str`.

---

## Synthetic Database

Seeded with a fixed random seed (reproducible):

| Table | Rows | Description |
|---|---|---|
| `companies` | ~2 000 | SME / Mid-Corp / Large across 15 EU countries, 15 NACE sectors |
| `loans` | ~8 000 | 3 product types: working capital, term loan, revolving credit |
| `payments` | ~60 000 | Monthly payment schedule with days-past-due tracking |

**Pre-built views:** `v_portfolio_summary`, `v_loan_performance`, `v_risk_by_manager`

### Key credit-risk metrics (stored as columns)

| Metric | Description |
|---|---|
| `pd_estimate` | Probability of Default (from Altman Z-score → credit rating mapping) |
| `lgd` | Loss Given Default (driven by collateral type) |
| `ead` | Exposure at Default |
| `expected_loss` | EAD × LGD × PD |
| `capital_consumption` | Economic capital (Basel-II simplified: EAD × RW × 8%) |
| `raroc` | Risk-Adjusted Return on Capital = net_revenue / capital_consumption |
| `cost_of_risk` | = expected_loss (annual provision) |
| `altman_z_score` | Modified Altman Z″ score (safe > 2.9, grey 1.23–2.9, distress < 1.23) |

---

## Quick start

```bash
# 1. Clone & install
git clone https://github.com/rubenfm77/sql-analyst-agent.git
cd sql-analyst-agent
pip install -r requirements.txt

# 2. Set your Groq API key (free at console.groq.com)
cp .env.example .env
# edit .env → GROQ_API_KEY=gsk_...

# 3. Run the app
streamlit run app.py
```

On first run click **Rebuild bank.db** in the sidebar to generate the synthetic dataset.

### Streamlit Cloud

Add `GROQ_API_KEY` to **Secrets** (`.streamlit/secrets.toml`) and deploy. The database is rebuilt on first click inside the app.

---

## Safety design

- Only `SELECT` statements accepted — DDL/DML keywords are blocked before execution.
- 15-second query timeout via a background thread.
- 500-row cap injected automatically if `LIMIT` is absent.
- No secrets in code; key read from env / Streamlit secrets.

---

## Conclusions

The agent correctly answers a broad range of analytical questions including:

- **Portfolio concentration** (exposure by country / sector / rating)
- **Credit risk analytics** (expected loss, capital consumption, RAROC league tables)
- **Payment behaviour** (NPL ratios, days-past-due distribution)
- **RM performance** (average PD, RAROC and default counts per manager)

The Altman Z-score → rating → PD chain produces realistic grade distributions (roughly 40% investment grade, 40% sub-investment grade, 20% distressed/default), making the dataset analytically interesting without being trivially clean.

RAROC varies from negative (high-PD, unsecured, low-rate deals) to >100% (highly collateralised, prime-rated term loans), reflecting real-world portfolio heterogeneity.

---

*Portfolio project by Rubén F.M. · [rubenfm77.github.io/PORTFOLIO](https://rubenfm77.github.io/PORTFOLIO)*
