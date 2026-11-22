@echo off
rem DART collect + GitHub upload in one step (run on a PC in Korea).
rem Usage, in the repo folder:  scripts\dart_all.bat
rem Companies already collected get only this years quarters (--latest).
cd /d "%~dp0.."
echo [1/4] Checking git...
if exist .git\MERGE_HEAD echo Unfinished git merge - see restore steps in README & goto fail
if exist .git\rebase-merge echo Unfinished git rebase - run: git rebase --abort & goto fail
if exist .git\rebase-apply echo Unfinished git rebase - run: git rebase --abort & goto fail
git pull --rebase --autostash
if errorlevel 1 goto fail
if "%DART_API_KEY%"=="" set /p DART_API_KEY=<C:\Users\ceter\Desktop\kiwoom\dart_key.txt
if "%DART_API_KEY%"=="" echo DART key file not found & goto fail
set PYTHONUNBUFFERED=1
echo [2/4] Collecting DART data (takes a while; do not click inside this window)...
for %%I in (cosmetics semi chem battery apparel food logistics auto steel travel) do (
  echo ---- %%I ----
  python -u scripts\update.py --industry %%I --only dart --latest
)
echo [3/4] Saving to git...
git add docs raw
git commit -m "DART update %date%"
git pull --rebase -X theirs
if errorlevel 1 goto fail
echo [4/4] Uploading to GitHub...
git push
if errorlevel 1 goto fail
echo.
echo === DONE: GitHub upload complete. Dashboards refresh in 1-2 minutes. ===
goto :eof
:fail
echo.
echo === FAILED: send a screenshot of this window to Claude. ===
