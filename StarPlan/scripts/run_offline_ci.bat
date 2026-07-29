@echo off
REM StarPlan Loop - Offline CI Command (P2-3)
REM Runs the full offline test suite without requiring Qwen API access.
REM Usage: scripts\run_offline_ci.bat
REM
REM Excludes: test_qwen_integration.py (requires DASHSCOPE_API_KEY)
REM Includes: all unit, regression, adversarial, and Layer 3 E2E tests

cd /d "%~dp0\.."

echo [CI] StarPlan Offline Test Suite
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
python -m pytest tests/ -p no:capture --ignore=tests/test_qwen_integration.py -q --tb=short
if %errorlevel% neq 0 (
    echo [FAIL] Pytest failed
    exit /b 1
)
echo.
echo [CI] All offline checks passed.
