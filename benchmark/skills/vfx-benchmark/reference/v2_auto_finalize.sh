#!/bin/bash
# Auto-finalize: wait for v2 sample run, then generate report.
# Run this in foreground after starting run_v2_samples.py in background.

set -e

RUN_PID_FILE=${RUN_PID_FILE:-/tmp/v2_run_16.pid}
LOG_FILE=${LOG_FILE:-/tmp/v2_run_16.log}
# 定位 repo root：本脚本位于 <repo>/benchmark/skills/vfx-benchmark/reference/
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../../../.." && pwd)
BACKEND=$REPO_ROOT/backend
BENCHMARK=$REPO_ROOT/benchmark

echo "[finalize] Watching for run_v2_samples.py completion..."

# Wait for python run_v2_samples process to exit
while pgrep -f "python.*run_v2_samples" > /dev/null; do
    sleep 30
    COUNT=$(ls /tmp/vfx_v2_runs/ 2>/dev/null | grep -v summary.json | wc -l | tr -d ' ')
    echo "[finalize] $(date +%H:%M:%S) Still running. $COUNT sample dirs exist."
done

echo "[finalize] ✅ Run completed at $(date)"
echo ""
echo "=== Final log tail ==="
tail -30 $LOG_FILE
echo ""

# Wait a few seconds for files to flush
sleep 5

# Collect results
echo ""
echo "[finalize] Collecting results..."
cd $BENCHMARK/skills/vfx-benchmark/reference
python collect_v2_results.py --output /tmp/v2_report_data.json

# Generate report
echo ""
echo "[finalize] Generating HTML report..."
REPORT_DIR=$BENCHMARK/test_results/$(date +%Y-%m-%d)_v2-codex-od-19samples
mkdir -p $REPORT_DIR
python generate_v2_report.py \
    --input /tmp/v2_report_data.json \
    --output $REPORT_DIR/index.html

# Also copy summary.json
cp /tmp/vfx_v2_runs/summary.json $REPORT_DIR/test_results.json 2>/dev/null || true

# Print summary
echo ""
echo "[finalize] ===== FINAL SUMMARY ====="
python3 -c "
import json
data = json.load(open('/tmp/v2_report_data.json'))
s = data['summary']
print(f'Samples run:    {s[\"present\"]} / {s[\"total_samples\"]}')
print(f'Passed (≥0.85): {s[\"passed\"]} / {s[\"present\"]}')
print(f'v2.0 avg score: {s[\"v2_avg_score\"]:.3f}')
print(f'v1.0 baseline:  {s[\"v1_avg_score\"]:.3f}')
print(f'Delta:          {s[\"delta_avg\"]:+.3f}')
"

echo ""
echo "[finalize] 📄 Report: $REPORT_DIR/index.html"
echo "[finalize] Open with: open $REPORT_DIR/index.html"
