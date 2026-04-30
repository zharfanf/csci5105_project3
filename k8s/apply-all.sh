#!/usr/bin/env bash

kubectl apply -f "k8s/frontend.yaml"
kubectl apply -f "k8s/storage.yaml"
kubectl apply -f "k8s/autoscaler.yaml"
# kubectl apply -f "k8s/storage-service.yaml"
# kubectl apply -f "k8s/storage-statefulset.yaml"
# kubectl apply -f "k8s/frontend-deployment.yaml"
# kubectl apply -f "k8s/frontend-service.yaml"
