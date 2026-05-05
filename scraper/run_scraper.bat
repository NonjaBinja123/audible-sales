@echo off
cd /d C:\Projects\AudibleTool\scraper
if not exist logs mkdir logs
C:\Projects\AudibleTool\scraper\.venv\Scripts\python.exe -u scraper.py >> logs\scraper.log 2>&1
