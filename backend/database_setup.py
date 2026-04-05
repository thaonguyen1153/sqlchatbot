# database_setup.py
# Initializes SQLite database for BIP project by running DDL scripts.
# Stores database in data/ directory and scripts in db/scripts/.

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
DB_DIR = PROJECT_ROOT / "data"
SCRIPTS_DIR = PROJECT_ROOT / "db" / "scripts"
DEFAULT_DB_NAME = "bip"
SCRIPT_EXT = ".sql"


def ensureDirs() -> None:
    """Create required directories."""
    DB_DIR.mkdir(exist_ok=True)
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)


def getDbPath(dbName: str = DEFAULT_DB_NAME) -> Path:
    """Build SQLite database path from database name."""
    return DB_DIR / f"{dbName}.db"


def runDdlScripts(
    dbName: str = DEFAULT_DB_NAME,
    scriptsDir: Path = SCRIPTS_DIR,
    overwrite: bool = False,
) -> None:
    """Run all DDL scripts against one SQLite database."""
    dbPath = getDbPath(dbName)

    if dbPath.exists() and not overwrite:
        print(f"DB exists, skipping: {dbPath}")
        print("Use overwrite=True to reset.")
        return

    if overwrite and dbPath.exists():
        dbPath.unlink()

    scriptFiles = sorted(scriptsDir.glob(f"*{SCRIPT_EXT}"))
    if not scriptFiles:
        print("No .sql files in", scriptsDir)
        return

    conn = sqlite3.connect(dbPath)
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        for scriptFile in scriptFiles:
            print(f"Running {scriptFile.name} on {dbPath.name}...")
            with open(scriptFile, "r", encoding="utf-8") as file:
                sql = file.read()
            conn.executescript(sql)
            print(f"✓ {scriptFile.name}")

        conn.commit()
        print(f"Database ready: {dbPath}")
    except Exception as error:
        conn.rollback()
        print(f"✗ Setup failed: {error}")
    finally:
        conn.close()


def runSpecificScript(
    scriptName: str,
    dbName: str = DEFAULT_DB_NAME,
) -> None:
    """Run one specific script file against one SQLite database."""
    scriptPath = SCRIPTS_DIR / scriptName
    dbPath = getDbPath(dbName)

    if not scriptPath.exists():
        print(f"Script not found: {scriptPath}")
        return

    ensureDirs()
    conn = sqlite3.connect(dbPath)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    try:
        print(f"Running {scriptName} on {dbPath.name}...")
        with open(scriptPath, "r", encoding="utf-8") as file:
            sql = file.read()
        cur.executescript(sql)
        conn.commit()
        print(f"✓ {scriptName} executed on {dbPath}")
    except Exception as error:
        conn.rollback()
        print(f"✗ {scriptName}: {error}")
    finally:
        conn.close()


def listTables(dbName: str = DEFAULT_DB_NAME) -> list[str]:
    """List all tables in one SQLite database."""
    dbPath = getDbPath(dbName)

    if not dbPath.exists():
        print(f"⚠️ No DB found: {dbPath}")
        return []

    try:
        conn = sqlite3.connect(dbPath)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """
        )
        tables = [row[0] for row in cur.fetchall()]

        if tables:
            print(f"Tables in {dbPath}: {tables}")
            return tables

        print("No tables found. Run setup first.")
        return []
    except sqlite3.Error as error:
        print(f"DB error: {error}")
        return []
    finally:
        conn.close()


def showSampleData(dbName: str = DEFAULT_DB_NAME) -> None:
    """Show sample data from each table."""
    dbPath = getDbPath(dbName)
    tables = listTables(dbName)

    if not tables:
        return

    conn = sqlite3.connect(dbPath)
    cur = conn.cursor()

    try:
        for table in tables:
            cur.execute(f"SELECT * FROM {table} LIMIT 2;")
            rows = cur.fetchall()
            print(f"\n{table} (first 2 rows):")
            for row in rows:
                print(f" {row}")
    finally:
        conn.close()


def main() -> None:
    ensureDirs()

    # Example: build separate databases
    runSpecificScript("01_university_schema.sql", dbName="university")
    runSpecificScript("02_retail_schema.sql", dbName="retail")


if __name__ == "__main__":
    main()
