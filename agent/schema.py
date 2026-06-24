"""
Introspects bank.db and produces a compact schema description for the LLM prompt.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "bank.db"

# Columns excluded from sample-row output (too long / sensitive)
_SKIP_SAMPLE = {"name"}

_EXTRA_NOTES = """
-- Key metrics stored in the loans table:
--   ead               Exposure At Default (= loan amount for drawn facilities)
--   lgd               Loss Given Default  (fraction, e.g. 0.20 = 20 %)
--   pd_estimate       Probability of Default (fraction, from company credit rating)
--   expected_loss     EAD × LGD × PD  (EUR)
--   capital_consumption  Economic capital = EAD × risk_weight × 8 %  (EUR)
--   interest_income   annual interest income (EUR)
--   cost_of_risk      = expected_loss (EUR)
--   operating_cost    annual operating cost allocated to the loan (EUR)
--   net_revenue       interest_income − cost_of_risk − operating_cost  (EUR)
--   raroc             net_revenue / capital_consumption  (ratio; × 100 = %)

-- Key metric in the companies table:
--   altman_z_score    Modified Altman Z″: > 2.9 safe, 1.23–2.9 grey, < 1.23 distress
--   pd_estimate       Company-level PD (fraction)
--   default_flag      1 if company is in default, 0 otherwise
--   client_segment    SME | Mid-Corp | Large

-- product_type values:  working_capital | term_loan | revolving_credit
-- collateral_type:      real_estate | equipment | guarantee | unsecured
-- payment_status:       on_time | late | missed
-- loan status:          active | matured | defaulted | prepaid
-- credit_rating order:  AAA > AA > A > BBB > BB > B > CCC > CC > C > D

-- Useful pre-built views:
--   v_portfolio_summary   — aggregated by country / sector / segment / rating
--   v_loan_performance    — loan-level with payment behaviour stats
--   v_risk_by_manager     — exposure, PD, RAROC, EL per relationship manager

-- Amounts are in EUR.  Divide by 1e6 to get M EUR.
-- Dates are stored as TEXT in ISO-8601 format (YYYY-MM-DD).
"""


def get_schema(db_path: Path = DB_PATH) -> str:
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    blocks = ["-- DATABASE SCHEMA (bank.db — FICTIONAL DATA)\n"]

    # Tables
    cur.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table','view') ORDER BY type DESC, name")
    objects = cur.fetchall()

    for obj_name, obj_type in objects:
        label = "TABLE" if obj_type == "table" else "VIEW"
        cur.execute(f"PRAGMA table_info({obj_name})")
        cols = cur.fetchall()

        # FK info for tables
        fk_map: dict[str, str] = {}
        if obj_type == "table":
            cur.execute(f"PRAGMA foreign_key_list({obj_name})")
            for fk in cur.fetchall():
                fk_map[fk[3]] = f"{fk[2]}({fk[4]})"   # from_col → table(to_col)

        col_lines = []
        for cid, cname, ctype, notnull, dflt, pk in cols:
            parts = [f"    {cname:<26} {ctype or 'TEXT'}"]
            if pk:
                parts.append("PRIMARY KEY")
            if notnull and not pk:
                parts.append("NOT NULL")
            if dflt is not None:
                parts.append(f"DEFAULT {dflt}")
            if cname in fk_map:
                parts.append(f"→ {fk_map[cname]}")
            col_lines.append(" ".join(parts))

        blocks.append(f"-- {label}: {obj_name}")
        blocks.append(f"CREATE {label} {obj_name} (")
        blocks.append(",\n".join(col_lines))
        blocks.append(");\n")

        # 3 sample rows (tables only, skip views for brevity)
        if obj_type == "table":
            try:
                cur.execute(f"SELECT * FROM {obj_name} LIMIT 3")
                rows = cur.fetchall()
                colnames = [d[0] for d in cur.description]
                blocks.append(f"-- Sample rows from {obj_name}:")
                for row in rows:
                    pairs = [
                        f"{c}={repr(v)}"
                        for c, v in zip(colnames, row)
                        if c not in _SKIP_SAMPLE
                    ]
                    blocks.append("--   " + ", ".join(pairs))
                blocks.append("")
            except Exception:
                pass

    con.close()
    return "\n".join(blocks) + "\n" + _EXTRA_NOTES
