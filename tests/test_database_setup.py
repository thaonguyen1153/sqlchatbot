import sys
import sqlite3
import tempfile
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
from database_setup import ensure_dirs, run_ddl_scripts, list_tables, SCRIPTS_DIR

# ─── Schema under test ────────────────────────────────────────────────────────
# Maps each expected SQL script to the tables it should produce,
# plus the expected column count per table and its primary/foreign keys.

EXPECTED_SCHEMA = {
    "01_university_schema.sql": {
        "Students": {
            "columns": 5,  # StudentID, FirstName, LastName, Age, Major
            "primary_key": ["StudentID"],
            "foreign_keys": [],
        },
        "Courses": {
            "columns": 3,  # CourseID, CourseName, Credits
            "primary_key": ["CourseID"],
            "foreign_keys": [],
        },
        "Enrollments": {
            "columns": 4,  # EnrollmentID, StudentID, CourseID, Grade
            "primary_key": ["EnrollmentID"],
            "foreign_keys": ["StudentID", "CourseID"],
        },
    },
    "02_retail_schema.sql": {
        "Customer": {
            "columns": 4,  
            "primary_key": ["CustomerID"],
            "foreign_keys": [],
        },
        "Product": {
            "columns": 4,
            "primary_key": ["ProductID"],
            "foreign_keys": [],
        },
        "Orders": {
            "columns": 4,  # OrderID, OrderDate, CustomerID, TotalAmount
            "primary_key": ["OrderID"],
            "foreign_keys": ["CustomerID"],
        },
        "OrderDetails": {
            "columns": 4,
            "primary_key": ["OrderDetailID"],
            "foreign_keys": ["OrderID", "ProductID"],
        },
    },
}

# ─── Helpers ──────────────────────────────────────────────────────────────────

def getTableInfo(conn: sqlite3.Connection, tableName: str) -> list[dict]:
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({tableName})")
    return cursor.fetchall()


def getForeignKeys(conn: sqlite3.Connection, tableName: str) -> list[dict]:
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA foreign_key_list({tableName})")
    return cursor.fetchall()


def getPrimaryKeys(conn: sqlite3.Connection, tableName: str) -> list[str]:
    info = getTableInfo(conn, tableName)
    # table_info row: (cid, name, type, notnull, dflt_value, pk)
    return [row[1] for row in info if row[5] > 0]


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def tempDbPath():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test_bip.db"


@pytest.fixture
def populatedDb(tempDbPath, tmp_path):
    """DB loaded with all expected SQL scripts."""
    scriptsDir = tmp_path / "db" / "scripts"
    scriptsDir.mkdir(parents=True)

    for scriptName in EXPECTED_SCHEMA:
        realScript = Path("db/scripts") / scriptName
        if realScript.exists():
            (scriptsDir / scriptName).write_text(realScript.read_text())

    run_ddl_scripts(tempDbPath, scriptsDir, overwrite=True)
    yield tempDbPath, scriptsDir


# ─── Directory tests ──────────────────────────────────────────────────────────

def test_ensure_dirs_creates_data_folder():
    ensure_dirs()
    assert Path("data").exists()


def test_ensure_dirs_creates_scripts_folder():
    ensure_dirs()
    assert SCRIPTS_DIR.exists()


# ─── Script-count test ────────────────────────────────────────────────────────

def test_scripts_dir_has_expected_script_count(populatedDb):
    _, scriptsDir = populatedDb
    sqlFiles = list(scriptsDir.glob("*.sql"))
    assert len(sqlFiles) == len(EXPECTED_SCHEMA), (
        f"Expected {len(EXPECTED_SCHEMA)} scripts, found {len(sqlFiles)}: "
        f"{[f.name for f in sqlFiles]}"
    )


# ─── Per-script: table existence ──────────────────────────────────────────────

@pytest.mark.parametrize("scriptName,tables", [
    (script, list(schema.keys()))
    for script, schema in EXPECTED_SCHEMA.items()
])
def test_script_creates_expected_tables(populatedDb, scriptName, tables):
    dbPath, _ = populatedDb
    conn = sqlite3.connect(dbPath)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    existing = {row[0] for row in cursor.fetchall()}
    conn.close()

    for table in tables:
        assert table in existing, (
            f"Script '{scriptName}' should create table '{table}'"
        )


# ─── Per-table: column count ──────────────────────────────────────────────────

@pytest.mark.parametrize("tableName,meta", [
    (table, meta)
    for schema in EXPECTED_SCHEMA.values()
    for table, meta in schema.items()
])
def test_table_has_expected_column_count(populatedDb, tableName, meta):
    dbPath, _ = populatedDb
    conn = sqlite3.connect(dbPath)
    columns = getTableInfo(conn, tableName)
    conn.close()

    assert len(columns) == meta["columns"], (
        f"Table '{tableName}': expected {meta['columns']} columns, "
        f"got {len(columns)}"
    )


# ─── Per-table: primary key ───────────────────────────────────────────────────

@pytest.mark.parametrize("tableName,meta", [
    (table, meta)
    for schema in EXPECTED_SCHEMA.values()
    for table, meta in schema.items()
])
def test_table_has_correct_primary_key(populatedDb, tableName, meta):
    dbPath, _ = populatedDb
    conn = sqlite3.connect(dbPath)
    primaryKeys = getPrimaryKeys(conn, tableName)
    conn.close()

    assert sorted(primaryKeys) == sorted(meta["primary_key"]), (
        f"Table '{tableName}': expected PK {meta['primary_key']}, "
        f"got {primaryKeys}"
    )


# ─── Per-table: foreign key columns ──────────────────────────────────────────

@pytest.mark.parametrize("tableName,meta", [
    (table, meta)
    for schema in EXPECTED_SCHEMA.values()
    for table, meta in schema.items()
    if meta["foreign_keys"]
])
def test_table_has_correct_foreign_keys(populatedDb, tableName, meta):
    dbPath, _ = populatedDb
    conn = sqlite3.connect(dbPath)
    fkRows = getForeignKeys(conn, tableName)
    conn.close()

    # foreign_key_list row: (id, seq, table, from, to, ...)
    fkColumns = [row[3] for row in fkRows]
    for expectedFk in meta["foreign_keys"]:
        assert expectedFk in fkColumns, (
            f"Table '{tableName}': expected FK on '{expectedFk}', "
            f"got FK columns {fkColumns}"
        )


# ─── Idempotency ──────────────────────────────────────────────────────────────

def test_run_ddl_scripts_skips_existing_db(tempDbPath, tmp_path):
    """Calling run_ddl_scripts twice without overwrite must not raise."""
    scriptsDir = tmp_path / "scripts"
    scriptsDir.mkdir()
    (scriptsDir / "01_noop.sql").write_text(
        "CREATE TABLE IF NOT EXISTS Noop (id INTEGER PRIMARY KEY);"
    )
    run_ddl_scripts(tempDbPath, scriptsDir, overwrite=True)
    run_ddl_scripts(tempDbPath, scriptsDir, overwrite=False)  # must not crash


# ─── list_tables ─────────────────────────────────────────────────────────────

def test_list_tables_returns_list_of_strings(populatedDb):
    dbPath, _ = populatedDb
    tables = list_tables(dbPath)
    assert isinstance(tables, list)
    assert all(isinstance(t, str) for t in tables)


def test_list_tables_matches_created_tables(populatedDb):
    dbPath, _ = populatedDb
    tables = set(list_tables(dbPath))
    expected = {
        table
        for schema in EXPECTED_SCHEMA.values()
        for table in schema
    }
    assert expected.issubset(tables), (
        f"Missing from list_tables: {expected - tables}"
    )
