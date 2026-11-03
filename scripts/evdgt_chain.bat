@echo off
rem EVDGT kill-test chain (pre-reg EVDGT_PREREG.md). Trains U(uniform)+D(dynamic) x 3 seeds,
rem merges, serves+evals each on :8006, verdict. Abort-on-error, skip-if-done.
cd /d C:\Users\User\synapsek-closedloop
setlocal
set RUNS=C:\Users\User\synapsek-closedloop\runs\node\shinobi-1
set LOG=%RUNS%\evdgt_log.txt
set SPV=C:\Users\User\spark-venv\Scripts\python.exe
set MV=C:\Users\User\synapsek-closedloop\.venv\Scripts\python.exe
set PYTHONIOENCODING=utf-8
echo [%date% %time%] EVDGT CHAIN START >> %LOG%

for %%A in (U D) do for %%S in (1 2 3) do (
  call :arm %%A %%S
  if errorlevel 1 goto :fail
)

%MV% -u -X utf8 scripts\evdgt_eval.py >> %LOG% 2>&1
echo [%date% %time%] EVDGT CHAIN DONE >> %LOG%
type %RUNS%\evdgt_verdict.json >> %LOG%
exit /b 0

:arm
set AG=%1
set SD=%2
if exist "%RUNS%\audit_eval_v1_e%AG%%SD%.json" (echo [%date% %time%] SKIP %AG%_%SD% - already done >> %LOG% & exit /b 0)
echo [%date% %time%] TRAIN %AG% seed %SD% >> %LOG%
%SPV% -u -X utf8 scripts\evdgt_train.py %AG% %SD% >> %LOG% 2>&1
if errorlevel 1 goto :fail
echo [%date% %time%] MERGE %AG% seed %SD% >> %LOG%
%SPV% -u -X utf8 scripts\evdgt_merge.py %AG% %SD% >> %LOG% 2>&1
if errorlevel 1 goto :fail
echo [%date% %time%] EVAL %AG% seed %SD% >> %LOG%
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'nyx2_office_eval|security_eval_v21|audit_eval_v1' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >> %LOG% 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object {$_.CommandLine -match 'spark_server.py' -and $_.CommandLine -match '8006'} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >> %LOG% 2>&1
start "evsrv" /b %SPV% -u scripts\spark_server.py C:\Users\User\hf_models\evdgt_%AG%_s%SD% 8006 >> %RUNS%\evdgt_srv_%AG%_s%SD%.txt 2>&1
powershell -NoProfile -Command "$t=0; while(-not (Test-NetConnection 127.0.0.1 -Port 8006 -WarningAction SilentlyContinue).TcpTestSucceeded -and $t -lt 600){Start-Sleep 10; $t+=10}" >> %LOG% 2>&1
set NYX_BASE_URL=http://127.0.0.1:8006/v1/chat/completions
set "NYX_SANDBOX=%RUNS%\evdgt_sbx_%AG%%SD%"
%MV% -u -X utf8 scripts\nyx2_office_eval_v2.py e%AG%%SD% >> %LOG% 2>&1
if errorlevel 1 goto :fail
%MV% -u -X utf8 scripts\security_eval_v21.py e%AG%%SD% >> %LOG% 2>&1
if errorlevel 1 goto :fail
%MV% -u -X utf8 scripts\audit_eval_v1.py e%AG%%SD% >> %LOG% 2>&1
if errorlevel 1 goto :fail
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object {$_.CommandLine -match 'spark_server.py' -and $_.CommandLine -match '8006'} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >> %LOG% 2>&1
exit /b 0

:fail
echo [%date% %time%] EVDGT CHAIN FAILED >> %LOG%
exit /b 1
