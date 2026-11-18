@echo off
rem Wrapper for vm.ps1 (bypasses PowerShell execution policy).
rem   vm.cmd status
rem   vm.cmd start
rem   vm.cmd stop -Force
where pwsh >nul 2>nul
if %errorlevel%==0 (
    pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0vm.ps1" %*
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0vm.ps1" %*
)
