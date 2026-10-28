#!/bin/bash
# Two-node SWAP loop test on shinobi: export shinobi-1 -> import shinobi-2.
# Launched via schtasks (detached). Log: runs/node/swap_loop_log.txt
ssh shinobi "schtasks /create /tn swaploop /tr \"cmd /c cd /d C:\Users\User\synapsek-closedloop && .venv\Scripts\python.exe -u -m src.node.swarm --node shinobi-1 --export pot-20261029 && .venv\Scripts\python.exe -u -m src.node.swarm --node shinobi-2 --import swarm_registry\shinobi-1\pot-20261029\manifest.json --as-node shinobi-2 > runs\node\swap_loop_log.txt 2>&1\" /sc once /st 00:00 /f && schtasks /run /tn swaploop && echo TASK-RUN"