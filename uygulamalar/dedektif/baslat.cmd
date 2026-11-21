@echo off
rem Vash Dedektif'i açar (çift tıkla). İlk açılışta derlenir.
cd /d "%~dp0"
if not exist dedektif.exe call ..\..\vash.cmd build dedektif.vash
start "" dedektif.exe
