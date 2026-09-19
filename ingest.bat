@echo off
setlocal

set SCRIPT_DIR=%~dp0

echo ============================================
echo   Do the tu dong - tool-film-maker
echo ============================================
echo.

set /p PROJECT_NAME=Ten du an (vd: Kid dance bsixteen):
set /p CARD_DRIVE=O dia the nho (vd: E:):
set /p DEST_CHOICE=Upload len dau? [drive/onedrive/both] (Enter = both):

if "%DEST_CHOICE%"=="" set DEST_CHOICE=both

echo.
echo Dang chay ingest.ps1 ...
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%ingest.ps1" -CardDrive "%CARD_DRIVE%" -ProjectName "%PROJECT_NAME%" -Dest %DEST_CHOICE%

echo.
echo ============================================
echo   Xong. Doc log o thu muc _ingest_logs neu can.
echo ============================================
pause
