# app.py - FastAPI Text-to-SQL RAG API
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pathlib import Path
import logging
from datetime import datetime
import sqlite3
import sys
import os
sys.path.insert(0, str(Path(__file__).parent))
from ingest_schema import EMBED_MODEL
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_core.prompts import ChatPromptTemplate
app = FastAPI(title="Text-to-SQL chatbot API")

# Global RAG components
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
CHROMA_DIR = PROJECT_ROOT / "chroma_db"
DB_PATH = PROJECT_ROOT / "data" / "bip.db"
LOG_FILE = PROJECT_ROOT / "logs" / "text2sql.log"

embeddings = OllamaEmbeddings(model=EMBED_MODEL)
vectorstore = Chroma( 
    persist_directory=str(CHROMA_DIR),
    embedding_function=embeddings,
    collection_name="university_schema"
)
llm = ChatOllama(model="llama3.2:latest", temperature=0)

prompt = ChatPromptTemplate.from_template("""
You are a SQLite expert. Based on the schema context, generate a SINGLE valid SQL SELECT query.

CONTEXT: {context}
QUESTION: {question}

Return ONLY the SQL query, no explanations:
```sql
{{query}}
```""")

# Setup logger
os.makedirs(LOG_FILE.parent, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Text2SQL")

@app.get("/health")
def health_check():
    return {"status": "OK", "chunks": vectorstore._collection.count()}

@app.get("/tables")
def get_tables():
    """New: List all user tables."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [row[0] for row in cur.fetchall()]
    conn.close()
    return {"tables": tables}

@app.get("/schema/{table}")
def get_schema(table: str):
    """New: Get schema for specific table."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    schema = [{"name": c[1], "type": c[2], "notnull": c[3], "pk": c[5]} for c in cur.fetchall()]
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    count = cur.fetchone()[0]
    conn.close()
    return {"table": table, "schema": schema, "row_count": count}

@app.get("/search/{query}")
def debug_search(query: str, k: int = 8):
    """New: Debug vector retrieval—what schema gets matched."""
    docs = vectorstore.similarity_search(query, k=k)
    return {
        "query": query,
        "matched_docs": [doc.page_content for doc in docs],
        "metadatas": [doc.metadata for doc in docs]
    }
class QueryRequest(BaseModel):
    question: str
    show_sql: bool = True

@app.post("/query")
async def text_to_sql(req: QueryRequest):
    query_id = f"Q-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    logger.info(f"[{query_id}] START: '{req.question}'")
    
    # 1. Retrieve relevant schema
    logger.info(f"[{query_id}] 1. Similarity search (k=8)")
    
    docs = vectorstore.similarity_search(req.question, k=8)
    context = "\n".join([doc.page_content for doc in docs])
    
    logger.info(f"[{query_id}] Retrieved {len(docs)} docs ({len(context)} chars)")
    
    # 2. Generate SQL
    logger.info(f"[{query_id}] 2. LLM generating SQL...")
    
    chain = prompt | llm
    sql_result = chain.invoke({"context": context, "question": req.question})
    sql = sql_result.content.strip("```sql\n").strip("```").strip()
    
    logger.info(f"[{query_id}] Generated SQL:\n{sql}")
    logger.debug(f"[{query_id}] Full context ({len(context)} chars):\n{context[:2000]}")  # First 2000 chars
    # 3. Validate & execute safely
    logger.info(f"[{query_id}] 3. Executing SQL...")
    
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()
    
    try:
        cur.execute(sql)
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        results = [dict(zip(columns, row)) for row in rows]
        
        conn.close()
        logger.info(f"[{query_id}] SUCCESS: {len(results)} rows, cols: {columns}")
        
        return {
            "query_id": query_id,
            "sql": sql if req.show_sql else None,
            "columns": columns,
            "rows": results[:50],  # Limit 50 rows
            "total_rows": len(results)
        }
    except sqlite3.Error as e:
        conn.close()
        logger.error(f"[{query_id}] SQL ERROR: {e}")
        raise HTTPException(status_code=400, detail=f"SQL Error: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000) #, reload=True
