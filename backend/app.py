from datetime import datetime
from pathlib import Path
import logging
import os
import sqlite3
import sys

import uvicorn
from fastapi import FastAPI, HTTPException
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama, OllamaEmbeddings
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent))
from ingest_schema import EMBED_MODEL
from sql_validator import validateSql

app = FastAPI(title="Text-to-SQL chatbot API")

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
DB_DIR = PROJECT_ROOT / "data"
CHROMA_ROOT_DIR = PROJECT_ROOT / "chroma_db"
LOG_FILE = PROJECT_ROOT / "logs" / "text2sql.log"
DEFAULT_DB_NAME = "retail"

embeddings = OllamaEmbeddings(model=EMBED_MODEL)
llm = ChatOllama(model="llama3.2:latest", temperature=0)

prompt = ChatPromptTemplate.from_template(
    """
You are a SQLite expert. Based on the provided database schema context, generate a SINGLE valid SQL SELECT query that answers the question.

The process of generating SQL should be:
1. Analyze the question and identify which tables and columns are needed to answer it.
2. Check the ALLOWED TABLES and TABLE COLUMNS to confirm the necessary tables and columns exist.
3. Construct the SQL query using only the allowed tables and columns, ensuring proper JOINs valid with VALID JOINS.
4. If using alias, make sure to use the correct table name in the FROM clause and JOIN clauses. Also connect to the attributes with the correct table name or alias.
5. Double check the generated SQL to ensure it adheres to the schema and answers the question correctly.


Do not invent table names, aliases, or column names.
When a table already contains a total amount column, prefer that column over reconstructing totals from detail rows.
If the question asks for a customer name, use Customer.Name only.

If the question has answer that need to be grouped, make sure to use GROUP BY and aggregation functions correctly.

If the question cannot be answered from the provided schema, return:
SELECT 'SCHEMA_ERROR' AS error_message

ALLOWED TABLES:
{allowed_tables}

TABLE COLUMNS:
{table_columns}

VALID JOINS:
{valid_joins}

CONTEXT:
{context}

QUESTION:
{question}

Rules:
- Use only the chosen database schema.
- Do not invent table names.
- Do not invent column names.
- Do not use tables outside ALLOWED TABLES.
- Return only one SQLite SELECT statement.
- If the question cannot be answered from the provided schema, return:
  SELECT 'SCHEMA_ERROR' AS error_message
"""
)

os.makedirs(LOG_FILE.parent, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("Text2SQL")


class QueryRequest(BaseModel):
    question: str
    db_name: str = DEFAULT_DB_NAME
    show_sql: bool = True
    debug: bool = False



def getDbPath(dbName: str) -> Path:
    """Build SQLite database path from database name."""
    return DB_DIR / f"{dbName}.db"



def getChromaDir(dbName: str) -> Path:
    """Build Chroma directory path from database name."""
    return CHROMA_ROOT_DIR / dbName



def getCollectionName(dbName: str) -> str:
    """Build Chroma collection name from database name."""
    return f"{dbName}_schema"



def validateDbExists(dbName: str) -> Path:
    """Validate selected SQLite database exists."""
    dbPath = getDbPath(dbName)
    if not dbPath.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Database not found: {dbPath.name}",
        )
    return dbPath



def getVectorstore(dbName: str) -> Chroma:
    """Create vector store for one database."""
    chromaDir = getChromaDir(dbName)
    collectionName = getCollectionName(dbName)

    if not chromaDir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Chroma store not found for db '{dbName}'",
        )

    return Chroma(
        persist_directory=str(chromaDir),
        embedding_function=embeddings,
        collection_name=collectionName,
    )



def getTableNames(dbPath: Path) -> list[str]:
    """Return all user table names from one SQLite database."""
    conn = sqlite3.connect(dbPath)
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        )
        return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()



def getTableColumns(dbPath: Path) -> dict[str, set[str]]:
    """Return table-to-columns mapping from one SQLite database."""
    conn = sqlite3.connect(dbPath)
    cur = conn.cursor()
    tableColumns = {}

    try:
        tables = getTableNames(dbPath)
        for table in tables:
            cur.execute(f"PRAGMA table_info({table})")
            columns = {row[1] for row in cur.fetchall()}
            tableColumns[table] = columns
        return tableColumns
    finally:
        conn.close()



def formatTableColumns(tableColumns: dict[str, set[str]]) -> str:
    """Format table columns for prompt input."""
    lines = []
    for table, columns in sorted(tableColumns.items()):
        lines.append(f"{table}: {', '.join(sorted(columns))}")
    return "\n".join(lines)
def quoteIdentifier(name: str) -> str:
    escapedName = name.replace('"', '""')
    return f'"{escapedName}"'


def getTableJoins(dbPath: Path) -> dict[str, list[dict[str, object]]]:
    """Return valid joins from SQLite foreign keys for one database."""
    conn = sqlite3.connect(dbPath)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    tableJoins: dict[str, list[dict[str, object]]] = {}

    try:
        tables = getTableNames(dbPath)

        for table in tables:
            pragmaTable = quoteIdentifier(table)
            cur.execute(f"PRAGMA foreign_key_list({pragmaTable})")
            foreignKeyRows = cur.fetchall()

            joinGroups: dict[int, dict[str, object]] = {}

            for row in foreignKeyRows:
                foreignKeyId = row["id"]

                if foreignKeyId not in joinGroups:
                    joinGroups[foreignKeyId] = {
                        "fromTable": table,
                        "toTable": row["table"],
                        "fromColumns": [],
                        "toColumns": [],
                        "onUpdate": row["on_update"],
                        "onDelete": row["on_delete"],
                        "match": row["match"],
                    }

                joinGroups[foreignKeyId]["fromColumns"].append(row["from"])
                joinGroups[foreignKeyId]["toColumns"].append(row["to"])

            tableJoins[table] = list(joinGroups.values())

        return tableJoins
    finally:
        conn.close()
        
def getJoinClauses(dbPath: Path) -> list[str]:
    """Return SQL-ready join clauses derived from foreign keys."""
    tableJoins = getTableJoins(dbPath)
    joinClauses: list[str] = []

    for joins in tableJoins.values():
        for joinInfo in joins:
            fromTable = joinInfo["fromTable"]
            toTable = joinInfo["toTable"]
            fromColumns = joinInfo["fromColumns"]
            toColumns = joinInfo["toColumns"]

            joinParts = []
            for fromColumn, toColumn in zip(fromColumns, toColumns):
                joinParts.append(
                    f"{fromTable}.{fromColumn} = {toTable}.{toColumn}"
                )

            joinClause = (
                f"{fromTable} JOIN {toTable} ON " +
                " AND ".join(joinParts)
            )
            joinClauses.append(joinClause)

    return joinClauses

def runSelectQuery(dbPath: Path, sql: str) -> tuple[list[str], list[dict]]:
    """Execute generated SQL safely and return rows."""
    conn = sqlite3.connect(dbPath)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    try:
        cur.execute(sql)

        if cur.description is None:
            raise HTTPException(
                status_code=400,
                detail="Only SELECT queries are allowed.",
            )

        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        results = [dict(zip(columns, row)) for row in rows]
        return columns, results
    except sqlite3.Error as error:
        raise HTTPException(
            status_code=400,
            detail=f"SQL Error: {error}",
        ) from error
    finally:
        conn.close()


@app.get("/health")
def healthCheck(db_name: str = DEFAULT_DB_NAME):
    """Health check for one selected database."""
    dbPath = validateDbExists(db_name)
    vectorstore = getVectorstore(db_name)

    return {
        "status": "OK",
        "db_name": db_name,
        "db_path": str(dbPath),
        "collection": getCollectionName(db_name),
        "chunks": vectorstore._collection.count(),
    }


@app.get("/databases")
def getDatabases():
    """List available SQLite databases."""
    if not DB_DIR.exists():
        return {"databases": []}

    databases = sorted(path.stem for path in DB_DIR.glob("*.db"))
    return {"databases": databases}


@app.get("/tables")
def getTables(db_name: str = DEFAULT_DB_NAME):
    """List all user tables for one database."""
    dbPath = validateDbExists(db_name)
    tables = getTableNames(dbPath)
    return {"db_name": db_name, "tables": tables}


@app.get("/schema/{table}")
def getSchema(table: str, db_name: str = DEFAULT_DB_NAME):
    """Get schema for one table in one database."""
    dbPath = validateDbExists(db_name)
    conn = sqlite3.connect(dbPath)
    cur = conn.cursor()

    try:
        cur.execute(f"PRAGMA table_info({table})")
        schema = [
            {
                "name": column[1],
                "type": column[2],
                "notnull": column[3],
                "pk": column[5],
            }
            for column in cur.fetchall()
        ]

        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]

        return {
            "db_name": db_name,
            "table": table,
            "schema": schema,
            "row_count": count,
        }
    except sqlite3.Error as error:
        raise HTTPException(
            status_code=400,
            detail=f"Schema error: {error}",
        ) from error
    finally:
        conn.close()


@app.get("/search/{query}")
def debugSearch(query: str, db_name: str = DEFAULT_DB_NAME, k: int = 8):
    """Debug vector retrieval for one database."""
    validateDbExists(db_name)
    vectorstore = getVectorstore(db_name)
    docs = vectorstore.similarity_search(query, k=k)

    return {
        "db_name": db_name,
        "query": query,
        "matched_docs": [doc.page_content for doc in docs],
        "metadatas": [doc.metadata for doc in docs],
    }


@app.post("/query")
async def textToSql(req: QueryRequest):
    """Convert question to SQL for one selected database."""
    queryId = f"Q-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    dbPath = validateDbExists(req.db_name)
    vectorstore = getVectorstore(req.db_name)
    allowedTables = getTableNames(dbPath)
    tableColumns = getTableColumns(dbPath)
    validJoins = getJoinClauses(dbPath)

    logger.info(f"[{queryId}] START: '{req.question}' | db={req.db_name}")
    logger.info(f"[{queryId}] Allowed tables: {allowedTables}")
    logger.info(f"[{queryId}] Table columns: {tableColumns}")
    logger.info(f"[{queryId}] Valid joins: {validJoins}")
    logger.info(f"[{queryId}] 1. Similarity search (k=8)")

    docs = vectorstore.similarity_search(req.question, k=8)
    context = "\n".join(doc.page_content for doc in docs)

    logger.info(f"[{queryId}] Retrieved {len(docs)} docs")
    logger.info(f"[{queryId}] 2. LLM generating SQL...")
    logger.info(f"[{queryId}] Prompt used:\n{prompt}")
    
    chain = prompt | llm
    sqlResult = chain.invoke(
        {
            "allowed_tables": ", ".join(allowedTables),
            "table_columns": formatTableColumns(tableColumns),
            "valid_joins": "\n".join(validJoins),
            "context": context,
            "question": req.question,
        }
    )
    sql = sqlResult.content.strip()
    sql = sql.removeprefix("```sql").removeprefix("```").strip()
    sql = sql.removesuffix("```").strip()

    logger.info(f"[{queryId}] Generated SQL:\n{sql}")

    isValid, message = validateSql(
        sql=sql,
        allowedTables=set(allowedTables),
        tableColumns=tableColumns
    )
    if not isValid:
        logger.warning(f"[{queryId}] SQL validation failed: {message}")
        raise HTTPException(status_code=400, detail=message)

    if req.debug:
        return {
            "query_id": queryId,
            "db_name": req.db_name,
            "allowed_tables": allowedTables,
            "table_columns": {
                table: sorted(columns)
                for table, columns in tableColumns.items()
            },
            "matched_docs": [doc.page_content for doc in docs],
            "sql": sql if req.show_sql else None,
            "debug_only": True,
        }

    logger.info(f"[{queryId}] 3. Executing SQL on {dbPath.name}...")
    columns, results = runSelectQuery(dbPath, sql)
    logger.info(f"[{queryId}] SUCCESS: {len(results)} rows")

    return {
        "query_id": queryId,
        "db_name": req.db_name,
        "sql": sql if req.show_sql else None,
        "columns": columns,
        "rows": results[:50],
        "total_rows": len(results),
    }


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000)
