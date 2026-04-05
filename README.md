# Text-to-SQL RAG Chatbot

**CST2213 Business Intelligence Programming - Phase 2 (Mar 2026)**  
Text-to-SQL system converts natural language queries to safe SELECTs on database using RAG (Chroma + OllamaEmbeddings), FastAPI backend, Streamlit UI.

[![API Docs](outputs/api_openapi.png)](http://localhost:8000/docs) [![Tests](outputs/test_report.html)](outputs/test_report.html)

## Current Status
- **Phase 1**: Project proposal, Data collection, data preparation.
- **Phase 2**: System design (ERD/UML in report), backend/frontend impl, features (RAG/SQL safe exec/charts), tests (pytest).
- **Deliverables**: API docs (OpenAPI JSON), feature report, testing report ready (outputs/).

## Folder Structure
```
sqlchatbot/
├── README.md                    # Project overview, setup, run instructions
├── requirements.txt             # Dependencies (langchain-ollama, fastapi, streamlit...)
├── docker-compose.yml          # Multi-DB + services stack
├── .env.example                # Ollama model, DB paths, API keys
│
├── backend/                    # FastAPI API + core services
│   ├── main.py                 # FastAPI app, /query endpoint
│   ├── services/
│   │   ├── sql_chain.py        # LangChain RAG chain (Chroma→Ollama)
│   │   ├── schema_introspector.py # SQLAlchemy reflection
│   │   ├── sql_validator.py    # sqlglot safety checks
│   │   └── result_formatter.py # Pandas→JSON/charts
│   ├── models/                 # Pydantic schemas (QueryRequest)
│   ├── database.py             # Multi-DB connection pool
│   └── utils.py                # Helpers (allowed_tables, logging)
│
├── frontend/                   # Streamlit UI
│   └── app.py                  # Chat interface, Plotly viz
│
├── data/                       # Multi-DB test sets
│   ├── superstore.db           # Global Superstore SQLite
│   ├── northwind.db            # Northwind SQLite
│   ├── create_test_dbs.py      # DDL population script
│   └── eval_queries.csv        # 50+ NL→SQL test cases
│
├── chroma_db/                  # Persisted vector store (gitignored)
├── tests/                      # pytest suite
│   ├── test_sql_chain.py
│   └── test_end_to_end.py
├── docs/                       # Phase 2 deliverables
│   ├── api_docs.html
│   └── diagrams/               # ERD, layers, sequence
└── deployment/                 # Dockerfiles, scripts
    ├── Dockerfile.backend
    └── Dockerfile.frontend
```

## Quick Start

### 1. Setup
```bash
mkdir -p data chromadb logs outputs db_scripts
ollama serve && ollama pull llama3.2:latest  # Embeddings/LLM
python database_setup.py  # Create bip.db
python ingest_schema-2.py # Build Chroma
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
# Gen PDF: See generate_report.ipynb in outputs/
```
## Features

- RAG Pipeline: Schema chunks → Ollama (llama3.2) → SQL → safe exec (validator).
- Endpoints: 5 total (health/tables/schema/search/query).
- UI: Chat, SQL view, auto-charts (bar/pie).
- Tests: Temp DB mocks, table/data asserts (3 students/4 enrolls).

## Endpoints Table

| Endpoint         | Method | Description             | Params              |
|------------------|--------|-------------------------|---------------------|
| /health          | GET    | Status + chunks         | None                |
| /tables          | GET    | List tables             | None                |
| /schema/{table}  | GET    | Schema/rowcount         | table: str          |
| /search          | GET    | Debug RAG               | query, k=8          |
| /query           | POST   | NLQ → SQL → results     | question, showsql   |

## Next step: Deployment/Phase 3

Dockerize, ML eval (NLQ accuracy), dashboard metrics.
Author: Thao Nguyen | CST2213 26W | Mar 2026