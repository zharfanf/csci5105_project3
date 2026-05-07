# How to Run Our Project

## Prerequisites

- Docker Desktop with Kubernetes enabled (Settings → Kubernetes → Enable Kubernetes)
- Kubernetes provisioner: kind (default in Docker Desktop)
- Python 3.11+ with `grpcio` and `grpcio-tools` installed
- `kubectl` configured to use the `docker-desktop` context

## Step 1: Build Docker Images

From the project root:

```bash
./build.sh
```

This builds three images: `marketplace-storage`, `marketplace-frontend`, `marketplace-controller`.

## Step 2: Load Images into Kubernetes

Images must be loaded into the cluster node.

```bash
docker save marketplace-storage:latest -o storage.tar
docker save marketplace-frontend:latest -o frontend.tar
docker save marketplace-controller:latest -o controller.tar

cat storage.tar | docker exec -i desktop-control-plane ctr -n k8s.io images import -
cat frontend.tar | docker exec -i desktop-control-plane ctr -n k8s.io images import -
cat controller.tar | docker exec -i desktop-control-plane ctr -n k8s.io images import -

rm storage.tar frontend.tar controller.tar
```

This step is required every time you need to rebuild an image.

## Step 3: Deploy to Kubernetes

```bash
./k8s/apply-all.sh
```

This deploys (in order): the storage StatefulSet and headless Service, the controller Deployment, the frontend Deployment and LoadBalancer Service, and the HPA.

## Step 4: Verify Deployment

```bash
kubectl get pods
```

Expected output (all Running):

```
controller-xxxxxxx-xxxxx   1/1   Running   0   ...
frontend-xxxxxxx-xxxxx     1/1   Running   0   ...
frontend-xxxxxxx-xxxxx     1/1   Running   0   ...
frontend-xxxxxxx-xxxxx     1/1   Running   0   ...
storage-0                  1/1   Running   0   ...
storage-1                  1/1   Running   0   ...
storage-2                  1/1   Running   0   ...
```

3 frontend pods, 3 storage pods, 1 controller pod.

## Step 5: Metrics Measurement Installation

To obtain the metrics (e.g., cpu and memory utils) for each pod, we recommend using `helm`

```bash
curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-4
chmod 700 get_helm.sh
./get_helm.sh
```

And then add metrics-server to the `kube-system` namespace
```bash
helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server/
helm repo update
helm install metrics-server --namespace kube-system --version 3.11.0 metrics-server/metrics-server --set "args[0]=--kubelet-insecure-tls"
```

After installation, now you can call `kubectl top pods` to obtain metrics utilization
```
(base) zharfanf@zharfanf csci5105_project3 % kubectl top pods
NAME                        CPU(cores)   MEMORY(bytes)   
frontend-xxxxxxxxxx-xxxxx   5m           28Mi            
storage-0                   4m           23Mi            
storage-1                   3m           18Mi            
storage-2                   3m           24Mi  
(base) zharfanf@zharfanf csci5105_project3 % kubectl get hpa
NAME           REFERENCE             TARGETS       MINPODS   MAXPODS   REPLICAS   AGE
frontend-hpa   Deployment/frontend   cpu: 4%/70%   1         5         1          5h37m
```

## Step 6: Port-Forward and Run Client/Eval

We recommend using three terminals for running evals. 

```bash
# Terminal 1: port-forward (keep running)
kubectl port-forward svc/frontend-service 50051:50051
```

```bash
# Terminal 2: run the eval script
export PYTHONPATH=proto/src
python eval.py
```

```bash
# Terminal 3: watch controller logs
kubectl logs -f deployment/controller
```

## Running the Client

```bash
export PYTHONPATH=proto/src
python client.py
```

## Running Our Specific Tests

### Fault Tolerance Test

```bash
chmod +x fault_tolerance_test_v2.sh
./fault_tolerance_test_v2.sh
```

This scales the storage StatefulSet down to 2 replicas, waits for the controller to detect the failure, scales back to 3, and verifies recovery. Results are saved to `test_results/fault_tolerance_<timestamp>/`.

### Autoscaling Test

```bash
chmod +x autoscaling_test.sh
./autoscaling_test.sh
```

This runs 3 concurrent eval instances to drive CPU above the HPA threshold (70%), triggering scale-up from 3 to 5 frontend pods. Results are saved to `test_results/autoscaling_<timestamp>/`.

## Teardown

```bash
./k8s/delete-all.sh
```

## Rebuilding After Code Changes

After modifying any source file:

```bash
# 1. rebuild the changed image(s)
docker build -t marketplace-frontend -f frontend/Dockerfile .
# or marketplace-storage, marketplace-controller

# 2. reload into kubernetes
docker save marketplace-frontend:latest -o frontend.tar
cat frontend.tar | docker exec -i desktop-control-plane ctr -n k8s.io images import -
rm frontend.tar

# 3. restart the affected pods
kubectl rollout restart deployment frontend
# or: kubectl rollout restart deployment controller
# or: kubectl delete pod storage-0 storage-1 storage-2 (for statefulset)
```

## Troubleshooting

**Metrics server not reporting CPU**: The HPA requires a metrics server. Install if missing:

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl patch deployment metrics-server -n kube-system --type='json' \
  -p='[{"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--kubelet-insecure-tls"}]'
```

Verify with `kubectl top pods`.