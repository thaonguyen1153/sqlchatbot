@echo off
call conda activate sqlchatbotenv

REM Start Ollama (adjust if different command)
start "" ollama serve

REM Start FastAPI backend
start "" python backend/app.py

REM Start Streamlit app (foreground)
streamlit run app_streamlit.py