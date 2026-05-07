#!/bin/bash
# autoscaling_test.sh
# generates heavy load to trigger HPA and captures scaling behavior
# usage: ./autoscaling_test.sh

set -e

RESULTS_DIR="test_results/autoscaling_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RESULTS_DIR"

echo "=== autoscaling test ==="
echo "results will be saved to $RESULTS_DIR"

# make sure port-forward is running
echo "starting port-forward..."
kubectl port-forward svc/frontend-service 50051:50051 > "$RESULTS_DIR/port_forward.log" 2>&1 &
PF_PID=$!
sleep 2

if ! kill -0 $PF_PID 2>/dev/null; then
    echo "ERROR: port-forward failed"
    exit 1
fi

# snapshot initial state
echo "--- initial state ---"
kubectl get pods -o wide | tee "$RESULTS_DIR/pods_initial.txt"
kubectl get hpa | tee "$RESULTS_DIR/hpa_initial.txt"

# start watching HPA in background
echo ""
echo "watching HPA..."
kubectl get hpa -w > "$RESULTS_DIR/hpa_log.txt" 2>&1 &
HPA_PID=$!

# start watching pods in background
kubectl get pods -w > "$RESULTS_DIR/pods_log.txt" 2>&1 &
PODS_PID=$!

# run multiple eval instances in parallel to generate load
echo "starting 3 parallel eval instances to generate load..."
export PYTHONPATH=proto/src

python eval.py > "$RESULTS_DIR/eval_1.txt" 2>&1 &
E1_PID=$!
python eval.py > "$RESULTS_DIR/eval_2.txt" 2>&1 &
E2_PID=$!
python eval.py > "$RESULTS_DIR/eval_3.txt" 2>&1 &
E3_PID=$!

echo "eval instances running (PIDs: $E1_PID $E2_PID $E3_PID)"
echo "waiting for them to finish..."

# periodically log HPA status while evals run
for i in $(seq 1 12); do
    sleep 10
    echo "--- HPA status at +${i}0s ---" | tee -a "$RESULTS_DIR/hpa_snapshots.txt"
    kubectl get hpa | tee -a "$RESULTS_DIR/hpa_snapshots.txt"
    echo "--- pods at +${i}0s ---" | tee -a "$RESULTS_DIR/hpa_snapshots.txt"
    kubectl get pods | tee -a "$RESULTS_DIR/hpa_snapshots.txt"
    echo "" | tee -a "$RESULTS_DIR/hpa_snapshots.txt"
done

# wait for evals to finish
wait $E1_PID 2>/dev/null || true
wait $E2_PID 2>/dev/null || true
wait $E3_PID 2>/dev/null || true

echo ""
echo "evals complete. waiting 60s to see if HPA scales down..."
sleep 60

# final state
echo "--- final state ---"
kubectl get pods -o wide | tee "$RESULTS_DIR/pods_final.txt"
kubectl get hpa | tee "$RESULTS_DIR/hpa_final.txt"

# stop background watchers
kill $HPA_PID 2>/dev/null || true
kill $PODS_PID 2>/dev/null || true
kill $PF_PID 2>/dev/null || true

# print summary
echo ""
echo "=== test complete ==="
echo ""
echo "--- eval 1 summary ---"
tail -20 "$RESULTS_DIR/eval_1.txt"
echo ""
echo "--- HPA timeline ---"
cat "$RESULTS_DIR/hpa_snapshots.txt"
echo ""
echo "all results saved to $RESULTS_DIR/"
echo "  eval_1/2/3.txt       - eval results from each instance"
echo "  hpa_log.txt          - continuous HPA watch log"
echo "  hpa_snapshots.txt    - periodic HPA + pod snapshots"
echo "  pods_log.txt         - continuous pod watch log"
echo "  pods_initial.txt     - pods before load"
echo "  pods_final.txt       - pods after cooldown"
