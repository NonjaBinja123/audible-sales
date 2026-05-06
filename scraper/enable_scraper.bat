@echo off
if exist "%~dp0scraper.disabled" (
    del "%~dp0scraper.disabled"
    echo Scraper enabled.
) else (
    echo Scraper was already enabled.
)
