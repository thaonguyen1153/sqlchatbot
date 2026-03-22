# ingest_schema.py - Robust Schema Ingestion with Error Handling
import sqlite3
import os
from pathlib import Path
from streamlit import columns
from tqdm import tqdm
import hashlib
from typing import List, Tuple
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings

EMBED_MODEL = 'llama3.2:latest'  
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
DB_PATH = PROJECT_ROOT / "data" / "bip.db"
CHROMA_DIR = PROJECT_ROOT / "chroma_db"
COLLECTION_NAME = "university_schema"

def validateDbPath(dbPath: Path) -> bool:
    """Check DB exists and accessible."""
    if not dbPath.exists():
        print(f"❌ DB not found: {dbPath}")
        return False
    try:
        conn = sqlite3.connect(str(dbPath))
        conn.close()
        print(f"✅ DB ready: {dbPath}")
        return True
    except sqlite3.Error as e:
        print(f"❌ DB error: {e}")
        return False

def rowToText(table: str, cols: list, row: tuple) -> str:
    """Convert row to schema description text."""
    return f"Table: {table}. " + " | ".join(f"{c}: {v}" for c, v in zip(cols, row))

def indexTable(conn: sqlite3.Connection, table: str) -> Tuple[List[str], List[str], List[dict]]:
    """Index table with explicit schema + samples."""
    try:
        cur = conn.cursor()
        
        # 1. EXPLICIT SCHEMA DESCRIPTION (NEW)
        cur.execute(f"PRAGMA table_info({table})")
        columns_info = cur.fetchall()
        cols = [c[1] for c in columns_info]  # Exact column names
        schema_desc = f"EXACT SCHEMA Table: {table}. Columns: {', '.join(f'{c[1]} ({c[2]})' for c in columns_info)}. Primary keys: {', '.join(c[1] for c in columns_info if c[5])}"
        docs = [schema_desc]
        metas = [{"table": table, "type": "schema"}]
        ids = [f"{table}_schema"]
        
        print(f" 📋 {table}: {len(cols)} cols → {schema_desc[:80]}...")
        
        # 2. Sample rows (existing)
        cur.execute(f"SELECT {', '.join(cols)} FROM {table} LIMIT 5")
        rows = cur.fetchall()
        for i, row in enumerate(rows):
            txt = f"Table {table} sample: " + " | ".join(f"{c}: {v}" for c, v in zip(cols, row))
            doc_id = f"{table}_row_{i}_{hashlib.sha256(str(row).encode()).hexdigest()[:8]}"
            docs.append(txt)
            ids.append(doc_id)
            metas.append({"table": table, "type": "sample", "row": i})
        
        return docs, ids, metas
    except sqlite3.Error as e:
        print(f" ❌ {table}: {e}")
        return [], [], []

def main():
    """Full ingestion pipeline with validation."""
    print("🔍 Validating database...")
    if not validateDbPath(DB_PATH):
        return
    
    os.makedirs(CHROMA_DIR, exist_ok=True)
    print(f"📁 Chroma dir: {CHROMA_DIR}")
    
    try:
        embeddings = OllamaEmbeddings(model=EMBED_MODEL)
        vectorstore = Chroma(
            persist_directory=str(CHROMA_DIR),
            embedding_function=embeddings,
            collection_name=COLLECTION_NAME
        )
        print("✅ Embeddings & Chroma ready")
    except Exception as e:
        print(f"❌ Chroma init failed: {e}")
        return
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """)
        tables = [t[0] for t in cur.fetchall()]
        conn.close()
        
        if not tables:
            print("❌ No user tables found in bip.db")
            return
        
        print(f"📋 Found {len(tables)} tables: {tables}")
        
        all_docs, all_ids, all_metas = [], [], []
        for table in tqdm(tables, desc="Indexing"):
            docs, ids, metas = indexTable(sqlite3.connect(DB_PATH), table)
            all_docs.extend(docs)
            all_ids.extend(ids)
            all_metas.extend(metas)
        
        if all_docs:
            vectorstore.add_texts(texts=all_docs, metadatas=all_metas, ids=all_ids)
            print(f"✅ Indexed {len(all_docs)} chunks into '{COLLECTION_NAME}'")
            print(f"   View: GET http://localhost:8000/health")
        else:
            print("⚠️ No schema chunks generated")
            
    except Exception as e:
        print(f"❌ Pipeline failed: {e}")

if __name__ == "__main__":
    main()
