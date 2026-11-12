@echo off
rem DART 실적 수집 + GitHub 업로드를 한 번에 (국내 PC에서 실행)
rem 사용법: 저장소 폴더에서  scripts\dart_all.bat
rem 이미 받은 회사는 올해 분기만 새로 받고(--latest), 처음 받는 업종은 10년치를 받는다.
chcp 65001 >nul
cd /d "%~dp0.."
if exist .git\MERGE_HEAD echo Unfinished git merge - see restore steps in README & goto fail
git pull --rebase --autostash
if errorlevel 1 goto fail
if "%DART_API_KEY%"=="" set /p DART_API_KEY=<C:\Users\ceter\Desktop\kiwoom\dart_key.txt
for %%I in (cosmetics semi chem battery apparel food logistics) do python scripts\update.py --industry %%I --only dart --latest
git add docs raw
git commit -m "DART update %date%"
git pull --rebase -X theirs
if errorlevel 1 goto fail
git push
if errorlevel 1 goto fail
echo.
echo === DONE: GitHub upload complete. Dashboards refresh in 1-2 minutes. ===
goto :eof
:fail
echo.
echo === FAILED: send a screenshot of this window to Claude. ===
