import sqlite3
from pathlib import Path

import pytest
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
import database_setup as dbSetup

UNIVERSITY_SCRIPT = "01_university_schema.sql"
RETAIL_SCRIPT = "02_retail_schema.sql"

EXPECTED_TABLES = {
    UNIVERSITY_SCRIPT: {
        "Students": {
            "columns": 5,
            "primaryKey": ["StudentID"],
            "foreignKeys": [],
        },
        "Courses": {
            "columns": 3,
            "primaryKey": ["CourseID"],
            "foreignKeys": [],
        },
        "Enrollments": {
            "columns": 4,
            "primaryKey": ["EnrollmentID"],
            "foreignKeys": ["StudentID", "CourseID"],
        },
    },
    RETAIL_SCRIPT: {
        "Customer": {
            "columns": 4,
            "primaryKey": ["CustomerID"],
            "foreignKeys": [],
        },
        "Product": {
            "columns": 4,
            "primaryKey": ["ProductID"],
            "foreignKeys": [],
        },
        "Orders": {
            "columns": 4,
            "primaryKey": ["OrderID"],
            "foreignKeys": ["CustomerID"],
        },
        "OrderDetails": {
            "columns": 4,
            "primaryKey": ["OrderDetailID"],
            "foreignKeys": ["OrderID", "ProductID"],
        },
    },
}


@pytest.fixture
def sandboxPaths(tmp_path, monkeypatch):
    projectRoot = tmp_path
    dataDir = projectRoot / "data"
    scriptsDir = projectRoot / "db" / "scripts"

    monkeypatch.setattr(dbSetup, "PROJECT_ROOT", projectRoot)
    monkeypatch.setattr(dbSetup, "DB_DIR", dataDir)
    monkeypatch.setattr(dbSetup, "SCRIPTS_DIR", scriptsDir)

    return projectRoot, dataDir, scriptsDir


@pytest.fixture
def scriptFiles(sandboxPaths):
    _, _, scriptsDir = sandboxPaths
    scriptsDir.mkdir(parents=True, exist_ok=True)

    universitySql = """
    CREATE TABLE Students (
        StudentID INTEGER PRIMARY KEY,
        FirstName TEXT,
        LastName TEXT,
        Age INTEGER,
        Major TEXT
    );

    CREATE TABLE Courses (
        CourseID INTEGER PRIMARY KEY,
        CourseName TEXT,
        Credits INTEGER
    );

    CREATE TABLE Enrollments (
        EnrollmentID INTEGER PRIMARY KEY,
        StudentID INTEGER,
        CourseID INTEGER,
        Grade TEXT,
        FOREIGN KEY (StudentID) REFERENCES Students(StudentID),
        FOREIGN KEY (CourseID) REFERENCES Courses(CourseID)
    );
    """.strip()

    retailSql = """
    CREATE TABLE Customer (
        CustomerID INTEGER PRIMARY KEY,
        Name TEXT,
        Email TEXT,
        City TEXT
    );

    CREATE TABLE Product (
        ProductID INTEGER PRIMARY KEY,
        ProductName TEXT,
        Category TEXT,
        Price REAL
    );

    CREATE TABLE Orders (
        OrderID INTEGER PRIMARY KEY,
        OrderDate TEXT,
        CustomerID INTEGER,
        TotalAmount REAL,
        FOREIGN KEY (CustomerID) REFERENCES Customer(CustomerID)
    );

    CREATE TABLE OrderDetails (
        OrderDetailID INTEGER PRIMARY KEY,
        OrderID INTEGER,
        ProductID INTEGER,
        Quantity INTEGER,
        FOREIGN KEY (OrderID) REFERENCES Orders(OrderID),
        FOREIGN KEY (ProductID) REFERENCES Product(ProductID)
    );
    """.strip()

    (scriptsDir / UNIVERSITY_SCRIPT).write_text(universitySql, encoding="utf-8")
    (scriptsDir / RETAIL_SCRIPT).write_text(retailSql, encoding="utf-8")

    return scriptsDir


@pytest.fixture
def retailDb(scriptFiles, sandboxPaths):
    dbSetup.ensureDirs()
    dbSetup.runSpecificScript(RETAIL_SCRIPT, dbName="retail")
    return dbSetup.getDbPath("retail")


@pytest.fixture
def universityDb(scriptFiles, sandboxPaths):
    dbSetup.ensureDirs()
    dbSetup.runSpecificScript(UNIVERSITY_SCRIPT, dbName="university")
    return dbSetup.getDbPath("university")


@pytest.fixture
def bipDb(scriptFiles, sandboxPaths):
    dbSetup.ensureDirs()
    dbSetup.runDdlScripts(dbName="bip", overwrite=True)
    return dbSetup.getDbPath("bip")


def getTableInfo(dbPath: Path, tableName: str) -> list[tuple]:
    conn = sqlite3.connect(dbPath)
    try:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({tableName})")
        return cursor.fetchall()
    finally:
        conn.close()


def getForeignKeys(dbPath: Path, tableName: str) -> list[tuple]:
    conn = sqlite3.connect(dbPath)
    try:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA foreign_key_list({tableName})")
        return cursor.fetchall()
    finally:
        conn.close()


def getPrimaryKeys(dbPath: Path, tableName: str) -> list[str]:
    tableInfo = getTableInfo(dbPath, tableName)
    return [row[1] for row in tableInfo if row[5] > 0]


def getUserTables(dbPath: Path) -> set[str]:
    conn = sqlite3.connect(dbPath)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """
        )
        return {row[0] for row in cursor.fetchall()}
    finally:
        conn.close()


def test_ensure_dirs_creates_data_directory(sandboxPaths):
    _, dataDir, _ = sandboxPaths
    dbSetup.ensureDirs()
    assert dataDir.exists()


def test_ensure_dirs_creates_scripts_directory(sandboxPaths):
    _, _, scriptsDir = sandboxPaths
    dbSetup.ensureDirs()
    assert scriptsDir.exists()


@pytest.mark.parametrize(
    ("dbName", "scriptName"),
    [
        ("university", UNIVERSITY_SCRIPT),
        ("retail", RETAIL_SCRIPT),
    ],
)
def test_run_specific_script_creates_expected_tables(
    sandboxPaths,
    scriptFiles,
    dbName,
    scriptName,
):
    dbSetup.ensureDirs()
    dbSetup.runSpecificScript(scriptName, dbName=dbName)

    dbPath = dbSetup.getDbPath(dbName)
    existingTables = getUserTables(dbPath)
    expectedTables = set(EXPECTED_TABLES[scriptName].keys())

    assert expectedTables == existingTables


@pytest.mark.parametrize(
    ("dbName", "scriptName"),
    [
        ("university", UNIVERSITY_SCRIPT),
        ("retail", RETAIL_SCRIPT),
    ],
)
def test_list_tables_matches_created_tables(
    sandboxPaths,
    scriptFiles,
    dbName,
    scriptName,
):
    dbSetup.ensureDirs()
    dbSetup.runSpecificScript(scriptName, dbName=dbName)

    tables = set(dbSetup.listTables(dbName))
    expectedTables = set(EXPECTED_TABLES[scriptName].keys())

    assert tables == expectedTables


def test_run_ddl_scripts_creates_combined_bip_database(bipDb):
    existingTables = getUserTables(bipDb)
    expectedTables = {
        tableName
        for schema in EXPECTED_TABLES.values()
        for tableName in schema
    }

    assert expectedTables.issubset(existingTables)
    missingTables = expectedTables - existingTables
    assert not missingTables, f"Missing tables: {sorted(missingTables)}"


@pytest.mark.parametrize(
    ("tableName", "meta"),
    [
        (tableName, meta)
        for schema in EXPECTED_TABLES.values()
        for tableName, meta in schema.items()
    ],
)
def test_table_has_expected_column_count(bipDb, tableName, meta):
    columns = getTableInfo(bipDb, tableName)
    assert len(columns) == meta["columns"]


@pytest.mark.parametrize(
    ("tableName", "meta"),
    [
        (tableName, meta)
        for schema in EXPECTED_TABLES.values()
        for tableName, meta in schema.items()
    ],
)
def test_table_has_correct_primary_key(bipDb, tableName, meta):
    primaryKeys = getPrimaryKeys(bipDb, tableName)
    assert sorted(primaryKeys) == sorted(meta["primaryKey"])


@pytest.mark.parametrize(
    ("tableName", "meta"),
    [
        (tableName, meta)
        for schema in EXPECTED_TABLES.values()
        for tableName, meta in schema.items()
        if meta["foreignKeys"]
    ],
)
def test_table_has_correct_foreign_keys(bipDb, tableName, meta):
    foreignKeyRows = getForeignKeys(bipDb, tableName)
    foreignKeyColumns = [row[3] for row in foreignKeyRows]

    for foreignKey in meta["foreignKeys"]:
        assert foreignKey in foreignKeyColumns


def test_run_ddl_scripts_skips_existing_database(scriptFiles, sandboxPaths):
    dbSetup.ensureDirs()
    dbSetup.runDdlScripts(dbName="bip", overwrite=True)
    dbSetup.runDdlScripts(dbName="bip", overwrite=False)

    dbPath = dbSetup.getDbPath("bip")
    assert dbPath.exists()


def test_get_db_path_uses_database_name(sandboxPaths):
    expectedPath = dbSetup.DB_DIR / "retail.db"
    assert dbSetup.getDbPath("retail") == expectedPath


def test_list_tables_returns_empty_for_missing_database(sandboxPaths):
    tables = dbSetup.listTables("missing_db")
    assert tables == []