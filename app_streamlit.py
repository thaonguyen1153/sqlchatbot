import logging
from pathlib import Path
import re
from typing import Dict, Set
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

PROJECT_ROOT = Path(__file__).parent
LOG_FILE = PROJECT_ROOT / "logs" / "text2sql.log"
API_BASE_URL = "http://localhost:8000"
DEFAULT_DB_NAME = "retail"
DEFAULT_CHART_TYPE = "Bar"
CHART_OPTIONS = ["None", "Bar", "Line", "Pie", "Scatter"]

st.set_page_config(page_title="Text-to-SQL RAG", layout="wide")

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(LOG_FILE)],
)
logger = logging.getLogger("Text2SQL-UI")


def fetchApiData(endpoint: str, params: dict | None = None) -> dict:
    response = requests.get(
        f"{API_BASE_URL}{endpoint}",
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=30)
def getDatabaseList() -> list[str]:
    data = fetchApiData("/databases")
    return data.get("databases", [])


@st.cache_data(ttl=30)
def getTableList(dbName: str) -> list[str]:
    data = fetchApiData("/tables", {"db_name": dbName})
    return data.get("tables", [])


@st.cache_data(ttl=30)
def getHealthInfo(dbName: str) -> dict:
    return fetchApiData("/health", {"db_name": dbName})

DATE_NAME_HINTS = (
    "date",
    "time",
    "day",
    "month",
    "year",
    "created",
    "updated",
    "timestamp",
)
def isDateLikeName(columnName: str) -> bool:
    lowerName = columnName.lower()
    return any(hint in lowerName for hint in DATE_NAME_HINTS)
def looksLikeDateValues(series: pd.Series) -> bool:
    cleanedSeries = series.dropna().astype(str).str.strip()

    if cleanedSeries.empty:
        return False

    sampleSeries = cleanedSeries.head(20)

    datePattern = re.compile(
        r"^("
        r"\d{4}-\d{2}-\d{2}"
        r"|\d{4}/\d{2}/\d{2}"
        r"|\d{2}/\d{2}/\d{4}"
        r"|\d{2}-\d{2}-\d{4}"
        r"|\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}(:\d{2})?"
        r")$"
    )

    matchCount = sampleSeries.str.match(datePattern).sum()
    return matchCount / len(sampleSeries) >= 0.8


def getDateColumns(df: pd.DataFrame) -> list[str]:
    dateColumns = []

    for column in df.columns:
        series = df[column]

        if pd.api.types.is_datetime64_any_dtype(series):
            dateColumns.append(column)
            continue

        if not isDateLikeName(column):
            continue

        if not looksLikeDateValues(series):
            continue

        converted = pd.to_datetime(series, errors="coerce")
        validRatio = converted.notna().sum() / len(series.dropna()) \
            if len(series.dropna()) > 0 else 0

        if validRatio >= 0.8:
            dateColumns.append(column)

    return dateColumns


def getColumnGroups(df: pd.DataFrame) -> tuple[list[str], list[str], list[str]]:
    numericColumns = df.select_dtypes(include="number").columns.tolist()
    dateColumns = getDateColumns(df)
    textColumns = [
        column
        for column in df.columns
        if column not in numericColumns + dateColumns
    ]
    return numericColumns, dateColumns, textColumns


def getAvailableChartTypes(df: pd.DataFrame) -> list[str]:
    numericColumns, dateColumns, textColumns = getColumnGroups(df)
    availableChartTypes = ["None"]

    canUseBar = (
        (bool(textColumns) and bool(numericColumns)) or
        len(numericColumns) >= 2
    )
    if canUseBar:
        availableChartTypes.append("Bar")

    canUseLine = (
        (bool(dateColumns) and bool(numericColumns)) or
        len(numericColumns) >= 2 #
    )
    if canUseLine:
        availableChartTypes.append("Line")

    canUsePie = (
        (bool(textColumns) and bool(numericColumns)) or
        bool(textColumns)
    )
    if canUsePie:
        availableChartTypes.append("Pie")

    if len(numericColumns) >= 2:
        availableChartTypes.append("Scatter")

    return availableChartTypes


def buildChart(df: pd.DataFrame, chartType: str):
    numericColumns, dateColumns, textColumns = getColumnGroups(df)

    if chartType == "None":
        return None

    if chartType == "Bar":
        if textColumns and numericColumns:
            return px.bar(df, x=textColumns[0], y=numericColumns[0])
        if len(numericColumns) >= 2:
            return px.bar(df, x=numericColumns[0], y=numericColumns[1])
        raise ValueError(
            "Bar chart needs category+number or two numeric columns."
        )
    
    #st.warning(f"Has date columns: {bool(dateColumns)} | Has text columns: {bool(textColumns)} | Has numeric columns: {bool(numericColumns)}")
    if chartType == "Line":
        if dateColumns and numericColumns:
            chartData = df.copy()
            firstDateColumn = dateColumns[0]
            chartData[firstDateColumn] = pd.to_datetime(
                chartData[firstDateColumn]
            )
            return px.line(
                chartData,
                x=firstDateColumn,
                y=numericColumns[0],
            )
        if textColumns and numericColumns:
            return px.line(df, x=textColumns[0], y=numericColumns[0])
        if len(numericColumns) >= 2:
            return px.line(df, x=numericColumns[0], y=numericColumns[1])
        raise ValueError(
            "Line chart needs date+number, text+number, or two numeric columns."
        )
    
    if chartType == "Pie":
        if textColumns and numericColumns:
            return px.pie(df, names=textColumns[0], values=numericColumns[0])
        if textColumns:
            return px.pie(df, names=textColumns[0])
        raise ValueError("Pie chart needs at least one categorical column.")

    if chartType == "Scatter":
        if len(numericColumns) >= 2:
            return px.scatter(df, x=numericColumns[0], y=numericColumns[1])
        raise ValueError("Scatter chart needs two numeric columns.")

    raise ValueError(f"Unsupported chart type: {chartType}")


def initializeState() -> None:
    defaults = {
        "messages": [],
        "selectedDb": DEFAULT_DB_NAME,
        "showSql": True,
        "showLogs": False,
        "chartType": DEFAULT_CHART_TYPE,
        "lastQuestion": "",
        "lastQueryId": None,
        "lastRows": [],
        "lastTotalRows": 0,
        "lastSql": None,
        "lastError": None,
        "lastQueryDb": DEFAULT_DB_NAME,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


initializeState()

st.title("Text-to-SQL Chatbot")
st.caption("Query multiple SQLite databases through one FastAPI backend.")

with st.sidebar:
    st.header("Configuration")

    try:
        databaseList = getDatabaseList()
    except requests.RequestException as error:
        databaseList = []
        st.error(f"Failed to load databases: {error}")

    if not databaseList:
        st.warning("No databases found from /databases.")
        selectedDb = DEFAULT_DB_NAME
    else:
        if st.session_state.selectedDb not in databaseList:
            st.session_state.selectedDb = databaseList[0]

        selectedDb = st.selectbox(
            "Database",
            options=databaseList,
            key="selectedDb",
            help="Choose which SQLite database to query.",
        )

    st.divider()
    st.subheader("Query Options")
    showSql = st.checkbox(
        "Show generated SQL",
        key="showSql",
    )

    st.divider()
    st.subheader("Database Info")
    try:
        healthInfo = getHealthInfo(selectedDb)
        st.caption(f"Collection: {healthInfo.get('collection', 'N/A')}")
        st.caption(f"Chunks: {healthInfo.get('chunks', 0)}")
    except requests.RequestException as error:
        st.info(f"Health check unavailable: {error}")

    try:
        tableList = getTableList(selectedDb)
        with st.expander("Tables", expanded=False):
            if tableList:
                for table in tableList:
                    st.write(f"- {table}")
            else:
                st.write("No tables found.")
    except requests.RequestException as error:
        st.info(f"Could not load tables: {error}")

    st.divider()
    st.subheader("Logs")
    showLogs = st.checkbox(
        "Show debug logs",
        key="showLogs",
    )
    if showLogs:
        with st.expander("Recent Logs", expanded=False):
            if LOG_FILE.exists():
                logText = LOG_FILE.read_text(encoding="utf-8")
                st.code(logText, language="log")
            else:
                st.info("No logs yet.")

with st.form("query_form"):
    question = st.text_input(
        "Ask a question",
        placeholder=f"Ask a question about the {selectedDb} database",
    )
    submitted = st.form_submit_button("Run query")

if submitted:
    cleanedQuestion = question.strip()

    if not cleanedQuestion:
        st.warning("Please enter a question.")
    else:
        logger.info("UI: query='%s' | db=%s", cleanedQuestion, selectedDb)
        st.session_state.messages.append(
            {
                "role": "user",
                "content": f"[{selectedDb}] {cleanedQuestion}",
            }
        )

        payload = {
            "question": cleanedQuestion,
            "db_name": selectedDb,
            "show_sql": showSql,
        }

        try:
            with st.spinner("Querying backend..."):
                response = requests.post(
                    f"{API_BASE_URL}/query",
                    json=payload,
                    timeout=60,
                )
                response.raise_for_status()
                data = response.json()

            queryId = data.get("query_id", "unknown")
            rows = data.get("rows", [])
            totalRows = data.get("total_rows", 0)
            sqlText = data.get("sql")

            st.session_state.lastQuestion = cleanedQuestion
            st.session_state.lastQueryId = queryId
            st.session_state.lastRows = rows
            st.session_state.lastTotalRows = totalRows
            st.session_state.lastSql = sqlText
            st.session_state.lastError = None
            st.session_state.lastQueryDb = selectedDb

            if rows:
                resultDf = pd.DataFrame(rows)
                availableChartTypes = getAvailableChartTypes(resultDf)
                if st.session_state.chartType not in availableChartTypes:
                    if DEFAULT_CHART_TYPE in availableChartTypes:
                        st.session_state.chartType = DEFAULT_CHART_TYPE
                    else:
                        st.session_state.chartType = availableChartTypes[0]
            else:
                st.session_state.chartType = "None"

            logger.info(
                "UI: response=%s | db=%s | rows=%s",
                queryId,
                selectedDb,
                totalRows,
            )

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": (
                        f"Database '{selectedDb}' returned {totalRows} rows."
                        if rows
                        else f"Database '{selectedDb}' returned no rows."
                    ),
                }
            )
        except requests.RequestException as error:
            logger.error("UI: API failed: %s", error)
            st.session_state.lastError = str(error)
            st.session_state.lastRows = []
            st.session_state.lastTotalRows = 0
            st.session_state.lastSql = None
            st.session_state.lastQueryId = None
            st.session_state.lastQueryDb = selectedDb
            st.session_state.chartType = "None"

if st.session_state.lastError:
    st.error(f"API error: {st.session_state.lastError}")

if st.session_state.lastQueryId or st.session_state.lastRows:
    st.subheader("Query Result")
    st.caption(
        "Database: "
        f"{st.session_state.lastQueryDb} | "
        f"Query ID: {st.session_state.lastQueryId or 'unknown'}"
    )

    if showSql and st.session_state.lastSql:
        with st.expander("Generated SQL", expanded=True):
            st.code(st.session_state.lastSql, language="sql")

    if st.session_state.lastRows:
        resultDf = pd.DataFrame(st.session_state.lastRows)
        availableChartTypes = getAvailableChartTypes(resultDf)

        if st.session_state.chartType not in availableChartTypes:
            if DEFAULT_CHART_TYPE in availableChartTypes:
                st.session_state.chartType = DEFAULT_CHART_TYPE
            else:
                st.session_state.chartType = availableChartTypes[0]

        resultTab, chartTab, historyTab = st.tabs(
            ["Results", "Visualization", "History"]
        )

        with resultTab:
            st.write(f"Returned {st.session_state.lastTotalRows} rows.")
            st.dataframe(resultDf, use_container_width=True)

        with chartTab:
            chartControlCol, chartDisplayCol = st.columns([1, 3])

            with chartControlCol:
                st.selectbox(
                    "Chart type",
                    options=availableChartTypes,
                    key="chartType",
                    help="Only chart types suitable for the last result are shown.",
                )

                st.caption(
                    "Available: " + ", ".join(availableChartTypes)
                )

            with chartDisplayCol:
                if st.session_state.chartType == "None":
                    st.info("No suitable chart selected for the last result.")
                else:
                    try:
                        fig = buildChart(
                            resultDf,
                            st.session_state.chartType,
                        )
                        st.plotly_chart(fig, use_container_width=True)
                        st.caption(
                            f"Chart type: {st.session_state.chartType}"
                        )
                    except ValueError as error:
                        st.warning(str(error))

        with historyTab:
            for message in st.session_state.messages[-10:]:
                with st.chat_message(message["role"]):
                    st.write(message["content"])
    else:
        st.info("No rows returned for this query.")

if st.session_state.messages:
    st.subheader("Recent Conversation")
    for message in st.session_state.messages[-5:]:
        with st.chat_message(message["role"]):
            st.write(message["content"])