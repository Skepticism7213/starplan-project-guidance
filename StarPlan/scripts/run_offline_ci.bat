@echo off
REM StarPlan Loop - Offline CI Command (P1-B)
REM Runs the full offline test suite with guaranteed no network model calls.
REM Usage: scripts\run_offline_ci.bat
REM
REM P1-B: Sets STARPLAN_MODEL_MODE=offline so qwen_client raises immediately
REM on any call attempt — even if .env has a valid DASHSCOPE_API_KEY.
REM Uses a dedicated writable temp dir to avoid Windows permission issues.

cd /d "%~dp0\.."

REM P1-B: Force offline mode — network tripwire active
set STARPLAN_MODEL_MODE=offline

REM P1-B: Dedicated writable temp/cache dir
set PYTEST_BASETEMP=%~dp0..\.ci_tmp\pytest
set PYTEST_CACHE_DIR=%~dp0..\.ci_tmp\pytest_cache
if not exist "%PYTEST_BASETEMP%" mkdir "%PYTEST_BASETEMP%"

echo [CI] StarPlan Offline Test Suite
echo [CI] STARPLAN_MODEL_MODE=%STARPLAN_MODEL_MODE%
echo [CI] Python: & python --version
echo.

echo [CI] Step 1/3: Compile check...
python -m compileall starplan_skills scripts tests -q
if %errorlevel% neq 0 (
    echo [FAIL] Compile check failed
    exit /b 1
)
echo [OK] Compile check passed
echo.

echo [CI] Step 2/3: Example schema validation...
python scripts/validate_examples.py
if %errorlevel% neq 0 (
    echo [FAIL] Example validation failed
    exit /b 1
)
echo [OK] Examples validated
echo.

echo [CI] Step 3/3: Pytest offline suite...
python -m pytest tests/ -p no:capture --ignore=tests/test_qwen_integration.py -q --tb=short --basetemp="%PYTEST_BASETEMP%" -o "cache_dir=%PYTEST_CACHE_DIR%"
if %errorlevel% neq 0 (
    echo [FAIL] Pytest failed
    exit /b 1
)
echo.
echo [CI] All offline checks passed. Zero network calls guaranteed.
