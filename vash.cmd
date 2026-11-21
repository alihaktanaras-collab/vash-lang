@echo off
rem Vash komutu: vash run / build / ir / check [--json] oyun.vash
rem Derleyicinin kendisi de Vash ile yazilmis: vashc\vash.vash  (calisan hali: vashc\vash.exe)
rem   vash yenile          vashc\ klasorundeki derleyici degistiyse vash.exe'yi yeniden uret
rem   vash py run x.vash   eski (Python) derleyiciyle calistir - karsilastirma icin
chcp 65001 > nul
setlocal
rem Mesaj dili: VASH_DIL; yoksa Windows'un arayuz dili (tr-TR ise Turkce)
set "VASH_CMD_DIL=%VASH_DIL%"
if not defined VASH_CMD_DIL for /f "tokens=3" %%a in ('reg query "HKCU\Control Panel\Desktop\MuiCached" /v MachinePreferredUILanguages 2^>nul ^| find "REG_"') do set "VASH_CMD_DIL=%%a"
if /i "%VASH_CMD_DIL:~0,2%"=="tr" set "VASH_CMD_DIL=tr"
set "KOK=%~dp0"
set "VASH_KOK=%KOK:~0,-1%"
set "PYTHONIOENCODING=utf-8"

if /i "%~1"=="py" goto python
if /i "%~1"=="yenile" goto yenile
if /i "%~1"=="kum" goto kum

set "VASH_KOMUT=%~1"
set "VASH_DOSYA=%~2"
set "VASH_TAM=%~f2"
set "VASH_JSON="
if /i not "%~1"=="check" goto komut_check_degil
if /i not "%~2"=="--json" goto komut_tamam
set "VASH_JSON=1"
set "VASH_DOSYA=%~3"
set "VASH_TAM=%~f3"
goto komut_tamam
:komut_check_degil
if /i "%~1"=="run" goto komut_tamam
if /i "%~1"=="build" goto komut_tamam
if /i "%~1"=="ir" goto komut_tamam
set "VASH_KOMUT=build"
set "VASH_DOSYA=%~1"
set "VASH_TAM=%~f1"
:komut_tamam
if "%VASH_DOSYA%"=="" goto kullanim

rem vash run dosya.vash a b c  ->  programa "a b c" verilir (args() ile okunur)
set "VASH_ARGUMANLAR="
if /i not "%VASH_KOMUT%"=="run" goto argumanlar_bitti
shift
shift
:arguman_dongu
if "%~1"=="" goto argumanlar_bitti
set VASH_ARGUMANLAR=%VASH_ARGUMANLAR% %1
shift
goto arguman_dongu
:argumanlar_bitti
:kum_hazir

rem clang'i bul: once PATH, sonra winget'in kurdugu klasor
set "VASH_CLANG="
for /f "delims=" %%i in ('where clang 2^>nul') do if not defined VASH_CLANG set "VASH_CLANG=%%i"
if not defined VASH_CLANG for /d %%d in ("%LOCALAPPDATA%\Microsoft\WinGet\Packages\*LLVM*") do for /d %%e in ("%%d\*") do if exist "%%e\bin\clang.exe" if not defined VASH_CLANG set "VASH_CLANG=%%e\bin\clang.exe"

rem Ilk seferde: Vash derleyicisini (bir kere) Python'daki derleyiciyle uret
if not exist "%KOK%vashc\vash.exe" call :hazirla || exit /b 1
"%KOK%vashc\vash.exe"
exit /b %errorlevel%

rem vash kum [--izin files+net] [--klasor yol] [--sure saniye] dosya.vash [argumanlar]
:kum
set "VASH_KOMUT=kum"
set "VASH_KUM=1"
set "VASH_KUM_IZIN="
set "VASH_KUM_KLASORU="
set "VASH_KUM_SURE=30"
shift
:kum_secenek
if /i "%~1"=="--izin" (
    set "VASH_KUM_IZIN=%~2"
    shift
    shift
    goto kum_secenek
)
if /i "%~1"=="--klasor" (
    set "VASH_KUM_KLASORU=%~f2"
    shift
    shift
    goto kum_secenek
)
if /i "%~1"=="--sure" (
    set "VASH_KUM_SURE=%~2"
    shift
    shift
    goto kum_secenek
)
set "VASH_DOSYA=%~1"
set "VASH_TAM=%~f1"
set "VASH_JSON="
if "%VASH_DOSYA%"=="" goto kullanim
set "VASH_ARGUMANLAR="
shift
:kum_arguman
if "%~1"=="" goto kum_bitti
set VASH_ARGUMANLAR=%VASH_ARGUMANLAR% %1
shift
goto kum_arguman
:kum_bitti
goto kum_hazir

:hazirla
if /i "%VASH_CMD_DIL%"=="tr" (echo Vash derleyicisi ilk kez hazirlaniyor...) else (echo Preparing the Vash compiler for the first time...)
python "%KOK%derleyici\derle.py" build "%KOK%vashc\vash.vash" > nul
if errorlevel 1 (
    if /i "%VASH_CMD_DIL%"=="tr" (echo HATA: Vash derleyicisi uretilemedi.) else (echo ERROR: Could not build the Vash compiler.)
    exit /b 1
)
exit /b 0

:yenile
if exist "%KOK%vashc\vash.exe" del "%KOK%vashc\vash.exe"
call :hazirla || exit /b 1
if /i "%VASH_CMD_DIL%"=="tr" (echo Vash derleyicisi yenilendi: vashc\vash.exe) else (echo Vash compiler rebuilt: vashc\vash.exe)
exit /b 0

:python
python "%KOK%derleyici\derle.py" %2 %3 %4 %5
exit /b %errorlevel%

:kullanim
if /i "%VASH_CMD_DIL%"=="tr" goto kullanim_tr
echo Vash compiler
echo.
echo Usage:
echo   vash run   file.vash     compile and run
echo   vash build file.vash     only make the .exe
echo   vash ir    file.vash     show the generated LLVM IR
echo   vash check file.vash     only check for errors (--json: for agents)
echo   vash kum [--izin files+net] [--klasor dir] [--sure 30] file.vash
echo                            sandbox: only the given permissions, files only inside the folder, time limit
exit /b 1
:kullanim_tr
echo Vash derleyicisi
echo.
echo Kullanim:
echo   vash run   dosya.vash    derle ve calistir
echo   vash build dosya.vash    sadece .exe uret
echo   vash ir    dosya.vash    uretilen LLVM IR'i goster
echo   vash check dosya.vash    sadece hatalari kontrol et (--json: ajanlar icin)
echo   vash kum [--izin files+net] [--klasor klasor] [--sure 30] dosya.vash
echo                            kum havuzu: sadece verilen izinler, dosyalar sadece klasorde, sure siniri
exit /b 1
