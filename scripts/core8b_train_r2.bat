@echo off
rem Core 8B SFT re-run on the local 5090 (RunPod outage). Checkpoints to shinobi disk.
rem Usage: core8b_train_r2.bat [smoke]
cd /d C:\Users\User\synapsek-closedloop
setlocal
set PYTHONIOENCODING=utf-8
set PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
set CORE8B_OUT=C:\Users\User\synapsek-closedloop\runs\node\shinobi-1\core8b_runs_r2
set CORE8B_DATA=C:\Users\User\synapsek-closedloop\runs\node\shinobi-1\core8b_data
set CORE8B_BASE=C:\Users\User\hf_models\qwen3-8b-normal
if "%1"=="smoke" set CORE8B_SMOKE=5
C:\Users\User\synapsek-closedloop\.venv\Scripts\python.exe -u -X utf8 scripts\core8b_train.py >> C:\Users\User\synapsek-closedloop\runs\node\shinobi-1\core8b_r2\train.log 2>&1
echo EXITCODE %errorlevel%
