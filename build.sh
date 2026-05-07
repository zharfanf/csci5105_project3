#!/bin/bash
set -e

# build images
# storage and frontend dockerfiles copy proto/ from repo root, so build context is .
docker build -t marketplace-storage -f storage/Dockerfile .
docker build -t marketplace-frontend -f frontend/Dockerfile .
docker build -t marketplace-controller -f controller/Dockerfile .

echo "done"