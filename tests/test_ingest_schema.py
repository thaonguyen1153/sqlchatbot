# app.py - FastAPI Text-to-SQL RAG API (Fixed)
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pathlib import Path
import sqlite3
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
from ingest_schema import EMBED_MODEL
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_core.prompts import ChatPromptTemplate

app = FastAPI(title="Text-to-SQL API")


# Global RAG components
# Project root is parent of backend/
PROJECT_ROOT = Path(__file__).parent.parent
CHROMA_DIR = PROJECT_ROOT / "chroma_db"

embeddings = OllamaEmbeddings(model=EMBED_MODEL)
vectorstore = Chroma(
    persist_directory=str(CHROMA_DIR),
    embedding_function=embeddings,
    collection_name="university_schema"
)
llm = ChatOllama(model="llama3.2:latest", temperature=0)  # Or your Ollama LLM


prompt = ChatPromptTemplate.from_template("""
You are a SQLite expert. Based on the schema context, generate a SINGLE valid SQL SELECT query.

CONTEXT: {context}
QUESTION: {question}

Return ONLY the SQL query, no explanations:
```sql
{generated_query}
```""")


@app.get("/health")
def health_check():
    return {"status": "OK", "tables": vectorstore._collection.count()}


class QueryRequest(BaseModel):
    question: str
    show_sql: bool = True


@app.post("/query")
async def text_to_sql(req: QueryRequest):
    # 1. Retrieve relevant schema
    docs = vectorstore.similarity_search(req.question, k=5)
    context = "\n".join([doc.page_content for doc in docs])
    
    # 2. Generate SQL
    chain = prompt | llm
    sql_result = chain.invoke({"context": context, "question": req.question})
    sql = sql_result.content.strip("```sql\n").strip("```").strip()
    
    # 3. Validate & execute safely
    conn = sqlite3.connect("data/bip.db")
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()
    
    try:
        cur.execute(sql)
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        results = [dict(zip(columns, row)) for row in rows]
        
        conn.close()
        return {
            "sql": sql if req.show_sql else None,
            "columns": columns,
            "rows": results[:50],  # Limit 50 rows
            "total_rows": len(results)
        }
    except sqlite3.Error as e:
        conn.close()
        raise HTTPException(status_code=400, detail=f"SQL Error: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
