# AI Business Analyst Assistant

A text-to-SQL business intelligence tool that lets anyone ask a plain-English question about e-commerce data and get back a grounded, data-backed answer — no SQL knowledge required.

**Stack:** SQLite, Google Gemini API, Streamlit, Python (Pandas)

---

## Business Problem

Analysts spend a large share of their time answering repetitive business questions — "what were sales last month," "which category is underperforming" — that require writing SQL, running it, and translating the result into plain language for a non-technical stakeholder. This project automates that loop end to end: a business user types a question, the system writes and validates the SQL, runs it against a real relational database, and returns a plain-English summary grounded in the actual result.

Unlike a fixed dashboard with pre-built charts and filters, this system isn't limited to a set list of questions. Any question about the underlying data — revenue, customers, products, sellers, payments, reviews — gets a fresh, generated query and answer, since the model has the full database schema available on every call.

## Dataset

Olist Brazilian E-Commerce dataset (Kaggle) — 8 relational tables covering ~100,000 orders: orders, order items, payments, reviews, products, sellers, customers, and category translations. Loaded into a single SQLite database to simulate a real company's operational database.

## How It Works

1. **Question → SQL.** The user's question, along with the full database schema and explicit business rules (e.g., only count `delivered` orders as revenue), is sent to Gemini, which generates a SQL query.
2. **Safety check.** Every generated query is validated before execution — only plain `SELECT` statements are allowed; anything else is rejected automatically. The system never lets an LLM touch the database beyond reading it.
3. **Execution.** The validated query runs against the SQLite database and returns real results.
4. **Result → Insight.** The result table is passed back to Gemini with instructions to summarize it in plain English, referencing the actual numbers rather than generating generic filler text.
5. **Interface.** A Streamlit app wraps the whole pipeline — question in, SQL shown transparently, result table, auto-generated chart, and a plain-English answer out.

## A Real Bug I Caught (and Why It Matters)

Early testing showed the model returning two different values for "total revenue" depending on how the question was phrased — one based on `order_items.price`, another based on `order_payments.payment_value`. Both are technically valid SQL, but `payment_value` includes freight charges and installment interest, inflating the figure by about R$2.2M. I traced the discrepancy back to the ambiguity in how "revenue" was defined in the prompt, then made the business rule explicit in the schema context so the model consistently uses product revenue rather than total amount paid. This is the kind of definitional ambiguity that comes up constantly in real analytics work, and catching it against manually-verified ground truth (rather than trusting output that merely "ran without error") was the actual point of building a verification step before wiring up the interface.

## Key Design Decisions

- **SELECT-only enforcement** — a hard safety rule, not a suggestion, since this system lets an LLM generate code that touches a real database.
- **Schema + business rules sent on every call** — the model has no memory between questions, so context must be self-contained each time.
- **Ground-truth verification** — before trusting the pipeline on new questions, I manually wrote and verified 5-6 queries myself, then checked the LLM's independently generated SQL against those known-correct answers.

## Known Limitations

- Complex multi-condition questions (e.g., comparing two time periods within a single query) occasionally need more specific phrasing to get a correct query on the first try.
- The system has no memory across questions within a session — each question is answered independently.
- The dataset has a data-collection artifact at its start and end (near-empty months), which the prompt explicitly instructs the model not to misinterpret as a real business trend.

## Development Note

Built with AI assistance throughout — Google's Gemini API powers the core text-to-SQL and summarization pipeline, and I used Claude to help scaffold the notebooks, debug prompt design, and think through edge cases like the revenue-definition bug above. I designed the verification methodology, tested the outputs against manually-computed ground truth, and can walk through every design decision and trade-off in the system.

## Project Structure

```
ai_analyst_project/
├── data/
│   └── olist.db
├── notebooks/
│   ├── 01_database_setup.ipynb
│   ├── 02_text_to_sql.ipynb
│   └── 03_summary_layer.ipynb
├── app.py
└── README.md
```

## Author

Rahul Saha .
