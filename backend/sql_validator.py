# backend/sql_validator.py
from typing import Set, Tuple

DISALLOWED = {"insert", "update", "delete", "drop", "alter"}
ALLOWED_START = {"select"}

def validateSql(sql: str, allowedTables: Set[str]) -> Tuple[bool, str]:
    text = sql.strip().lower()
    if ";" in text:
        return False, "Multiple statements not allowed"
    if not any(text.startswith(k) for k in ALLOWED_START):
        return False, "Only SELECT statements are allowed"
    if any(k in text for k in DISALLOWED):
        return False, "Disallowed keyword in SQL"

    # Very simple table check (can be improved with sqlglot later)
    usedTables = {t for t in allowedTables if t.lower() in text}
    if not usedTables:
        return False, "No allowed tables referenced"
    return True, "ok"
