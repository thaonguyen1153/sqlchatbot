# app_streamlit.py
import streamlit as st
import requests
import logging
from datetime import datetime
from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

PROJECT_ROOT = Path(__file__).parent
LOG_FILE = PROJECT_ROOT / "logs" / "text2sql.log"

# Streamlit logger (console + file)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(LOG_FILE)]
)
logger = logging.getLogger("Text2SQL-UI")

API_URL = "http://localhost:8000/query"

st.set_page_config(page_title="Text-to-SQL RAG", layout="centered")
st.title("University Text-to-SQL Chatbot")

# Chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar for logs toggle
show_logs = st.sidebar.checkbox("Show Debug Logs", value=False)
if show_logs:
    with st.sidebar.expander("Recent Logs"):
        if LOG_FILE.exists():
            with open(LOG_FILE, "r") as f:
                st.code(f.read(), language="log")
        else:
            st.info("No logs yet") 

chart_type = st.sidebar.selectbox(
    "📈 Auto-generate Chart:",
    ["None", "Bar (categorical)", "Line (time)", "Pie (proportions)"]
) 
with st.form("query_form"):
    question = st.text_input("Ask a question about the university DB (students/courses/grades)")
    show_sql = st.checkbox("Show generated SQL", value=True)
    submitted = st.form_submit_button("Run query")

if submitted:
    if not question.strip():
        st.warning("Please enter a question.")
    else:
        logger.info(f"UI: New query '{question}'")
        # Log step 1: Input validation
        logger.info(f"UI: 1. Validated input: '{question}'")
        st.session_state.messages.append({"role": "user", "content": question})
    
        payload = {"question": question.strip(), "show_sql": show_sql}
        try:
            # Log step 2: API call
            logger.info("UI: 2. Calling FastAPI...")
            with st.spinner("Querying backend..."):
                resp = requests.post(API_URL, json=payload, timeout=60)
                resp.raise_for_status()
                data = resp.json()

            query_id = data.get("query_id", "unknown")
            logger.info(f"UI: 3. API response {query_id}: {len(data.get('rows', []))} rows")
        
            # Log step 4: Render SQL
            if show_sql and data.get("sql"):
                st.subheader("Generated SQL")
                st.code(data["sql"], language="sql")
                logger.info(f"UI: 4. Rendered SQL ({len(data['sql'])} chars)")

            rows = data.get("rows", [])
            total_rows = data.get("total_rows", 0)
            
            if rows:
                df = pd.DataFrame(rows)
                logger.info(f"UI: df created | Shape: {df.shape} | Dtypes: {dict(df.dtypes)}")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if show_sql and data.get("sql"):
                        st.subheader("📝 Generated SQL")
                        st.code(data["sql"], language="sql")
                        logger.info(f"UI: 4. Rendered SQL ({len(data['sql'])} chars)")
                
                with col2:
                    st.subheader(f"📊 Results ({total_rows} rows)")
                    st.dataframe(df, width='stretch')  # Now uses df
                    logger.info(f"UI: 5. Table rendered")
                
                # Charts (uses df)
                if chart_type != "None":
                    st.subheader("📈 Visualization")
                    
                    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
                    cat_cols = df.select_dtypes(include=['object']).columns.tolist()
                    
                    try:
                        if chart_type == "Bar (categorical)" and cat_cols and numeric_cols:
                            fig = px.bar(df, x=cat_cols[0], y=numeric_cols[0])
                        elif chart_type == "Pie (proportions)" and cat_cols:
                            fig = px.pie(df, names=cat_cols[0])
                        else:
                            fig = px.bar(df, x=df.columns[0], y=df.select_dtypes(include=['number']).columns[0])
                        
                        st.plotly_chart(fig, width='stretch')
                        logger.info(f"UI: Chart OK | {chart_type}")
                    except Exception as chart_err:
                        logger.error(f"UI: Chart failed: {chart_err}")
                        st.error(f"Chart error: {chart_err}")
                
                st.session_state.messages.append({"role": "assistant", "content": f"Found {total_rows} rows"})
            else:
                st.info("No rows returned for this query.")
                logger.warning("UI: 6. No results")
        except requests.exceptions.RequestException as e:
            logger.error(f"UI: API failed: {e}")
            st.error(f"API error: {e}")

# Chat history display
for msg in st.session_state.messages[-5:]:  # Last 5
    with st.chat_message(msg["role"]):
        st.write(msg["content"])