# ingest_schema.py
# Robust schema ingestion with support for separate SQLite databases.

import hashlib
import os
import sqlite3
from pathlib import Path
from typing import List, Tuple

from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from tqdm import tqdm

EMBED_MODEL = "llama3.2:latest"
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
DB_DIR = PROJECT_ROOT / "data"
CHROMA_ROOT_DIR = PROJECT_ROOT / "chroma_db"
DEFAULT_DB_NAME = "bip"


def getDbPath(dbName: str = DEFAULT_DB_NAME) -> Path:
    """Build SQLite database path from database name."""
    return DB_DIR / f"{dbName}.db"


def getChromaDir(dbName: str = DEFAULT_DB_NAME) -> Path:
    """Build Chroma directory path from database name."""
    return CHROMA_ROOT_DIR / dbName


def getCollectionName(dbName: str = DEFAULT_DB_NAME) -> str:
    """Build Chroma collection name from database name."""
    return f"{dbName}_schema"


def validateDbPath(dbPath: Path) -> bool:
    """Check DB exists and is accessible."""
    if not dbPath.exists():
        print(f"❌ DB not found: {dbPath}")
        return False

    try:
        conn = sqlite3.connect(str(dbPath))
        conn.close()
        print(f"✅ DB ready: {dbPath}")
        return True
    except sqlite3.Error as error:
        print(f"❌ DB error: {error}")
        return False


def indexTable(
    conn: sqlite3.Connection,
    table: str,
) -> Tuple[List[str], List[str], List[dict]]:
    """Index one table with schema description and sample rows."""
    try:
        cur = conn.cursor()
        cur.execute(f"PRAGMA table_info({table})")
        columnsInfo = cur.fetchall()

        cols = [column[1] for column in columnsInfo]
        primaryKeys = [column[1] for column in columnsInfo if column[5]]

        schemaDesc = (
            f"EXACT SCHEMA Table: {table}. Columns: "
            f"{', '.join(f'{col[1]} ({col[2]})' for col in columnsInfo)}. "
            f"Primary keys: {', '.join(primaryKeys)}"
        )

        docs = [schemaDesc]
        metas = [{"table": table, "type": "schema"}]
        ids = [f"{table}_schema"]

        print(f" 📋 {table}: {len(cols)} cols → {schemaDesc[:80]}...")

        cur.execute(f"SELECT {', '.join(cols)} FROM {table} LIMIT 5")
        rows = cur.fetchall()

        for index, row in enumerate(rows):
            text = (
                f"Table {table} sample: "
                + " | ".join(f"{col}: {value}" for col, value in zip(cols, row))
            )
            rowHash = hashlib.sha256(str(row).encode()).hexdigest()[:8]
            docId = f"{table}_row_{index}_{rowHash}"

            docs.append(text)
            ids.append(docId)
            metas.append(
                {"table": table, "type": "sample", "row": index}
            )

        return docs, ids, metas
    except sqlite3.Error as error:
        print(f" ❌ {table}: {error}")
        return [], [], []


def main(dbName: str = DEFAULT_DB_NAME) -> None:
    """Full ingestion pipeline for one SQLite database."""
    dbPath = getDbPath(dbName)
    chromaDir = getChromaDir(dbName)
    collectionName = getCollectionName(dbName)

    print("🔍 Validating database...")
    if not validateDbPath(dbPath):
        return

    os.makedirs(chromaDir, exist_ok=True)
    print(f"📁 Chroma dir: {chromaDir}")

    try:
        embeddings = OllamaEmbeddings(model=EMBED_MODEL)
        vectorstore = Chroma(
            persist_directory=str(chromaDir),
            embedding_function=embeddings,
            collection_name=collectionName,
        )
        print("✅ Embeddings & Chroma ready")
    except Exception as error:
        print(f"❌ Chroma init failed: {error}")
        return

    try:
        conn = sqlite3.connect(dbPath)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """
        )
        tables = [table[0] for table in cur.fetchall()]

        if not tables:
            print(f"❌ No user tables found in {dbPath.name}")
            return

        print(f"📋 Found {len(tables)} tables: {tables}")

        allDocs = []
        allIds = []
        allMetas = []

        for table in tqdm(tables, desc="Indexing"):
            docs, ids, metas = indexTable(conn, table)
            allDocs.extend(docs)
            allIds.extend(ids)
            allMetas.extend(metas)

        if allDocs:
            vectorstore.add_texts(
                texts=allDocs,
                metadatas=allMetas,
                ids=allIds,
            )
            print(
                f"✅ Indexed {len(allDocs)} chunks into "
                f"'{collectionName}'"
            )
            print(" View: GET http://localhost:8000/health")
        else:
            print("⚠️ No schema chunks generated")
    except Exception as error:
        print(f"❌ Pipeline failed: {error}")
    finally:
        conn.close()


if __name__ == "__main__":
    main("university")
    main("retail")