"""
AI Business Analyst Assistant — Streamlit App

Run with: streamlit run app.py
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

# ── Connect to DB ───
@st.cache_resource
def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

conn = get_connection()

# ── API Key & Model Configuration ───
env_key = os.environ.get("GEMINI_API_KEY", "")
if not env_key and os.path.exists(".env"):
    try:
        with open(".env") as f:
            for line in f:
                if line.startswith("GEMINI_API_KEY="):
                    val = line.strip().split("=", 1)[1].strip("\"'")
                    if val and not val.startswith("#"):
                        env_key = val
                        break
    except Exception:
        pass

input_key = st.sidebar.text_input(
    "🔑 Gemini API Key (Optional)",
    value=env_key,
    type="password",
    help="Enter key or leave blank to use built-in SQL Analyst engine."
)
api_key = input_key.strip() if input_key else env_key.strip()

selected_model = st.sidebar.selectbox(
    "🤖 Select Gemini Model",
    ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"],
    index=0
)

# ── Schema extraction ───
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
- "Revenue" means product revenue only: use SUM(order_items.price).
"""

# ── Local Rule-Based SQL & Summary Engine (Fallback) ──────────────────────
def local_sql_generator(question):
    q_lower = question.lower()
    if "revenue" in q_lower or "top" in q_lower or "category" in q_lower or "sales" in q_lower:
        if "lowest" in q_lower or "review" in q_lower or "rating" in q_lower or "score" in q_lower:
            return """SELECT category_translation.product_category_name_english AS category,
       ROUND(AVG(order_reviews.review_score), 2) AS avg_review_score,
       COUNT(order_reviews.review_score) AS review_count
FROM order_reviews
JOIN orders ON order_reviews.order_id = orders.order_id
JOIN order_items ON orders.order_id = order_items.order_id
JOIN products ON order_items.product_id = products.product_id
JOIN category_translation ON products.product_category_name = category_translation.product_category_name
WHERE orders.order_status = 'delivered'
GROUP BY category
HAVING review_count > 100
ORDER BY avg_review_score ASC
LIMIT 5"""
        else:
            return """SELECT category_translation.product_category_name_english AS category,
       ROUND(SUM(order_items.price), 2) AS total_revenue
FROM order_items
JOIN orders ON order_items.order_id = orders.order_id
JOIN products ON order_items.product_id = products.product_id
JOIN category_translation ON products.product_category_name = category_translation.product_category_name
WHERE orders.order_status = 'delivered'
GROUP BY category
ORDER BY total_revenue DESC
LIMIT 5"""

    elif "state" in q_lower or "customer" in q_lower or "location" in q_lower:
        return """SELECT customer_state AS state,
       COUNT(customer_id) AS total_customers
FROM customers
GROUP BY customer_state
ORDER BY total_customers DESC
LIMIT 10"""

    elif "payment" in q_lower or "method" in q_lower or "pay" in q_lower:
        return """SELECT payment_type AS payment_method,
       COUNT(order_id) AS total_orders,
       ROUND(SUM(payment_value), 2) AS total_value
FROM order_payments
GROUP BY payment_type
ORDER BY total_orders DESC"""

    else:
        return """SELECT category_translation.product_category_name_english AS category,
       COUNT(order_items.order_item_id) AS total_units_sold,
       ROUND(SUM(order_items.price), 2) AS total_revenue
FROM order_items
JOIN orders ON order_items.order_id = orders.order_id
JOIN products ON order_items.product_id = products.product_id
JOIN category_translation ON products.product_category_name = category_translation.product_category_name
WHERE orders.order_status = 'delivered'
GROUP BY category
ORDER BY total_revenue DESC
LIMIT 5"""


def local_summary_generator(question, sql, result_df):
    if result_df.empty:
        return "The query completed successfully but found no matching records in the database."

    col1 = result_df.columns[0]
    col2 = result_df.columns[1] if len(result_df.columns) > 1 else col1
    top_label = result_df.iloc[0][col1]
    top_val = result_df.iloc[0][col2]

    if isinstance(top_val, (int, float)):
        formatted_val = f"{top_val:,.2f}" if isinstance(top_val, float) else f"{top_val:,}"
    else:
        formatted_val = str(top_val)

    return f"Based on the analysis for '{question}', **{top_label}** leads the dataset with **{formatted_val}** ({col2}). A total of {len(result_df)} top entries were identified in this result breakdown."


# ── Core Gemini + Fallback Pipeline ────────────────────────────────────────
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


def ask_business_question(question, model="gemini-2.0-flash", key=""):
    sql = None
    summary = None
    used_engine = "Gemini AI"

    # Step 1: Attempt Gemini API if key is available
    if key:
        try:
            client = genai.Client(api_key=key)
            prompt = build_sql_prompt(question)
            res = client.models.generate_content(model=model, contents=prompt)
            raw_sql = clean_sql(res.text)
            if is_safe_select(raw_sql):
                sql = raw_sql
        except Exception:
            # If Gemini API fails (quota 429, invalid key, rate limit), fallback gracefully
            sql = None

    # Step 2: Fallback to local SQL Engine if Gemini failed or no key
    if not sql:
        sql = local_sql_generator(question)
        used_engine = "SQL Business Engine (Offline Fallback)"

    # Step 3: Run SQL Query on SQLite DB
    try:
        result_df = pd.read_sql(sql, conn)
    except Exception as e:
        return {'sql': sql, 'result': None, 'summary': None, 'error': f'SQL execution failed: {e}'}

    # Step 4: Generate Summary
    if key and used_engine == "Gemini AI":
        try:
            client = genai.Client(api_key=key)
            preview = result_df.head(20).to_string(index=False)
            sum_prompt = f"Question: '{question}'\nData:\n{preview}\nSummarize in 2-3 clear business sentences with numbers."
            res = client.models.generate_content(model=model, contents=sum_prompt)
            summary = res.text.strip()
        except Exception:
            summary = local_summary_generator(question, sql, result_df)
    else:
        summary = local_summary_generator(question, sql, result_df)

    return {'sql': sql, 'result': result_df, 'summary': summary, 'error': None, 'engine': used_engine}


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
    with st.spinner("Analyzing business question..."):
        result = ask_business_question(question, model=selected_model, key=api_key)

    if result['error']:
        st.error(result['error'])
    else:
        if "Fallback" in result.get('engine', ''):
            st.info("⚡ Powered by SQLite Business Engine.")

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
