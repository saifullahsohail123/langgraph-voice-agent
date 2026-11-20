@echo off
echo ========================================================
echo  Launching Luna AI Voice Agent Web Server
echo  Powered by LangGraph, FastAPI, and MCP
echo ========================================================
echo.
python -m pip install fastapi uvicorn pydantic python-dotenv
echo.
echo Starting Web Server at http://localhost:8000
python web_app.py
pause
