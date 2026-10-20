@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8503
) else if exist "..\.venv\Scripts\python.exe" (
  "..\.venv\Scripts\python.exe" -m streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8503
) else (
  echo Create a Python 3.10+ virtual environment first:
  echo py -3 -m venv .venv
  echo .venv\Scripts\python.exe -m pip install -r requirements.txt
)
pause
