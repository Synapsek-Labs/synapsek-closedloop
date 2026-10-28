#!/bin/bash
# Launch PoT node collect+train on shinobi (background via hermes terminal tool)
ssh shinobi "cd C:\Users\User\synapsek-closedloop && set PYTHONUNBUFFERED=1&& .venv\Scripts\python.exe -u -m src.node.pot_node --node shinobi-1 2>&1"
