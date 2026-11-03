@echo off
rem BANDSAMP eval-only recovery (chain died silently at EVAL stage 2026-11-03 12:30:47).
rem Runs serve+eval for all 6 merged arms + verdict. Idempotent; safe to re-run.
cd /d C:\Users\User\synapsek-closedloop
setlocal
set RUNS=C:\Users\User\synapsek-closedloop\runs\node\shinobi-1
set LOG=%RUNS%\bandsamp_eval_log.txt
set SPV=C:\Users\User\spark-venv\Scripts\python.exe
set MV=C:\Users\User\synapsek-closedloop\.venv\Scripts\python.exe
set PYTHONIOENCODING=utf-8
echo [%date% %time%] EVAL-ONLY RECOVERY START >> %LOG%

call :arm A 1
if errorlevel 1 goto :fail
call :arm A 2
if errorlevel 1 goto :fail
call :arm A 3
if errorlevel 1 goto :fail
call :arm B 1
if errorlevel 1 goto :fail
call :arm B 2
if errorlevel 1 goto :fail
call :arm B 3
if errorlevel 1 goto :fail

%MV% -u -X utf8 scripts\bandsamp_eval.py >> %LOG% 2>&1
echo [%date% %time%] BANDSAMP EVAL-ONLY DONE >> %LOG%
type %RUNS%\bandsamp_verdict.json >> %LOG%
exit /b 0

:arm
set AG=%1
set SD=%2
echo [%date% %time%] EVAL %AG% seed %SD% >> %LOG%
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object {$_.CommandLine -match 'spark_server.py' -and $_.CommandLine -match '8005'} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >> %LOG% 2>&1
start "bssrv" /b %SPV% -u scripts\spark_server.py C:\Users\User\hf_models\bandsamp_%AG%_s%SD% 8005 >> %RUNS%\bandsamp_srv_%AG%_s%SD%.txt 2>&1
powershell -NoProfile -Command "$t=0; while(-not (Test-NetConnection 127.0.0.1 -Port 8005 -WarningAction SilentlyContinue).TcpTestSucceeded -and $t -lt 600){Start-Sleep 10; $t+=10}" >> %LOG% 2>&1
set NYX_BASE_URL=http://127.0.0.1:8005/v1/chat/completions
set "NYX_SANDBOX=%RUNS%\bandsamp_sbx_%AG%%SD%"
%MV% -u -X utf8 scripts\nyx2_office_eval_v2.py bs%AG%%SD% >> %LOG% 2>&1
if errorlevel 1 goto :fail
%MV% -u -X utf8 scripts\security_eval_v21.py bs%AG%%SD% >> %LOG% 2>&1
if errorlevel 1 goto :fail
%MV% -u -X utf8 scripts\audit_eval_v1.py bs%AG%%SD% >> %LOG% 2>&1
if errorlevel 1 goto :fail
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object {$_.CommandLine -match 'spark_server.py' -and $_.CommandLine -match '8005'} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >> %LOG% 2>&1
exit /b 0

:fail
echo [%date% %time%] BANDSAMP EVAL-ONLY FAILED >> %LOG%
exit /b 1
