#!/bin/bash
# v2 gate: detached via schtasks on shinobi, delta dir passed as arg.
# Usage: bash scripts/pot_gate_replay.sh   (gates runs/node/shinobi-1/delta_replay)
ssh shinobi "schtasks /create /tn potgate /tr \"cmd /c cd /d C:\Users\User\synapsek-closedloop && .venv\Scripts\python.exe -u -m src.node.pot_node --node shinobi-1 --gate-only --delta delta_replay > runs\node\shinobi-1\gate_log.txt 2>&1\" /sc once /st 00:00 /f && schtasks /run /tn potgate && echo TASK-RUN"