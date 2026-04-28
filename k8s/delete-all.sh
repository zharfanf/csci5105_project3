#!/usr/bin/env bash

kubectl delete -f "k8s/storage-service.yaml"
kubectl delete -f "k8s/storage-statefulset.yaml"
kubectl delete -f "k8s/frontend-deployment.yaml"
kubectl delete -f "k8s/frontend-service.yaml"
