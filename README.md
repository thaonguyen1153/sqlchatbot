## Project Folder structure

text_to_sql_chatbot/
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
