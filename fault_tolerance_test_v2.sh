#!/bin/bash
# fault_tolerance_test_v2.sh
# scales down a storage replica so controller detects failure,
# then scales back up and captures recovery logs
# usage: ./fault_tolerance_test_v2.sh

set -e

RESULTS_DIR="test_results/fault_tolerance_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RESULTS_DIR"

echo "=== fault tolerance test v2 ==="
echo "results will be saved to $RESULTS_DIR"

# snapshot before
echo ""
echo "--- pods before test ---"
kubectl get pods -o wide | tee "$RESULTS_DIR/pods_before.txt"

# start capturing controller logs
kubectl logs -f deployment/controller > "$RESULTS_DIR/controller_logs.txt" 2>&1 &
CTRL_PID=$!

echo ""
echo ">>> SCALING STORAGE DOWN TO 2 REPLICAS (removing storage-2) <<<"
echo "scaled down at $(date)" | tee "$RESULTS_DIR/timeline.txt"
kubectl scale statefulset storage --replicas=2

echo "waiting 25 seconds for controller to detect failure..."
sleep 25

echo ""
echo "--- controller logs after failure detection ---"
kubectl logs deployment/controller | tail -15 | tee "$RESULTS_DIR/failure_detection.txt"

echo ""
echo "--- pods during outage ---"
kubectl get pods -o wide | tee "$RESULTS_DIR/pods_during_outage.txt"

echo ""
echo ">>> SCALING STORAGE BACK TO 3 REPLICAS <<<"
echo "scaled back up at $(date)" | tee -a "$RESULTS_DIR/timeline.txt"
kubectl scale statefulset storage --replicas=3

echo "waiting 25 seconds for pod to restart and controller to sync..."
sleep 25

echo ""
echo "--- controller logs after recovery ---"
kubectl logs deployment/controller | tail -20 | tee "$RESULTS_DIR/recovery_logs.txt"

echo ""
echo "--- pods after recovery ---"
kubectl get pods -o wide | tee "$RESULTS_DIR/pods_after.txt"

# also run a quick eval to prove system still works after recovery
echo ""
echo ">>> RUNNING EVAL TO VERIFY SYSTEM WORKS POST-RECOVERY <<<"

# start port forward
kubectl port-forward svc/frontend-service 50051:50051 > "$RESULTS_DIR/port_forward.log" 2>&1 &
PF_PID=$!
sleep 2

export PYTHONPATH=proto/src
python eval.py > "$RESULTS_DIR/eval_post_recovery.txt" 2>&1
echo "eval complete"

# print eval summary
echo ""
echo "--- post-recovery eval summary ---"
grep -A2 "totals:" "$RESULTS_DIR/eval_post_recovery.txt" | tee -a "$RESULTS_DIR/summary.txt"
grep "scenario\|consistent\|bids:" "$RESULTS_DIR/eval_post_recovery.txt" | tee -a "$RESULTS_DIR/summary.txt"

# cleanup
kill $CTRL_PID 2>/dev/null || true
kill $PF_PID 2>/dev/null || true

echo ""
echo "=== test complete ==="
echo ""
echo "--- full controller log ---"
cat "$RESULTS_DIR/controller_logs.txt"
echo ""
echo "--- timeline ---"
cat "$RESULTS_DIR/timeline.txt"
echo ""
echo "all results saved to $RESULTS_DIR/"
echo "  controller_logs.txt    - full controller log with failure + recovery"
echo "  failure_detection.txt  - controller output when replica died"
echo "  recovery_logs.txt      - controller output after replica recovered"
echo "  pods_before.txt        - pods before test"
echo "  pods_during_outage.txt - pods while replica was down"
echo "  pods_after.txt         - pods after recovery"
echo "  eval_post_recovery.txt - full eval after recovery"
echo "  timeline.txt           - timestamps of scale down/up"
