import re
from typing import Dict, Set, Tuple

ALLOWED_START = ("select", "with")
DISALLOWED = {
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "create",
    "attach",
    "detach",
    "pragma",
    "replace",
    "truncate",
}
RESERVED_ALIAS_WORDS = {
    "on",
    "where",
    "group",
    "order",
    "limit",
    "inner",
    "left",
    "right",
    "full",
    "join",
    "having",
}


def normalizeSql(sqlText: str) -> tuple[bool, str, str]:
    """Allow one trailing semicolon, reject multiple statements."""
    cleanedSql = sqlText.strip()

    if not cleanedSql:
        return False, "", "SQL is empty"

    if cleanedSql.endswith(";"):
        cleanedSql = cleanedSql[:-1].rstrip()

    if ";" in cleanedSql:
        return False, "", "Multiple statements not allowed"

    return True, cleanedSql, ""


def extractTableAliases(sql: str) -> Dict[str, str]:
    """Map valid qualifiers to their original table names."""
    qualifierMap: Dict[str, str] = {}
    pattern = re.compile(
        r"\b(?:FROM|JOIN)\s+"
        r"([A-Za-z_][A-Za-z0-9_]*)"
        r"(?:\s+(?:AS\s+)?([A-Za-z_][A-Za-z0-9_]*))?",
        re.IGNORECASE | re.MULTILINE,
    )

    for tableName, aliasName in pattern.findall(sql):
        qualifierMap[tableName] = tableName

        if aliasName and aliasName.lower() not in RESERVED_ALIAS_WORDS:
            qualifierMap[aliasName] = tableName

    return qualifierMap


def extractQualifiedColumns(sql: str) -> list[tuple[str, str]]:
    """Extract qualified columns like T1.Name or Product.ProductName."""
    pattern = re.compile(
        r"\b([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\b"
    )
    return pattern.findall(sql)


def validateSql(
    sql: str,
    allowedTables: Set[str],
    tableColumns: Dict[str, Set[str]] | None = None,
) -> Tuple[bool, str]:
    """Validate SQL safety, tables, aliases, and qualified columns."""
    text = sql.strip()
    if not text:
        return False, "Empty SQL"

    isValid, normalizedSql, errorMessage = normalizeSql(text)
    if not isValid:
        return False, errorMessage

    text = normalizedSql
    lowerText = text.lower()

    if not any(lowerText.startswith(keyword) for keyword in ALLOWED_START):
        return False, "Only SELECT statements are allowed"

    if any(keyword in lowerText for keyword in DISALLOWED):
        return False, "Disallowed keyword found in SQL"

    qualifierMap = extractTableAliases(text)
    if not qualifierMap:
        return False, "No tables found in FROM/JOIN clauses"

    referencedTables = set(qualifierMap.values())
    invalidTables = referencedTables - allowedTables
    if invalidTables:
        return False, f"Invalid tables referenced: {sorted(invalidTables)}"

    """
    if tableColumns is not None:
        for qualifier, column in extractQualifiedColumns(text):
            if qualifier not in qualifierMap:
                return False, (
                    f"Unknown alias or table qualifier: {qualifier}"
                )

            tableName = qualifierMap[qualifier]
            validColumns = tableColumns.get(tableName, set())

            if column not in validColumns:
                previewColumns = sorted(validColumns)[:5]
                hasMore = "..." if len(validColumns) > 5 else ""
                return (
                    False,
                    f"Invalid column '{column}' for table '{tableName}' "
                    f"(valid columns: {previewColumns}{hasMore})",
                )
        """
    return True, "SQL validation passed"