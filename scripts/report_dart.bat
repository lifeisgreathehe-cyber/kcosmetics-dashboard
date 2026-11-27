@echo off
rem Report dashboard (docs/report): extra DART collect + rebuild + GitHub upload. Run on a PC in Korea.
rem Usage, in the repo folder:  scripts\report_dart.bat
rem First run takes about 1 hour (all companies, 10 years). Later runs only fetch new reports.
cd /d "%~dp0.."
echo [1/5] Checking git...
if exist .git\MERGE_HEAD echo Unfinished git merge - see restore steps in README & goto fail
if exist .git\rebase-merge echo Unfinished git rebase - run: git rebase --abort & goto fail
git pull --rebase --autostash
if errorlevel 1 goto fail
if "%DART_API_KEY%"=="" set /p DART_API_KEY=<C:\Users\ceter\Desktop\kiwoom\dart_key.txt
if "%DART_API_KEY%"=="" echo DART key file not found & goto fail
set PYTHONUNBUFFERED=1
echo [2/5] Collecting DART statements, dividends, shareholders (do not click inside this window)...
python -u scripts\report\collect_dart.py --industry all
if errorlevel 1 goto fail
echo [3/5] Building reports...
python -u scripts\report\build.py
if errorlevel 1 goto fail
echo [4/5] Saving to git...
git add raw/report docs/report
git commit -m "report: DART update %date%"
git pull --rebase -X theirs
if errorlevel 1 goto fail
echo [5/5] Uploading to GitHub...
git push
if errorlevel 1 goto fail
echo.
echo === DONE: GitHub upload complete. Report dashboard refreshes in 1-2 minutes. ===
goto :eof
:fail
echo.
echo === FAILED: send a screenshot of this window to Claude. ===
