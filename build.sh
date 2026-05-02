#!/bin/bash
set -e

# copy proto file into each component
mkdir -p controller/proto storage/proto
cp proto/marketplace.proto controller/proto/marketplace.proto
cp proto/marketplace.proto storage/proto/marketplace.proto

# build images
docker build -t marketplace-storage ./storage
docker build -t marketplace-controller ./controller

echo "done"
