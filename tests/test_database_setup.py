import sys
import pytest
from pathlib import Path
import sqlite3
import tempfile

# Fix path to backend
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
from database_setup import ensure_dirs, run_ddl_scripts

@pytest.fixture
def temp_db_path():
    """Temp DB for isolated testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_bip.db"
        yield db_path

def test_ensure_dirs_creates_folders(tmp_path):
    from database_setup import SCRIPTS_DIR
    ensure_dirs()
    assert Path("data").exists()
    assert SCRIPTS_DIR.exists()

def test_run_ddl_scripts_creates_db_and_tables(temp_db_path, tmp_path):
    """Test DDL with fixed syntax."""
    # Create valid test script
    scripts_dir = tmp_path / "db" / "scripts"
    scripts_dir.mkdir(parents=True)
    
    script_content = """
    CREATE TABLE IF NOT EXISTS test_customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL
    );
    
    CREATE TABLE IF NOT EXISTS test_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER,
        FOREIGN KEY(customer_id) REFERENCES test_customers(id)
    );
    """
    
    script_path = scripts_dir / "01_test_tables.sql"
    script_path.write_text(script_content)
    
    run_ddl_scripts(temp_db_path, scripts_dir)
    
    # Verify DB and tables
    assert temp_db_path.exists()
    conn = sqlite3.connect(temp_db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {row[0] for row in cur.fetchall()}
    conn.close()
    
    assert "test_customers" in tables
    assert "test_orders" in tables

def test_database_contains_expected_tables(temp_db_path, tmp_path):
    """Verify schema creates expected tables with correct structure."""
    scripts_dir = tmp_path / "db" / "scripts"
    scripts_dir.mkdir(parents=True)
    
    # Use your university schema
    schema_sql = Path("db/scripts/01_university_schema.sql").read_text()
    (scripts_dir / "01_university_schema.sql").write_text(schema_sql)
    
    run_ddl_scripts(temp_db_path, scripts_dir)
    
    conn = sqlite3.connect(temp_db_path)
    cur = conn.cursor()
    
    # Check tables exist
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {row[0] for row in cur.fetchall()}
    expected_tables = {'Students', 'Courses', 'Enrollments'}
    assert expected_tables.issubset(tables)
    
    # Verify sample data
    cur.execute("SELECT COUNT(*) FROM Students;")
    assert cur.fetchone()[0] >= 3  # At least 3 students
    
    cur.execute("SELECT COUNT(*) FROM Enrollments;")
    assert cur.fetchone()[0] == 4  # Exactly 4 enrollments
    
    conn.close()
    print("✓ Schema and data verified")

def test_real_schema_loaded():
    """Verify ACTUAL project DB has correct university tables."""
    from database_setup import DB_PATH, list_tables
    
    # Run setup first (safe overwrite for test)
    ensure_dirs()
    run_ddl_scripts(DB_PATH, Path("db/scripts"), overwrite=True)
    
    tables = list_tables()
    expected = {"Students", "Courses", "Enrollments"}
    
    assert expected.issubset(tables), f"Missing tables. Got: {tables}"
    
    # Verify data exists
    conn = sqlite3.connect(DB_PATH)
    conn.execute("BEGIN IMMEDIATE")  # Exclusive lock for test
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM Students")
    students = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM Enrollments") 
    enrolls = cur.fetchone()[0]
    
    conn.rollback()  # Don't commit test changes
    conn.close()
    
    assert students >= 3
    assert enrolls == 4
    print(f"✓ Real DB verified: {students} students, {enrolls} enrollments")

