@echo off
rem Vash Engine düzenleyicisini açar (çift tıkla). İstersen bir oyun dosyası ver: baslat.cmd yol\oyun.json
cd /d "%~dp0"
if not exist duzenleyici.exe call ..\vash.cmd build duzenleyici.vash
if "%~1"=="" (start "" duzenleyici.exe ornekler/platform/oyun.json) else (start "" duzenleyici.exe "%~1")
