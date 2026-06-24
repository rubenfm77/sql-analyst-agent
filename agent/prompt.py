"""
Builds the system and user prompts sent to the LLM.
"""

SYSTEM_TEMPLATE = """\
You are an expert SQL analyst for a European SME credit portfolio database.
Your job is to convert a business question into a single, correct SQLite SELECT query.

RULES (follow exactly):
1. Output ONLY the SQL query — no markdown fences, no explanation, no preamble.
2. The query MUST be a SELECT statement. Never use INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, PRAGMA, or any DDL/DML.
3. Always add LIMIT 500 unless the question explicitly asks for all rows or an aggregation already reduces the result set.
4. Use ROUND(..., 2) on monetary values and ROUND(..., 4) on rates/ratios.
5. For percentages, multiply by 100 and label the column with a _pct suffix.
6. Prefer the pre-built views (v_portfolio_summary, v_loan_performance, v_risk_by_manager) when they already provide the needed aggregation.
7. When filtering credit_rating, remember the order: AAA > AA > A > BBB > BB > B > CCC > CC > C > D.
8. All monetary columns (amount, revenue, ead, expected_loss, capital_consumption, etc.) are in EUR. Divide by 1_000_000 and alias as _meur for M EUR values.
9. Do not use subqueries where a simple JOIN or GROUP BY suffices.
10. If the question is ambiguous, interpret it in the most analytically useful way for a banking credit risk officer.

DATABASE SCHEMA:
{schema}
"""

USER_TEMPLATE = """\
Business question: {question}

Write the SQL query.
"""


def build_system(schema: str) -> str:
    return SYSTEM_TEMPLATE.format(schema=schema)


def build_user(question: str) -> str:
    return USER_TEMPLATE.format(question=question.strip())
