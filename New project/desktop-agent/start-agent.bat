@echo off
REM Runs the agent from source without opening a persistent terminal window.
REM For troubleshooting, run venv\Scripts\python.exe agent.py directly.
cd /d "%~dp0"
wscript.exe "%~dp0start-agent-hidden.vbs"
