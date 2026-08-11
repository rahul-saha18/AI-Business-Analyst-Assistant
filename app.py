"""
AI Business Analyst Assistant — Streamlit App

Run with: streamlit run app.py

Requires:
- olist.db in the same folder (or update DB_PATH below)
- GEMINI_API_KEY set as an environment variable before launching, e.g.:
    export GEMINI_API_KEY="your-key-here"
    streamlit run app.py
"""

import streamlit as st
import sqlite3
import pandas as pd
import os
from google import genai

# ── Page setup ────────────────────────────────────────────────────────────
st.set_page_config(page_title="AI Business Analyst Assistant", layout="wide")
st.title("📊 AI Business Analyst Assistant")
st.caption("Ask a business question in plain English. Powered by SQLite + Gemini.")

DB_PATH = "olist.db"

# ── Connect to DB and Gemini (cached so it doesn't reconnect every rerun) ──
@st.cache_resource
def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

@st.cache_resource
def get_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        st.error("GEMINI_API_KEY not found. Set it as an environment variable before launching this app.")
        st.stop()
    return genai.Client(api_key=api_key)

conn = get_connection()
client = get_client()

# ── Schema extraction (cached — schema doesn't change during a session) ───
@st.cache_data
def get_schema_text(_conn):
    tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", _conn)['name'].tolist()
    schema_parts = []
    for table in tables:
        cols = pd.read_sql(f"PRAGMA table_info({table})", _conn)
        col_list = ", ".join(f"{row['name']} ({row['type']})" for _, row in cols.iterrows())
        schema_parts.append(f"Table: {table}\nColumns: {col_list}")
    return "\n\n".join(schema_parts)

schema_text = get_schema_text(conn)

SCHEMA_CONTEXT = f"""
{schema_text}

Key relationships:
- orders.customer_id = customers.customer_id
- order_items.order_id = orders.order_id
- order_items.product_id = products.product_id
- order_items.seller_id = sellers.seller_id
- order_reviews.order_id = orders.order_id
- order_payments.order_id = orders.order_id
- products.product_category_name = category_translation.product_category_name (use category_translation.product_category_name_english for readable category names)

Important business rules:
- For revenue questions, only count orders where order_status = 'delivered'
- "Revenue" means product revenue only: use SUM(order_items.price). Do NOT use order_payments.payment_value
  for revenue calculations — that column includes freight/shipping charges and installment interest,
  which inflates the figure and is a different business metric (total amount paid, not product revenue).
  Only use order_payments when the question is specifically about payment methods or amounts paid.
- The dataset covers September 2016 to August 2018. September 2016 and December 2016 have very few
  orders (data collection artifact, not a real trend). August 2018 is a partial/incomplete month.
  Do not treat unusually low activity in these specific months as a genuine business decline.
- When averaging review_score by category, only include categories with more than 100 reviews to
  avoid misleading results from small samples.
"""


# ── Core pipeline functions ────────────────────────────────────────────────
def build_sql_prompt(question):
    return f'''You are a SQL expert working with a SQLite database for an e-commerce company.

Database schema:
{SCHEMA_CONTEXT}

Write a SQLite query to answer this business question:
"{question}"

Rules:
- Return ONLY the SQL query, no explanation, no markdown code fences, no commentary.
- Use only SELECT statements. Never use INSERT, UPDATE, DELETE, DROP, or ALTER.
- Use table aliases for readability.
'''


def clean_sql(raw_text):
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.lower().startswith("sql"):
            text = text[3:]
    return text.strip().rstrip(";")


def is_safe_select(sql):
    forbidden = ['insert', 'update', 'delete', 'drop', 'alter', 'create', 'truncate', 'replace']
    sql_lower = sql.lower()
    if not sql_lower.strip().startswith('select'):
        return False
    if any(word in sql_lower for word in forbidden):
        return False
    return True


def question_to_sql(question, model="gemini-flash-latest"):
    prompt = build_sql_prompt(question)
    response = client.models.generate_content(model=model, contents=prompt)
    return clean_sql(response.text)


def build_summary_prompt(question, sql, result_df):
    preview = result_df.head(20).to_string(index=False)
    row_count = len(result_df)
    return f'''You are a business analyst presenting findings to a non-technical stakeholder.

Business question asked: "{question}"

SQL query used:
{sql}

Query result ({row_count} row(s) total, showing up to 20):
{preview}

Write a short, clear summary (2-4 sentences) answering the original business question, referencing
specific numbers from the result. Do not mention SQL or databases in your answer — write as if you
personally analyzed the data. Do not invent any numbers not present in the result above.
'''


def summarize_result(question, sql, result_df, model="gemini-flash-latest"):
    prompt = build_summary_prompt(question, sql, result_df)
    response = client.models.generate_content(model=model, contents=prompt)
    return response.text.strip()


def ask_business_question(question):
    sql = question_to_sql(question)

    if not is_safe_select(sql):
        return {
            'sql': sql, 'result': None, 'summary': None,
            'error': 'Generated SQL failed the safety check (not a plain SELECT) — not executed.'
        }

    try:
        result_df = pd.read_sql(sql, conn)
    except Exception as e:
        return {'sql': sql, 'result': None, 'summary': None, 'error': f'SQL execution failed: {e}'}

    if result_df.empty:
        summary = "The query ran successfully but returned no rows for this question."
    else:
        summary = summarize_result(question, sql, result_df)

    return {'sql': sql, 'result': result_df, 'summary': summary, 'error': None}


# ── UI ──────────────────────────────────────────────────────────────────
st.markdown("#### Example questions to try:")
st.markdown("""
- What are the top 5 product categories by revenue?
- Which state do most customers come from?
- What payment method do most customers use?
- Which product category has the lowest average review score?
""")

question = st.text_input("Ask a business question:", placeholder="e.g. What were the top 5 categories by revenue?")

if st.button("Ask", type="primary") and question:
    with st.spinner("Generating SQL and analyzing..."):
        result = ask_business_question(question)

    if result['error']:
        st.error(result['error'])
        st.code(result['sql'], language='sql')
    else:
        st.markdown("### 💡 Answer")
        st.write(result['summary'])

        with st.expander("🔍 Show generated SQL"):
            st.code(result['sql'], language='sql')

        st.markdown("### 📋 Raw Result")
        st.dataframe(result['result'])

        # Auto-chart: if result has a categorical column + one numeric column, plot it
        df = result['result']
        numeric_cols = df.select_dtypes(include='number').columns.tolist()
        non_numeric_cols = df.select_dtypes(exclude='number').columns.tolist()

        if len(numeric_cols) >= 1 and len(non_numeric_cols) >= 1 and len(df) <= 30:
            st.markdown("### 📈 Chart")
            chart_df = df.set_index(non_numeric_cols[0])[numeric_cols[0]]
            st.bar_chart(chart_df)

st.markdown("---")
st.caption("Built with SQLite, Google Gemini, and Streamlit — text-to-SQL business analyst assistant.")
