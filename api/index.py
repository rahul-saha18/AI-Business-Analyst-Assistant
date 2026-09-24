import os
import sqlite3
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from google import genai

app = FastAPI(title="AI Business Analyst API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Determine DB Path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "olist.db")
if not os.path.exists(DB_PATH):
    DB_PATH = "olist.db"

def get_db_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def get_schema_text():
    try:
        conn = get_db_connection()
        tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", conn)['name'].tolist()
        schema_parts = []
        for table in tables:
            cols = pd.read_sql(f"PRAGMA table_info({table})", conn)
            col_list = ", ".join(f"{row['name']} ({row['type']})" for _, row in cols.iterrows())
            schema_parts.append(f"Table: {table}\nColumns: {col_list}")
        conn.close()
        return "\n\n".join(schema_parts)
    except Exception as e:
        return f"Error extracting schema: {e}"

SCHEMA_CONTEXT = f"""
{get_schema_text()}

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

def local_sql_generator(question: str) -> str:
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

def local_summary_generator(question: str, sql: str, result_df: pd.DataFrame) -> str:
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

def build_sql_prompt(question: str) -> str:
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

def clean_sql(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.lower().startswith("sql"):
            text = text[3:]
    return text.strip().rstrip(";")

def is_safe_select(sql: str) -> bool:
    forbidden = ['insert', 'update', 'delete', 'drop', 'alter', 'create', 'truncate', 'replace']
    sql_lower = sql.lower()
    if not sql_lower.strip().startswith('select'):
        return False
    if any(word in sql_lower for word in forbidden):
        return False
    return True

class QueryRequest(BaseModel):
    question: str
    api_key: Optional[str] = None
    model: Optional[str] = "gemini-2.0-flash"

@app.get("/api/health")
def health():
    return {"status": "ok", "db_exists": os.path.exists(DB_PATH)}

@app.get("/api/schema")
def get_schema():
    return {
        "schema": SCHEMA_CONTEXT,
        "sample_questions": [
            "What are the top 5 product categories by revenue?",
            "Which state do most customers come from?",
            "What payment method do most customers use?",
            "Which product category has the lowest average review score?"
        ]
    }

@app.post("/api/query")
def execute_query(req: QueryRequest):
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    # Get API key from request, environment variable
    env_key = os.environ.get("GEMINI_API_KEY", "")
    if not env_key and os.path.exists(os.path.join(BASE_DIR, ".env")):
        try:
            with open(os.path.join(BASE_DIR, ".env")) as f:
                for line in f:
                    if line.startswith("GEMINI_API_KEY="):
                        val = line.strip().split("=", 1)[1].strip("\"'")
                        if val and not val.startswith("#"):
                            env_key = val
                            break
        except Exception:
            pass

    key = req.api_key.strip() if req.api_key else env_key.strip()
    model_name = req.model if req.model else "gemini-2.0-flash"

    sql = None
    summary = None
    used_engine = "Gemini AI"

    # Step 1: Attempt Gemini API if key is available
    if key:
        try:
            client = genai.Client(api_key=key)
            prompt = build_sql_prompt(question)
            res = client.models.generate_content(model=model_name, contents=prompt)
            raw_sql = clean_sql(res.text)
            if is_safe_select(raw_sql):
                sql = raw_sql
        except Exception:
            sql = None

    # Step 2: Fallback to local SQL Engine if Gemini failed or no key
    if not sql:
        sql = local_sql_generator(question)
        used_engine = "SQL Business Engine (Offline Fallback)"

    # Step 3: Run SQL Query on SQLite DB
    try:
        conn = get_db_connection()
        result_df = pd.read_sql(sql, conn)
        conn.close()
    except Exception as e:
        return {
            "sql": sql,
            "result": None,
            "columns": [],
            "summary": None,
            "error": f"SQL execution failed: {str(e)}",
            "engine": used_engine
        }

    # Step 4: Generate Summary
    if key and used_engine == "Gemini AI":
        try:
            client = genai.Client(api_key=key)
            preview = result_df.head(20).to_string(index=False)
            sum_prompt = f"Question: '{question}'\nData:\n{preview}\nSummarize in 2-3 clear business sentences with numbers."
            res = client.models.generate_content(model=model_name, contents=sum_prompt)
            summary = res.text.strip()
        except Exception:
            summary = local_summary_generator(question, sql, result_df)
    else:
        summary = local_summary_generator(question, sql, result_df)

    # Convert DataFrame to list of dicts safely handling NaN/Infinity
    records = result_df.where(pd.notnull(result_df), None).to_dict(orient="records")
    columns = list(result_df.columns)

    return {
        "sql": sql,
        "result": records,
        "columns": columns,
        "summary": summary,
        "error": None,
        "engine": used_engine
    }
