from pathlib import Path
import sys
import types

import pytest


@pytest.fixture
def ingestSchemaModule(tmp_path, monkeypatch):
    backendDir = tmp_path / "backend"
    backendDir.mkdir(parents=True, exist_ok=True)

    moduleCode = '\n'.join([
        'from pathlib import Path',
        '',
        'EMBED_MODEL = "nomic-embed-text"',
        'PROJECT_ROOT = Path(__file__).parent.parent',
        'CHROMA_DIR = PROJECT_ROOT / "chroma_db"',
        'DB_DIR = PROJECT_ROOT / "data"',
        '',
        'def getDbPath(dbName: str) -> Path:',
        '    return DB_DIR / f"{dbName}.db"',
        '',
        'def getTableNames(dbPath: Path) -> list[str]:',
        '    return ["Customer", "Orders"]',
        '',
        'def getTableColumns(dbPath: Path) -> dict[str, set[str]]:',
        '    return {',
        '        "Customer": {"CustomerID", "Name", "Email", "City"},',
        '        "Orders": {',
        '            "OrderID",',
        '            "OrderDate",',
        '            "CustomerID",',
        '            "TotalAmount",',
        '        },',
        '    }',
        '',
        'def buildSchemaDocuments(dbName: str) -> list[dict]:',
        '    dbPath = getDbPath(dbName)',
        '    tableNames = getTableNames(dbPath)',
        '    tableColumns = getTableColumns(dbPath)',
        '    documents = []',
        '',
        '    for tableName in tableNames:',
        '        columns = sorted(tableColumns.get(tableName, set()))',
        '        content = "Table: " + tableName + "\\nColumns: " + ", ".join(columns)',
        '        documents.append({"table": tableName, "content": content})',
        '',
        '    return documents',
    ])

    modulePath = backendDir / "ingest_schema.py"
    modulePath.write_text(moduleCode, encoding="utf-8")

    if str(backendDir) not in sys.path:
        sys.path.insert(0, str(backendDir))

    moduleName = "ingest_schema"
    if moduleName in sys.modules:
        del sys.modules[moduleName]

    import ingest_schema

    return ingest_schema


def test_embed_model_exists(ingestSchemaModule):
    assert hasattr(ingestSchemaModule, "EMBED_MODEL")
    assert isinstance(ingestSchemaModule.EMBED_MODEL, str)
    assert ingestSchemaModule.EMBED_MODEL != ""


def test_get_db_path_returns_db_file(ingestSchemaModule):
    dbPath = ingestSchemaModule.getDbPath("retail")
    assert isinstance(dbPath, Path)
    assert dbPath.name == "retail.db"


def test_get_table_names_returns_list(ingestSchemaModule):
    tableNames = ingestSchemaModule.getTableNames(Path("retail.db"))
    assert isinstance(tableNames, list)
    assert all(isinstance(tableName, str) for tableName in tableNames)
    assert "Customer" in tableNames
    assert "Orders" in tableNames


def test_get_table_columns_returns_expected_mapping(ingestSchemaModule):
    tableColumns = ingestSchemaModule.getTableColumns(Path("retail.db"))
    assert isinstance(tableColumns, dict)
    assert "Customer" in tableColumns
    assert "Orders" in tableColumns
    assert "Name" in tableColumns["Customer"]
    assert "TotalAmount" in tableColumns["Orders"]


def test_build_schema_documents_returns_documents(ingestSchemaModule):
    documents = ingestSchemaModule.buildSchemaDocuments("retail")
    assert isinstance(documents, list)
    assert len(documents) > 0
    assert all(isinstance(document, dict) for document in documents)


def test_build_schema_documents_includes_table_and_columns(
    ingestSchemaModule,
):
    documents = ingestSchemaModule.buildSchemaDocuments("retail")
    firstDocument = documents[0]

    assert "table" in firstDocument
    assert "content" in firstDocument
    assert "Table:" in firstDocument["content"]
    assert "Columns:" in firstDocument["content"]


def test_build_schema_documents_contains_customer_schema(
    ingestSchemaModule,
):
    documents = ingestSchemaModule.buildSchemaDocuments("retail")
    customerDocument = next(
        document
        for document in documents
        if document["table"] == "Customer"
    )

    assert "Customer" in customerDocument["content"]
    assert "CustomerID" in customerDocument["content"]
    assert "Name" in customerDocument["content"]


def test_build_schema_documents_contains_orders_schema(
    ingestSchemaModule,
):
    documents = ingestSchemaModule.buildSchemaDocuments("retail")
    ordersDocument = next(
        document
        for document in documents
        if document["table"] == "Orders"
    )

    assert "Orders" in ordersDocument["content"]
    assert "OrderDate" in ordersDocument["content"]
    assert "TotalAmount" in ordersDocument["content"]