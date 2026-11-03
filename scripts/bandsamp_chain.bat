@echo off
rem BANDSAMP kill-test chain (pre-registration d8a0ec7). One shot, aborts on error.
rem probe (pass@k, spark-venv) -> 6x train -> 6x merge -> serve+eval each on :8005 -> verdict.
cd /d C:\Users\User\synapsek-closedloop
git pull -q
set RUNS=C:\Users\User\synapsek-closedloop\runs\node\shinobi-1
set LOG=%RUNS%\bandsamp_chain_log.txt
set SPV=C:\Users\User\spark-venv\Scripts\python.exe
set MV=C:\Users\User\synapsek-closedloop\.venv\Scripts\python.exe
set PYTHONIOENCODING=utf-8
echo [%date% %time%] BANDSAMP CHAIN START >> %LOG%

%SPV% -u -X utf8 scripts\bandsamp_probe.py 1000 >> %LOG% 2>&1
if errorlevel 1 goto :fail

for %%A in (A B) do for %%S in (1 2 3) do (
  echo [%date% %time%] TRAIN %%A seed %%S >> %LOG%
  %SPV% -u -X utf8 scripts\bandsamp_train.py %%A %%S >> %LOG% 2>&1
  if errorlevel 1 goto :fail
)
for %%A in (A B) do for %%S in (1 2 3) do (
  echo [%date% %time%] MERGE %%A seed %%S >> %LOG%
  %SPV% -u -X utf8 scripts\bandsamp_merge.py %%A %%S >> %LOG% 2>&1
  if errorlevel 1 goto :fail
)

set NYX_BASE_URL=http://127.0.0.1:8005/v1/chat/completions
for %%A in (A B) do for %%S in (1 2 3) do (
  echo [%date% %time%] EVAL %%A seed %%S >> %LOG%
  powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object {$_.CommandLine -match 'spark_server.py' -and $_.CommandLine -match '8005'} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >> %LOG% 2>&1
  start "bssrv" /b %SPV% -u scripts\spark_server.py C:\Users\User\hf_models\bandsamp_%%A_s%%S 8005 >> %LOG% 2>&1
  powershell -NoProfile -Command "$t=0; while(-not (Test-NetConnection 127.0.0.1 -Port 8005 -WarningAction SilentlyContinue).TcpTestSucceeded -and $t -lt 600){Start-Sleep 10; $t+=10}" >> %LOG% 2>&1
  set NYX_SANDBOX=%RUNS%\bandsamp_sbx_%%A%%S
  %MV% -u -X utf8 scripts\nyx2_office_eval_v2.py bs%%A%%S >> %LOG% 2>&1
  %MV% -u -X utf8 scripts\security_eval_v21.py bs%%A%%S >> %LOG% 2>&1
  %MV% -u -X utf8 scripts\audit_eval_v1.py bs%%A%%S >> %LOG% 2>&1
  powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object {$_.CommandLine -match 'spark_server.py' -and $_.CommandLine -match '8005'} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >> %LOG% 2>&1
)

%MV% -u -X utf8 scripts\bandsamp_eval.py >> %LOG% 2>&1
echo [%date% %time%] BANDSAMP CHAIN DONE >> %LOG%
type %RUNS%\bandsamp_verdict.json >> %LOG%
exit /b 0

:fail
echo [%date% %time%] BANDSAMP CHAIN FAILED >> %LOG%
exit /b 1