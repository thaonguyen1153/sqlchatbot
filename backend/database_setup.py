# database_setup.py
# Initializes SQLite database for BIP project by running DDL scripts.
# Stores database in data/ directory and scripts in db/scripts/.

import sqlite3
import os
from pathlib import Path

# Constants
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
DB_PATH = PROJECT_ROOT / "data" / "bip.db"
DB_DIR = PROJECT_ROOT / "data"
SCRIPTS_DIR = PROJECT_ROOT / "db" / "scripts"
CHROMA_DIR = PROJECT_ROOT / "chroma_db"
SCRIPT_EXT = ".sql"

def ensure_dirs():
    """Create required directories."""
    DB_DIR.mkdir(exist_ok=True)
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

def run_ddl_scripts(db_path: Path, scripts_dir: Path, overwrite: bool = False):
    """Safe DDL execution."""
    if db_path.exists() and not overwrite:
        print(f"DB exists, skipping. Use overwrite=True to reset.")
        return
    
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")  # Enforce FKs
    
    script_files = sorted(scripts_dir.glob("*.sql"))
    if not script_files:
        print("No .sql files in", scripts_dir)
        conn.close()
        return
    
    for script_file in script_files:
        print(f"Running {script_file.name}...")
        try:
            with open(script_file, 'r') as f:
                sql = f.read()
            conn.executescript(sql)
            print(f"✓ {script_file.name}")
        except Exception as e:
            print(f"✗ {script_file.name}: {e}")
            conn.rollback()
    
    conn.commit()
    conn.close()
    print(f"Database ready: {db_path}")



def run_specific_script(script_name: str):
    """Run one specific script file."""
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        print(f"Script not found: {script_path}")
        return
    
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    print(f"Running {script_name}...")
    with open(script_path, "r") as f:
        sql = f.read()
    cur.executescript(sql)
    
    conn.commit()
    conn.close()
    print(f"✓ {script_name} executed on {DB_PATH}")

# Usage: run_specific_script("01_university_schema.sql")

def list_tables(db_path: Path = None):
    """List all tables. Auto-creates DB if missing."""
    if db_path is None:
        db_path = DB_PATH
    
    # Ensure DB exists
    if not db_path.exists():
        print("⚠️ No DB found. Running setup...")
        ensure_dirs()
        run_ddl_scripts(db_path, SCRIPTS_DIR, overwrite=False)
    
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """)
        tables = [row[0] for row in cur.fetchall()]
        conn.close()
        
        if tables:
            print(f"Tables in {db_path}: {tables}")
            return tables
        else:
            print("No tables found. Run setup first.")
            return []
            
    except sqlite3.Error as e:
        print(f"DB error: {e}")
        return []

# Usage: python -c "from database_setup import list_tables; list_tables()"

def show_sample_data():
    """Show sample data from each table."""
    tables = list_tables()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    for table in tables:
        cur.execute(f"SELECT * FROM {table} LIMIT 2;")
        rows = cur.fetchall()
        print(f"\n{table} (first 2 rows):")
        for row in rows:
            print(f"  {row}")
    
    conn.close()


# Update main()
def main():
    ensure_dirs()
    run_ddl_scripts(DB_PATH, SCRIPTS_DIR, overwrite=True)  # Set False for safety


if __name__ == "__main__":
    main()
