"""
Seed script — generates bank.db with synthetic SME credit portfolio data.
ALL DATA IS FICTIONAL. Run directly: python data/seed.py [--db path/to/bank.db]
"""

import sqlite3
import argparse
import random
from datetime import date, timedelta
from pathlib import Path
import math

DISCLAIMER = (
    "ALL DATA IN THIS DATABASE IS ENTIRELY FICTIONAL AND RANDOMLY GENERATED. "
    "No real companies, institutions, or individuals are represented. "
    "This dataset exists solely for portfolio / demonstration purposes."
)

SEED = 42
DB_PATH = Path(__file__).parent.parent / "bank.db"

COUNTRIES = [
    "Germany", "France", "Spain", "Italy", "Netherlands",
    "Belgium", "Portugal", "Poland", "Czech Republic", "Hungary",
    "Romania", "Austria", "Sweden", "Denmark", "Finland",
]

SECTORS = [
    "Manufacturing", "Wholesale Trade", "Retail Trade", "Construction",
    "Professional Services", "IT & Technology", "Food & Beverage",
    "Healthcare", "Real Estate", "Logistics & Transport",
    "Energy", "Agriculture", "Financial Services", "Hotels & Tourism",
    "Chemicals",
]

PRODUCT_TYPES = ["working_capital", "term_loan", "revolving_credit"]
COLLATERAL_TYPES = ["real_estate", "equipment", "guarantee", "unsecured"]

RELATIONSHIP_MANAGERS = [
    "Anna Schmidt", "Pierre Dupont", "Carlos García", "Luca Rossi",
    "Sophie Janssen", "Thomas Müller", "Elena Popescu", "Jakub Novak",
    "Maria Santos", "Lars Eriksson", "Katarzyna Kowalski", "Marco Bianchi",
    "Isabelle Martin", "Henrik Nielsen", "Päivi Virtanen", "David Fernandez",
    "Claudia Weber", "Andrei Ionescu", "Zsolt Nagy", "Barbora Horakova",
]

CLIENT_SEGMENTS = ["SME", "Mid-Corp", "Large"]

RATING_SCALE = ["AAA", "AA", "A", "BBB", "BB", "B", "CCC", "CC", "C", "D"]

PD_BY_RATING = {
    "AAA": 0.0001, "AA": 0.0002, "A": 0.0005, "BBB": 0.001,
    "BB": 0.005,   "B": 0.02,   "CCC": 0.10,  "CC": 0.20,
    "C": 0.40,     "D": 1.00,
}

LGD_BY_COLLATERAL = {
    "real_estate": 0.20,
    "equipment": 0.35,
    "guarantee": 0.45,
    "unsecured": 0.60,
}

RISK_WEIGHT_BY_RATING = {
    "AAA": 0.20, "AA": 0.20, "A": 0.50, "BBB": 1.00,
    "BB": 1.00,  "B": 1.50,  "CCC": 1.50, "CC": 1.50,
    "C": 1.50,   "D": 1.50,
}

# Operating cost as fraction of loan amount (annualised)
OPERATING_COST_RATIO = 0.008


def altman_z(working_capital, total_assets, ebitda, equity, total_liabilities, revenue):
    if total_assets == 0 or total_liabilities == 0:
        return 1.5
    x1 = working_capital / total_assets
    x2 = (ebitda * 0.4) / total_assets          # proxy for retained earnings
    x3 = ebitda / total_assets
    x4 = equity / max(total_liabilities, 1)
    x5 = revenue / total_assets
    return 0.717 * x1 + 0.847 * x2 + 3.107 * x3 + 0.420 * x4 + 0.998 * x5


def rating_from_z(z: float) -> str:
    if z > 4.0:   return "AAA"
    if z > 3.5:   return "AA"
    if z > 3.0:   return "A"
    if z > 2.5:   return "BBB"
    if z > 2.0:   return "BB"
    if z > 1.5:   return "B"
    if z > 1.2:   return "CCC"
    if z > 0.8:   return "CC"
    if z > 0.4:   return "C"
    return "D"


def rand_date(rng, start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=rng.randint(0, delta))


def build_companies(rng, n=2000):
    rows = []
    for i in range(1, n + 1):
        country = rng.choice(COUNTRIES)
        sector = rng.choice(SECTORS)
        segment = rng.choices(CLIENT_SEGMENTS, weights=[0.60, 0.30, 0.10])[0]

        # Size drives revenue range
        size_factor = {"SME": 1, "Mid-Corp": 8, "Large": 40}[segment]
        employees = int(rng.lognormvariate(math.log(50 * size_factor), 0.8))
        employees = max(5, min(employees, 50_000))

        revenue = round(rng.lognormvariate(math.log(2_000_000 * size_factor), 0.9), 2)
        ebitda_margin = rng.uniform(0.02, 0.28)
        ebitda = round(revenue * ebitda_margin, 2)

        asset_turnover = rng.uniform(0.4, 1.8)
        total_assets = round(revenue / asset_turnover, 2)
        leverage = rng.uniform(0.30, 0.80)
        total_liabilities = round(total_assets * leverage, 2)
        equity = round(total_assets - total_liabilities, 2)
        working_capital = round(total_assets * rng.uniform(0.05, 0.30), 2)

        z = altman_z(working_capital, total_assets, ebitda, equity, total_liabilities, revenue)
        z = round(z + rng.gauss(0, 0.15), 4)   # add small noise
        rating = rating_from_z(z)
        pd_est = round(PD_BY_RATING[rating] * rng.uniform(0.8, 1.2), 6)
        default_flag = 1 if rating in ("D",) else (1 if (rating == "C" and rng.random() < 0.5) else 0)

        founded = rng.randint(1950, 2020)
        onboarding = rand_date(rng, date(2010, 1, 1), date(2024, 12, 31))
        rm = rng.choice(RELATIONSHIP_MANAGERS)

        # Fictitious company name
        adjectives = ["Euro", "Nord", "Trans", "Alpha", "Prime", "Inter", "Global", "Metro",
                      "Capital", "Allied", "Crown", "Peak", "Apex", "Delta", "Atlas"]
        nouns = ["Group", "Industries", "Solutions", "Holdings", "Partners", "Ventures",
                 "Systems", "Services", "Works", "Corp", "Ltd", "GmbH", "SA", "SRL", "BV"]
        name = f"{rng.choice(adjectives)} {rng.choice(nouns)} {i:04d}"

        rows.append((
            i, name, country, sector, founded, employees,
            round(revenue, 2), round(ebitda, 2),
            round(ebitda_margin, 4),
            round(total_assets, 2), round(total_liabilities, 2), round(equity, 2),
            round(working_capital, 2),
            round(z, 4), rating, pd_est, default_flag,
            segment, rm, onboarding.isoformat(),
        ))
    return rows


def build_loans(rng, companies):
    rows = []
    loan_id = 1
    for comp in companies:
        cid          = comp[0]
        total_assets = comp[9]
        rating       = comp[14]
        pd_est       = comp[15]
        default_flag = comp[16]
        segment      = comp[17]

        n_loans = rng.randint(1, 5)
        for _ in range(n_loans):
            product = rng.choice(PRODUCT_TYPES)
            col_type = rng.choices(
                COLLATERAL_TYPES,
                weights=[0.35, 0.25, 0.20, 0.20]
            )[0]
            lgd = LGD_BY_COLLATERAL[col_type]

            # Loan amount as fraction of total_assets
            max_frac = {"SME": 0.25, "Mid-Corp": 0.35, "Large": 0.45}[segment]
            amount = round(total_assets * rng.uniform(0.02, max_frac), 2)
            collateral_value = round(amount * rng.uniform(0.5, 1.8) if col_type != "unsecured" else 0, 2)

            orig = rand_date(rng, date(2018, 1, 1), date(2024, 6, 30))
            tenor_months = rng.choice([12, 24, 36, 48, 60, 84]) if product == "term_loan" else rng.choice([12, 24, 36])
            maturity = orig + timedelta(days=tenor_months * 30)

            base_rate = rng.uniform(0.025, 0.045)
            credit_spread = {
                "AAA": 0.003, "AA": 0.005, "A": 0.008, "BBB": 0.015,
                "BB": 0.030, "B": 0.060, "CCC": 0.120, "CC": 0.180,
                "C": 0.250, "D": 0.300,
            }[rating]
            rate = round(base_rate + credit_spread + rng.uniform(-0.005, 0.005), 5)

            if default_flag and rng.random() < 0.7:
                status = "defaulted"
            elif maturity < date(2025, 1, 1):
                status = rng.choices(["matured", "prepaid"], weights=[0.8, 0.2])[0]
            else:
                status = "active"

            ead = amount
            rw = RISK_WEIGHT_BY_RATING[rating]
            capital_consumption = round(ead * rw * 0.08, 2)
            expected_loss = round(ead * lgd * pd_est, 2)
            interest_income = round(amount * rate, 2)
            operating_cost = round(amount * OPERATING_COST_RATIO, 2)
            cost_of_risk = expected_loss
            net_revenue = round(interest_income - cost_of_risk - operating_cost, 2)
            raroc = round(net_revenue / capital_consumption, 6) if capital_consumption > 0 else 0.0

            rows.append((
                loan_id, cid, product, round(amount, 2), "EUR",
                orig.isoformat(), maturity.isoformat(), round(rate, 5), status,
                col_type, round(collateral_value, 2),
                round(ead, 2), round(lgd, 4), round(pd_est, 6),
                round(expected_loss, 2), round(capital_consumption, 2),
                round(interest_income, 2), round(operating_cost, 2),
                round(cost_of_risk, 2), round(net_revenue, 2), round(raroc, 6),
            ))
            loan_id += 1
    return rows


def build_payments(rng, loans):
    rows = []
    pay_id = 1
    today = date(2025, 6, 24)

    for loan in loans:
        lid      = loan[0]
        orig_str = loan[5]
        mat_str  = loan[6]
        amount   = loan[3]
        status   = loan[8]
        pd_est   = loan[13]

        orig    = date.fromisoformat(orig_str)
        mat     = date.fromisoformat(mat_str)

        # Monthly payments up to today or maturity
        current = orig + timedelta(days=30)
        while current <= min(mat, today):
            monthly_amount = round(amount / max(((mat - orig).days // 30), 1), 2)
            late_prob = pd_est * 8          # higher PD → more late payments
            if status == "defaulted" and current > today - timedelta(days=365):
                paid_date = None
                dpd = rng.randint(90, 365)
                pay_status = "missed"
            elif rng.random() < min(late_prob, 0.4):
                delay = rng.randint(1, 90)
                paid_date = (current + timedelta(days=delay)).isoformat()
                dpd = delay
                pay_status = "late"
            else:
                paid_date = (current + timedelta(days=rng.randint(0, 3))).isoformat()
                dpd = 0
                pay_status = "on_time"

            rows.append((
                pay_id, lid, current.isoformat(), paid_date,
                monthly_amount, dpd, pay_status,
            ))
            pay_id += 1
            current += timedelta(days=30)
            if len(rows) > 120_000:   # safety cap
                return rows
    return rows


DDL = """
CREATE TABLE IF NOT EXISTS companies (
    company_id        INTEGER PRIMARY KEY,
    name              TEXT NOT NULL,
    country           TEXT NOT NULL,
    sector            TEXT NOT NULL,
    founded_year      INTEGER,
    employees         INTEGER,
    revenue           REAL,
    ebitda            REAL,
    ebitda_margin     REAL,
    total_assets      REAL,
    total_liabilities REAL,
    equity            REAL,
    working_capital   REAL,
    altman_z_score    REAL,
    credit_rating     TEXT,
    pd_estimate       REAL,
    default_flag      INTEGER,
    client_segment    TEXT,
    relationship_manager TEXT,
    onboarding_date   TEXT
);

CREATE TABLE IF NOT EXISTS loans (
    loan_id              INTEGER PRIMARY KEY,
    company_id           INTEGER NOT NULL REFERENCES companies(company_id),
    product_type         TEXT NOT NULL,
    amount               REAL NOT NULL,
    currency             TEXT DEFAULT 'EUR',
    origination_date     TEXT NOT NULL,
    maturity_date        TEXT NOT NULL,
    interest_rate        REAL,
    status               TEXT,
    collateral_type      TEXT,
    collateral_value     REAL,
    ead                  REAL,
    lgd                  REAL,
    pd_estimate          REAL,
    expected_loss        REAL,
    capital_consumption  REAL,
    interest_income      REAL,
    operating_cost       REAL,
    cost_of_risk         REAL,
    net_revenue          REAL,
    raroc                REAL
);

CREATE TABLE IF NOT EXISTS payments (
    payment_id     INTEGER PRIMARY KEY,
    loan_id        INTEGER NOT NULL REFERENCES loans(loan_id),
    due_date       TEXT NOT NULL,
    paid_date      TEXT,
    amount         REAL,
    days_past_due  INTEGER DEFAULT 0,
    payment_status TEXT
);

CREATE VIEW IF NOT EXISTS v_portfolio_summary AS
SELECT
    c.country,
    c.sector,
    c.client_segment,
    c.credit_rating,
    COUNT(DISTINCT c.company_id)          AS n_companies,
    COUNT(l.loan_id)                       AS n_loans,
    ROUND(SUM(l.amount) / 1e6, 2)         AS total_exposure_meur,
    ROUND(SUM(l.expected_loss) / 1e6, 4)  AS total_expected_loss_meur,
    ROUND(SUM(l.capital_consumption)/1e6, 4) AS total_capital_meur,
    ROUND(AVG(l.raroc) * 100, 2)          AS avg_raroc_pct,
    ROUND(AVG(c.pd_estimate) * 100, 4)    AS avg_pd_pct,
    ROUND(SUM(l.amount * c.default_flag) / NULLIF(SUM(l.amount),0) * 100, 2) AS npl_ratio_pct
FROM companies c
JOIN loans l ON l.company_id = c.company_id
GROUP BY c.country, c.sector, c.client_segment, c.credit_rating;

CREATE VIEW IF NOT EXISTS v_loan_performance AS
SELECT
    l.loan_id,
    c.name             AS company_name,
    c.country,
    c.sector,
    c.credit_rating,
    l.product_type,
    l.amount,
    l.interest_rate,
    l.status,
    l.collateral_type,
    l.ead,
    l.lgd,
    l.pd_estimate,
    l.expected_loss,
    l.capital_consumption,
    l.raroc,
    l.net_revenue,
    COUNT(p.payment_id)                            AS total_payments,
    SUM(CASE WHEN p.payment_status = 'late'   THEN 1 ELSE 0 END) AS late_payments,
    SUM(CASE WHEN p.payment_status = 'missed' THEN 1 ELSE 0 END) AS missed_payments,
    MAX(p.days_past_due)                           AS max_days_past_due
FROM loans l
JOIN companies c ON c.company_id = l.company_id
LEFT JOIN payments p ON p.loan_id = l.loan_id
GROUP BY l.loan_id;

CREATE VIEW IF NOT EXISTS v_risk_by_manager AS
SELECT
    c.relationship_manager,
    COUNT(DISTINCT c.company_id)             AS n_clients,
    COUNT(l.loan_id)                          AS n_loans,
    ROUND(SUM(l.amount)/1e6, 2)              AS exposure_meur,
    ROUND(AVG(c.pd_estimate)*100, 3)         AS avg_pd_pct,
    ROUND(AVG(l.raroc)*100, 2)               AS avg_raroc_pct,
    ROUND(SUM(l.expected_loss)/1e6, 4)       AS total_el_meur,
    ROUND(SUM(l.capital_consumption)/1e6, 4) AS total_capital_meur,
    SUM(c.default_flag)                       AS n_defaulted_clients
FROM companies c
JOIN loans l ON l.company_id = c.company_id
GROUP BY c.relationship_manager;
"""


def seed(db_path: Path = DB_PATH):
    rng = random.Random(SEED)
    import numpy as np                     # used only for lognormal draws
    # Monkey-patch rng to support lognormvariate via numpy for speed
    np_rng = np.random.default_rng(SEED)

    class _Rng:
        def __getattr__(self, name):
            return getattr(rng, name)
        def lognormvariate(self, mu, sigma):
            return float(np_rng.lognormal(mu, sigma))
        def gauss(self, mu, sigma):
            return float(np_rng.normal(mu, sigma))

    r = _Rng()

    print(f"Seeding {db_path} …")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    # Drop and recreate
    cur.executescript("""
        DROP VIEW  IF EXISTS v_risk_by_manager;
        DROP VIEW  IF EXISTS v_loan_performance;
        DROP VIEW  IF EXISTS v_portfolio_summary;
        DROP TABLE IF EXISTS payments;
        DROP TABLE IF EXISTS loans;
        DROP TABLE IF EXISTS companies;
    """)
    cur.executescript(DDL)

    companies = build_companies(r, 2000)
    cur.executemany(
        "INSERT INTO companies VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        companies,
    )
    print(f"  {len(companies)} companies inserted")

    loans = build_loans(r, companies)
    cur.executemany(
        "INSERT INTO loans VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        loans,
    )
    print(f"  {len(loans)} loans inserted")

    payments = build_payments(r, loans)
    cur.executemany(
        "INSERT INTO payments VALUES (?,?,?,?,?,?,?)",
        payments,
    )
    print(f"  {len(payments)} payments inserted")

    con.commit()
    con.close()
    print(f"Done. {DISCLAIMER}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DB_PATH))
    args = ap.parse_args()
    seed(Path(args.db))
