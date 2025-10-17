@echo off
setlocal
if "%PWSH%"=="" set "PWSH=pwsh.exe"
for /f "delims=" %%i in ('git rev-parse --show-toplevel') do set "ROOT=%%i"
"%PWSH%" -NoLogo -NoProfile -File "%ROOT%\.githooks\pre-commit.ps1"
exit /b %ERRORLEVEL%
