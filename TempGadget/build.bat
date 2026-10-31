rem TempGadget build script. Sources: src\, installer\. Output: dist\TempGadget.exe and dist\TempGadget_Setup.exe
@echo off
setlocal
title TempGadget builder
set "VER=1.1.0"
set "AUTHOR=Artvip"
set "ROOT=%~dp0"
set "OUT=%~dp0dist\"
set "W=%TEMP%\TempGadgetBuild"
set "C=%LOCALAPPDATA%\TempGadgetCache"
set "VP=%C%\venv\Scripts"

rem Persistent cache (venv + LibreHardwareMonitor DLLs). Run with /clean to wipe it and force a full rebuild.
if /i "%~1"=="/clean" rmdir /s /q "%C%" 2>nul
mkdir "%C%" 2>nul
mkdir "%OUT%" 2>nul

echo [1/7] Preparing...
if exist "%W%" rmdir /s /q "%W%"
mkdir "%W%" || goto fail
copy /y "%ROOT%src\temp_gadget.py" "%W%\temp_gadget.py" >nul || goto fail

echo [2/7] Python environment...
if exist "%VP%\python.exe" "%VP%\python.exe" -c "import PySide6, clr, PyInstaller" >nul 2>&1 && (echo Already installed, skipping. & goto depsok)
set PY=
for %%V in (3.13 3.12 3.11 3.10) do if not defined PY py -%%V -c "pass" >nul 2>&1 && set "PY=py -%%V"
if not defined PY python -c "import sys; sys.exit(not ((3,9) <= sys.version_info[:2] <= (3,13)))" >nul 2>&1 && set "PY=python"
if not exist "%VP%\python.exe" if not defined PY goto nopython
if not exist "%VP%\python.exe" %PY% -m venv "%C%\venv" || goto fail
"%VP%\python.exe" -m pip install -q --upgrade pip
"%VP%\python.exe" -m pip install -q pythonnet pyinstaller PySide6 || goto fail
:depsok

echo [3/7] LibreHardwareMonitor...
if exist "%C%\libs\LibreHardwareMonitorLib.dll" echo Already downloaded, skipping. & goto lhmok
powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; $ProgressPreference='SilentlyContinue'; Invoke-WebRequest 'https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases/latest/download/LibreHardwareMonitor.zip' -OutFile '%W%\lhm.zip'; Expand-Archive '%W%\lhm.zip' '%W%\lhm' -Force; New-Item -ItemType Directory '%C%\libs' -Force | Out-Null; Get-ChildItem '%W%\lhm' -Recurse -Filter *.dll | Copy-Item -Destination '%C%\libs' -Force" || goto fail
if not exist "%C%\libs\LibreHardwareMonitorLib.dll" goto fail
:lhmok

echo [4/7] PawnIO driver (needed for CPU temperature)...
sc query PawnIO >nul 2>&1 && (echo PawnIO already installed. & goto pawnok)
echo Installing via winget (admin rights will be requested)...
powershell -NoProfile -Command "Start-Process powershell -Verb RunAs -Wait -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-Command','winget install -e --id namazso.PawnIO --silent --accept-source-agreements --accept-package-agreements'"
sc query PawnIO >nul 2>&1 && goto pawnok
echo winget did not install it, downloading the installer directly...
powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; $ProgressPreference='SilentlyContinue'; Invoke-WebRequest 'https://github.com/namazso/PawnIO.Setup/releases/latest/download/PawnIO_setup.exe' -OutFile '%W%\PawnIO_setup.exe'; Start-Process '%W%\PawnIO_setup.exe' -Verb RunAs -Wait -ArgumentList '-install','-silent'"
sc query PawnIO >nul 2>&1 && goto pawnok
echo.
echo WARNING: could not confirm PawnIO installation. The exe will still be built,
echo but CPU temperature may show "--" until PawnIO is installed ^(winget install namazso.PawnIO^).
echo.
:pawnok

echo [5/7] Building exe (2-4 min)...
for /f %%H in ('powershell -NoProfile -Command "(Get-FileHash '%W%\temp_gadget.py').Hash"') do set "HASH=%%H"
set "OLD="
if exist "%C%\build.hash" set /p OLD=<"%C%\build.hash"
if exist "%OUT%TempGadget.exe" if "%HASH%"=="%OLD%" echo Exe is up to date, skipping build. & goto built
taskkill /f /im TempGadget.exe >nul 2>&1
cd /d "%W%"
"%VP%\pyinstaller.exe" --onefile --noconsole --log-level WARN --uac-admin --name TempGadget --add-data "%C%\libs;libs" --collect-all pythonnet --collect-all clr_loader --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick --exclude-module PySide6.Qt3DCore temp_gadget.py || goto fail
copy /y "%W%\dist\TempGadget.exe" "%OUT%TempGadget.exe" >nul || goto fail
cd /d "%OUT%"
>"%C%\build.hash" echo %HASH%
:built
rmdir /s /q "%W%"

echo [6/7] Installer ^(Inno Setup^)...
call :makesetup
echo.
echo [7/7] Done: %OUT%TempGadget.exe
if not exist "%OUT%TempGadget_Setup.exe" goto runexe
echo Installer: %OUT%TempGadget_Setup.exe
start "" "%OUT%TempGadget_Setup.exe"
exit /b 0
:runexe
start "" "%OUT%TempGadget.exe"
exit /b 0

:makesetup
del "%OUT%TempGadget_Setup.exe" 2>nul
set "ISCC=%C%\inno\ISCC.exe"
if exist "%ISCC%" goto isccok
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ISCC%" goto isccok
set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if exist "%ISCC%" goto isccok
set "ISCC=%C%\inno\ISCC.exe"
echo Downloading Inno Setup ^(one time^)...
powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; $ProgressPreference='SilentlyContinue'; Invoke-WebRequest 'https://jrsoftware.org/download.php/is.exe' -OutFile '%C%\is_setup.exe'"
if not exist "%C%\is_setup.exe" goto setupfail
start "" /wait "%C%\is_setup.exe" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /CURRENTUSER /DIR="%C%\inno"
if not exist "%ISCC%" goto setupfail
:isccok
set "S=%C%\setup"
rmdir /s /q "%S%" 2>nul
mkdir "%S%"
powershell -NoProfile -Command "$u=New-Object Text.UTF8Encoding $true; foreach($f in 'setup.iss','license.txt','info.txt'){ $x=[regex]::Replace([IO.File]::ReadAllText('%ROOT%installer\'+$f,[Text.Encoding]::UTF8),'\r?\n',[Environment]::NewLine).Replace('@AUTHOR@',$env:AUTHOR).Replace('@VER@',$env:VER); [IO.File]::WriteAllText('%S%\'+$f,$x,$u) }" || goto setupfail
"%ISCC%" /Q "/DAppVer=%VER%" "/DAppAuthor=%AUTHOR%" "/DSrcExe=%OUT%TempGadget.exe" "/O%OUT%." "%S%\setup.iss" || goto setupfail
exit /b 0
:setupfail
echo.
echo WARNING: installer was not created. TempGadget.exe is ready anyway.
echo Install Inno Setup manually ^(winget install JRSoftware.InnoSetup^) and run this file again.
exit /b 0

:nopython
echo Python 3.9-3.13 not found.
where winget >nul 2>&1 || (echo Install Python 3.12 from https://www.python.org/downloads/ and run this file again. & pause & exit /b 1)
choice /c YN /m "Install Python 3.12 via winget"
if errorlevel 2 exit /b 1
winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
echo.
echo Python installed. Close this window and run this file again.
pause
exit /b 0

:fail
echo.
echo Build failed. See the messages above.
pause
exit /b 1
