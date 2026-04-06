# Text-to-SQL RAG Chatbot
![BI chatbot](docs/chatbot.png)
**CST2213 Business Intelligence Programming - Final project (April 2026)**  
Text-to-SQL system converts natural language queries to safe SELECTs on database using RAG (Chroma + OllamaEmbeddings), FastAPI backend, Streamlit UI.

[API Docs](http://localhost:8000/docs) | [Tests](outputs/test_report.html)

## Current Status
- **Phase 1**: Project proposal, Data collection, data preparation.
- **Phase 2**: System design (ERD/UML in report), backend/frontend impl, features (RAG/SQL safe exec/charts), tests (pytest).
- **Deliverables**: API docs (OpenAPI JSON), feature report, testing report ready (outputs/).
- **Final state**: The app support multiple database schemas. After generated SQL, it is validated before execute and the application suggest suitable plot to visualize. 

## Folder Structure
```
sqlchatbot/
├── README.md                    # Project overview, setup, run instructions
├── requirements.txt             # Dependencies (langchain-ollama, fastapi, streamlit...)
│
├── backend/                    # FastAPI API + core services
│   ├── app.py                  # FastAPI app, /query endpoint
│   ├── database_setup.py       # Create SQLLite from sql script
│   ├── ingest_schema.py        # Vectorize schema
│   └── sql_validator.py        # Check for SQL sqfety
│
├── data/                       # Multi-DB test sets SQLite(gitignored)
│   ├── retail.db               
│   └── university.db            
│
├── chroma_db/                  # Persisted vector store (gitignored)
│
├── logs/                       # Intermediate log file
│   └── text2sql.log            
│
├── tests/                      # pytest suite
│   ├── test_database_setup.py
│   └── test_ingest_schema.py
│
├── docs/                       # Project documentation
│   ├── report.pdf
│   ├── presentation.pdf
│   └── diagrams/               # ERD, layers, sequence
│
├── outputs/                    # Generated test report
│   └── test_report.html
│
├── app_streamlit.py            # Streamlit application
└── _run_all_.bat               # Start LLM, backend and frontend servers
```

## Quick Start

### 1. Setup
```bash
mkdir -p data chromadb logs outputs chroma_db
ollama serve && ollama pull llama3.2:latest  # Embeddings/LLM
python database_setup.py  # Create SQLLites
python ingest_schema-2.py # Build Chroma from schemas
pip install -r requirements.txt  # fastapi uvicorn streamlit langchain-ollama chromadb pytest-html reportlab
```

### 2. Run Backend
```bash 
uvicorn app-4:app --reload --port 8000
```
- Docs: http://localhost:8000/docs
- Test: Postman or curl -X POST "http://localhost:8000/query" -d '{"question": "avg GPA by course"}'

### 3. Run UI
```bash
streamlit run app_streamlit.py --server.port 8501
```
### 4. Tests/Reports
```bash
pytest test_*.py --html=outputs/test_report.html --self-contained-html -v
```
## Features

- RAG Pipeline: Schema chunks → Ollama (llama3.2) → SQL → safe exec (validator).
- Endpoints: 5 total (health/tables/schema/search/query).
- UI: Chat, SQL view, auto-charts (bar/pie/line).
- Tests: datasets from Data Analytics subject Fall 2025.

## Endpoints Table

| Endpoint         | Method | Description             | Params              |
|------------------|--------|-------------------------|---------------------|
| /health          | GET    | Status + chunks         | None                |
| /databases          | GET    | List databases             | None                |
| /tables          | GET    | List tables             | None                |
| /schema/{table}  | GET    | Schema of specific table         | table: str, db_name: str (retail is default)         |
| /search          | GET    | Debug RAG               | query, db_name, k=8          |
| /query           | POST   | NLQ → SQL → results     | question, showsql   |

## Evaluate:

The application evaluate base on these criterias:

- The app creates the correct SQL query for each question.
- The SQL runs successfully without errors.
- The returned data is correct and matches the database.
- The final answer is consistent with the SQL result.
- The response is clear, relevant, and complete for the user’s question.

Please refer to [the report](docs/sql-evaluation-table.html) for set of questions used and result.

---
Author: Thao Nguyen | CST2213 26W | April 2026