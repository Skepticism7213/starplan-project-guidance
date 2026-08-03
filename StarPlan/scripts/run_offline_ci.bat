@echo off
setlocal
REM StarPlan Loop - Offline CI Command (P1-B)
REM Runs the full offline test suite with guaranteed no network model calls.
REM Usage: scripts\run_offline_ci.bat
REM
REM P1-B: Sets STARPLAN_MODEL_MODE=offline so qwen_client raises immediately
REM on any call attempt -- even if .env has a valid DASHSCOPE_API_KEY.
REM Uses a dedicated writable temp dir to avoid Windows permission issues.

cd /d "%~dp0\.."

REM Keep cmd, PowerShell pipes, and Python on the same UTF-8 boundary.
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

REM P1-B: Force offline mode -- network tripwire active
set STARPLAN_MODEL_MODE=offline

REM P1-B: Dedicated writable temp/cache dir (avoid repository ACL leftovers)
set "CI_TEMP_ROOT=%TEMP%\starplan_ci_%RANDOM%_%RANDOM%"
set "PYTEST_BASETEMP=%CI_TEMP_ROOT%\pytest"
set "PYTEST_CACHE_DIR=%CI_TEMP_ROOT%\pytest_cache"
set "ASTROPY_CACHE_DIR=%TEMP%\starplan_astropy"
if not exist "%PYTEST_BASETEMP%" mkdir "%PYTEST_BASETEMP%"
if not exist "%PYTEST_CACHE_DIR%" mkdir "%PYTEST_CACHE_DIR%"
if not exist "%ASTROPY_CACHE_DIR%" mkdir "%ASTROPY_CACHE_DIR%"

set "PYTHON=python"
if exist "%~dp0..\.venv\Scripts\python.exe" set "PYTHON=%~dp0..\.venv\Scripts\python.exe"

echo [CI] StarPlan Offline Test Suite
echo [CI] STARPLAN_MODEL_MODE=%STARPLAN_MODEL_MODE%
echo [CI] Temp root: %CI_TEMP_ROOT%
echo [CI] Python:
"%PYTHON%" --version
echo.

echo [CI] Step 1/3: Compile check...
"%PYTHON%" -X utf8 -m compileall starplan_skills scripts tests -q
if errorlevel 1 (
    echo [FAIL] Compile check failed
    exit /b 1
)
echo [OK] Compile check passed
echo.

echo [CI] Step 2/3: Example schema validation...
"%PYTHON%" -X utf8 scripts/validate_examples.py
if errorlevel 1 (
    echo [FAIL] Example validation failed
    exit /b 1
)
echo [OK] Examples validated
echo.

echo [CI] Step 3/3: Pytest offline suite...
"%PYTHON%" -X utf8 -m pytest tests/ -p no:capture --ignore=tests/test_qwen_integration.py -q --tb=short --basetemp="%PYTEST_BASETEMP%" -o "cache_dir=%PYTEST_CACHE_DIR%"
if errorlevel 1 (
    echo [FAIL] Pytest failed
    exit /b 1
)
echo.
echo [CI] All offline checks passed. Zero network calls guaranteed.
