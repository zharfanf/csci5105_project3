"""
Storage replica node for the marketplace.
Uses quorum replication - all replicas are peers, no primary/backup.
Service pods handle the quorum logic (fan out, wait for W acks, etc).
This just stores items and accepts reads/writes.
"""

import os
import sys
import time
import uuid
import threading
import logging
from concurrent import futures

import grpc
import marketplace_pb2 as pb2
import marketplace_pb2_grpc as pb2_grpc

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("replica")


class StorageState:
    """thread safe storage for items"""
    def __init__(self):
        self._lock = threading.RLock()
        self._items = {} # item_id -> dict
        self._global_version = 0

    def get(self, item_id):
        with self._lock:
            item = self._items.get(item_id)
            if item:
                return dict(item)
            return None

    def put(self, item_dict):
        with self._lock:
            self._items[item_dict["item_id"]] = dict(item_dict)
            v = item_dict.get("version", 0)
            if v > self._global_version:
                self._global_version = v

    def get_version(self, item_id):
        with self._lock:
            item = self._items.get(item_id)
            if item:
                return item["version"]
            return 0

    def search(self, keyword="", category=""):
        with self._lock:
            results = []
            for item in self._items.values():
                # check keyword match
                kw_match = True
                if keyword:
                    kw_match = (keyword.lower() in item.get("title", "").lower() or
                               keyword.lower() in item.get("description", "").lower())
                # check category match
                cat_match = True
                if category:
                    cat_match = category.lower() == item.get("category", "").lower()

                if kw_match and cat_match:
                    results.append(dict(item))
            return results

    def get_all(self):
        with self._lock:
            return [dict(v) for v in self._items.values()]

    def item_count(self):
        with self._lock:
            return len(self._items)

    @property
    def latest_version(self):
        with self._lock:
            return self._global_version


# helper functions for converting between dicts and protobuf messages
def to_proto(d):
    return pb2.Item(
        item_id=d.get("item_id", ""),
        seller_id=d.get("seller_id", ""),
        title=d.get("title", ""),
        category=d.get("category", ""),
        description=d.get("description", ""),
        starting_price=d.get("starting_price", 0.0),
        current_price=d.get("current_price", 0.0),
        quantity=d.get("quantity", 0),
        status=d.get("status", "active"),
        version=d.get("version", 0),
    )

def from_proto(item_pb):
    return {
        "item_id": item_pb.item_id,
        "seller_id": item_pb.seller_id,
        "title": item_pb.title,
        "category": item_pb.category,
        "description": item_pb.description,
        "starting_price": item_pb.starting_price,
        "current_price": item_pb.current_price,
        "quantity": item_pb.quantity,
        "status": item_pb.status,
        "version": item_pb.version,
    }


class StorageServiceServicer(pb2_grpc.StorageServiceServicer):

    def __init__(self, replica_id):
        self.replica_id = replica_id
        self.state = StorageState()
        logger.info(f"replica {self.replica_id} started")

    def Write(self, request, context):
        op = request.operation
        item_dict = from_proto(request.item)
        version = request.proposed_version

        if op == "create":
            # new item, just store it
            item_dict["version"] = version
            if not item_dict.get("current_price"):
                item_dict["current_price"] = item_dict["starting_price"]
            self.state.put(item_dict)

            logger.info(f"[{self.replica_id}] created {item_dict['item_id']} v{version}")
            return pb2.StorageWriteResponse(
                success=True,
                item=to_proto(item_dict),
                message="created",
                current_version=version
            )

        elif op == "update":
            existing = self.state.get(item_dict["item_id"])
            if not existing:
                return pb2.StorageWriteResponse(success=False, message="item not found", current_version=0)

            # optimistic concurrency - check version
            if request.item.version > 0 and existing["version"] != request.item.version:
                return pb2.StorageWriteResponse(
                    success=False,
                    message=f"version conflict: expected {request.item.version} but got {existing['version']}",
                    current_version=existing["version"]
                )

            # merge fields that were actually set
            if item_dict["description"]:
                existing["description"] = item_dict["description"]
            if item_dict["quantity"] > 0:
                existing["quantity"] = item_dict["quantity"]
            if item_dict["status"]:
                existing["status"] = item_dict["status"]
            if item_dict["current_price"] > 0:
                existing["current_price"] = item_dict["current_price"]
            existing["version"] = existing["version"] + 1

            self.state.put(existing)
            logger.info(f"[{self.replica_id}] updated {existing['item_id']} v{existing['version']}")
            return pb2.StorageWriteResponse(
                success=True,
                item=to_proto(existing),
                message="updated",
                current_version=existing["version"]
            )

        elif op == "bid":
            existing = self.state.get(item_dict["item_id"])
            if not existing:
                return pb2.StorageWriteResponse(success=False, message="item not found", current_version=0)

            if existing["status"] != "auction":
                return pb2.StorageWriteResponse(
                    success=False,
                    message="item is not in auction mode",
                    current_version=existing["version"]
                )

            if item_dict["current_price"] <= existing["current_price"]:
                return pb2.StorageWriteResponse(
                    success=False,
                    message=f"bid too low, current price is {existing['current_price']}",
                    current_version=existing["version"]
                )

            # accept the bid
            existing["current_price"] = item_dict["current_price"]
            existing["version"] = existing["version"] + 1
            self.state.put(existing)

            logger.info(f"[{self.replica_id}] bid on {existing['item_id']}: ${item_dict['current_price']:.2f} v{existing['version']}")
            return pb2.StorageWriteResponse(
                success=True,
                item=to_proto(existing),
                message="bid accepted",
                current_version=existing["version"]
            )
        else:
            return pb2.StorageWriteResponse(success=False, message=f"unknown op: {op}", current_version=0)

    def Read(self, request, context):
        item = self.state.get(request.item_id)
        if item is None:
            return pb2.StorageReadResponse(success=False, message="not found")
        return pb2.StorageReadResponse(success=True, item=to_proto(item))

    def Search(self, request, context):
        results = self.state.search(keyword=request.keyword, category=request.category)
        return pb2.StorageSearchResponse(success=True, items=[to_proto(r) for r in results])

    def Repair(self, request, context):
        """read repair - accept a newer version of an item from a service pod"""
        incoming = from_proto(request.item)
        existing = self.state.get(incoming["item_id"])

        if existing is None or incoming["version"] > existing["version"]:
            self.state.put(incoming)
            logger.info(f"[{self.replica_id}] repaired {incoming['item_id']} to v{incoming['version']}")
            return pb2.RepairResponse(success=True, message="repaired")
        return pb2.RepairResponse(success=True, message="already up to date")

    def SyncState(self, request, context):
        """dump all items for a recovering replica"""
        items = self.state.get_all()
        logger.info(f"[{self.replica_id}] sync requested by {request.replica_id}, sending {len(items)} items")
        return pb2.SyncResponse(
            items=[to_proto(i) for i in items],
            latest_version=self.state.latest_version
        )

    def CheckHealth(self, request, context):
        return pb2.ReplicaHeartbeatResponse(
            replica_id=self.replica_id,
            item_count=self.state.item_count(),
            latest_version=self.state.latest_version,
            healthy=True
        )


def serve():
    replica_id = os.environ.get("POD_NAME", "replica-unknown")
    port = os.environ.get("PORT", "50052")

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    pb2_grpc.add_StorageServiceServicer_to_server(
        StorageServiceServicer(replica_id), server
    )
    server.add_insecure_port(f"0.0.0.0:{port}")
    server.start()
    logger.info(f"replica {replica_id} listening on port {port}")

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == "__main__":
    serve()