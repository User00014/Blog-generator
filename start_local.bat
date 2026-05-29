@echo off
setlocal EnableExtensions

cd /d "%~dp0"

set "PYTHON_EXE=E:\anaconda\envs\envb\python.exe"
set "APP_URL=http://127.0.0.1:4173"
set "PID_FILE=%~dp0.local_server.pid"

:menu
cls
echo AI Blog Local Launcher
echo.
echo 1. Start
echo 2. Check status
echo 3. Stop
echo 4. Restart
echo 5. Exit
echo.
set /p "CHOICE=Select option: "

if "%CHOICE%"=="1" goto start_server
if "%CHOICE%"=="2" goto check_status
if "%CHOICE%"=="3" goto stop_server
if "%CHOICE%"=="4" goto restart_server
if "%CHOICE%"=="5" goto end

echo Invalid option.
pause
goto menu

:start_server
if not exist "%PYTHON_EXE%" (
  echo Python not found: %PYTHON_EXE%
  pause
  goto menu
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -Uri '%APP_URL%/api/config' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } } catch {}; exit 1"
if not errorlevel 1 (
  echo Server is already running.
  start "" "%APP_URL%"
  pause
  goto menu
)

echo Starting backend...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p = Start-Process -FilePath '%PYTHON_EXE%' -ArgumentList 'run.py' -WorkingDirectory '%~dp0' -WindowStyle Minimized -PassThru; Set-Content -Path '%PID_FILE%' -Value $p.Id"

echo Waiting for backend...
timeout /t 8 /nobreak >nul

powershell -NoProfile -ExecutionPolicy Bypass -Command "for ($i=0; $i -lt 20; $i++) { try { $r = Invoke-WebRequest -Uri '%APP_URL%/api/config' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } } catch { Start-Sleep -Seconds 1 } }; exit 1"
if errorlevel 1 (
  echo Backend did not respond.
  pause
  goto menu
)

echo Server started.
start "" "%APP_URL%"
pause
goto menu

:check_status
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -Uri '%APP_URL%/api/config' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { Write-Host 'Status: running'; exit 0 } } catch {}; Write-Host 'Status: stopped'; exit 1"
pause
goto menu

:stop_server
if exist "%PID_FILE%" (
  for /f %%p in (%PID_FILE%) do (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Stop-Process -Id %%p -Force -ErrorAction Stop; Write-Host 'Stopped process %%p' } catch { Write-Host 'Process %%p not running' }"
  )
  del "%PID_FILE%" >nul 2>nul
) else (
  echo No pid file found. Trying port cleanup.
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$c = Get-NetTCPConnection -LocalPort 4173 -State Listen -ErrorAction SilentlyContinue; if ($c) { $c | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { try { Stop-Process -Id $_ -Force; Write-Host ('Stopped process ' + $_) } catch {} } }"
pause
goto menu

:restart_server
if exist "%PID_FILE%" (
  for /f %%p in (%PID_FILE%) do (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Stop-Process -Id %%p -Force -ErrorAction Stop; Write-Host 'Stopped process %%p' } catch { Write-Host 'Process %%p not running' }"
  )
  del "%PID_FILE%" >nul 2>nul
) else (
  echo No pid file found. Trying port cleanup.
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$c = Get-NetTCPConnection -LocalPort 4173 -State Listen -ErrorAction SilentlyContinue; if ($c) { $c | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { try { Stop-Process -Id $_ -Force; Write-Host ('Stopped process ' + $_) } catch {} } }"
echo Restarting...
goto start_server

:end
endlocal
exit /b 0
