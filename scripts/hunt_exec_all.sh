#!/bin/bash
# Run one exec process per engine, in parallel. Usage: scripts/hunt_exec_all.sh OUTDIR PY
OUT=$1; PY=$2
for spec in duckdb mysql:32770:mysql-8.0.46 mysql:32768:mysql-8.4.13 mysql:13406:mysql-9.4.0 mysql:32772:mysql-9.7.2 mysql:13407:mysql-26.7.0; do
  n=$(echo $spec | tr ':' '_')
  nohup $PY scripts/hunt.py exec $OUT $spec > $OUT/exec_$n.log 2>&1 &
done
