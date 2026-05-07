"""
Controller for the marketplace system.
Monitors storage replicas and handles failure detection + recovery.
Doesn't handle any client traffic - service pods do that.
"""

import os
import time
import threading
import logging
from concurrent import futures

import grpc
import marketplace_pb2 as pb2
import marketplace_pb2_grpc as pb2_grpc

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("controller")


class ClusterState:
    """keeps track of which replicas are alive"""

    def __init__(self):
        self._lock = threading.RLock()
        self.all_replicas = []
        self.healthy_replicas = set()
        self.replica_health = {} # addr -> {last_seen, healthy}

    def set_replicas(self, addrs):
        with self._lock:
            self.all_replicas = list(addrs)
            for addr in addrs:
                if addr not in self.replica_health:
                    self.replica_health[addr] = {"last_seen": time.time(), "healthy": True}
                    self.healthy_replicas.add(addr)

    def mark_healthy(self, addr):
        with self._lock:
            self.replica_health[addr] = {"last_seen": time.time(), "healthy": True}
            self.healthy_replicas.add(addr)

    def mark_unhealthy(self, addr):
        with self._lock:
            if addr in self.replica_health:
                self.replica_health[addr]["healthy"] = False
            self.healthy_replicas.discard(addr)

    def get_healthy(self):
        with self._lock:
            return list(self.healthy_replicas)

    def get_all(self):
        with self._lock:
            return list(self.all_replicas)

    def is_healthy(self, addr):
        with self._lock:
            return addr in self.healthy_replicas

    def healthy_count(self):
        with self._lock:
            return len(self.healthy_replicas)


class HealthMonitor:
    """background thread that heartbeats replicas and handles failures"""

    def __init__(self, cluster, interval=5, threshold=3):
        self.cluster = cluster
        self.interval = interval
        self.threshold = threshold
        self._stop = threading.Event()
        self._miss_counts = {}
        self._recovering = set() # dont try to recover same replica twice at once

    def start(self):
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()
        logger.info(f"health monitor started (interval={self.interval}s, threshold={self.threshold})")

    def stop(self):
        self._stop.set()

    def _loop(self):
        # wait a bit for replicas to boot up
        self._stop.wait(10)

        while not self._stop.is_set():
            for addr in self.cluster.get_all():
                self._check(addr)
            self._stop.wait(self.interval)

    def _check(self, addr):
        try:
            channel = grpc.insecure_channel(addr)
            stub = pb2_grpc.StorageServiceStub(channel)
            resp = stub.CheckHealth(
                pb2.ReplicaHeartbeatRequest(controller_id="controller"),
                timeout=3.0
            )
            channel.close()

            was_dead = not self.cluster.is_healthy(addr)
            self.cluster.mark_healthy(addr)
            self._miss_counts[addr] = 0

            # replica just came back online - need to sync it
            if was_dead and addr not in self._recovering:
                logger.info(f"{addr} is back online, starting recovery")
                self._recover(addr)

        except grpc.RpcError:
            misses = self._miss_counts.get(addr, 0) + 1
            self._miss_counts[addr] = misses

            if misses >= self.threshold:
                if self.cluster.is_healthy(addr):
                    logger.error(f"FAILURE: {addr} missed {misses} heartbeats, marking dead")
                    self.cluster.mark_unhealthy(addr)

                    healthy = self.cluster.get_healthy()
                    logger.info(f"healthy replicas: {healthy} ({len(healthy)}/{len(self.cluster.get_all())})")

                    # if we have less than W=2 replicas we cant do writes anymore
                    if self.cluster.healthy_count() < 2:
                        logger.critical("LESS THAN 2 REPLICAS HEALTHY - WRITES WILL FAIL")
            else:
                logger.warning(f"heartbeat failed for {addr} ({misses}/{self.threshold})")

    def _recover(self, recovering_addr):
        """sync state from a healthy replica to the one that just came back"""
        self._recovering.add(recovering_addr)

        try:
            # find a healthy replica to copy from
            healthy = [a for a in self.cluster.get_healthy() if a != recovering_addr]
            if not healthy:
                logger.error(f"no healthy replicas to sync from for {recovering_addr}")
                return

            source = healthy[0]
            logger.info(f"syncing {recovering_addr} from {source}")

            # get all items from source replica
            src_channel = grpc.insecure_channel(source)
            src_stub = pb2_grpc.StorageServiceStub(src_channel)
            sync_resp = src_stub.SyncState(
                pb2.SyncRequest(replica_id=recovering_addr, last_known_version=0),
                timeout=30.0
            )
            src_channel.close()

            # push items to recovering replica using repair
            tgt_channel = grpc.insecure_channel(recovering_addr)
            tgt_stub = pb2_grpc.StorageServiceStub(tgt_channel)

            count = 0
            for item in sync_resp.items:
                try:
                    tgt_stub.Repair(pb2.RepairRequest(item=item), timeout=5.0)
                    count += 1
                except grpc.RpcError as e:
                    logger.warning(f"failed to repair item {item.item_id}: {e}")

            tgt_channel.close()
            logger.info(f"recovery done: synced {count}/{len(sync_resp.items)} items to {recovering_addr}")

        except grpc.RpcError as e:
            logger.error(f"recovery failed for {recovering_addr}: {e}")
        finally:
            self._recovering.discard(recovering_addr)


def main():
    port = os.environ.get("CONTROLLER_PORT", "50050")

    # get replica addresses from env
    replica_addrs = os.environ.get(
        "REPLICA_ADDRESSES",
        "storage-0.storage:50052,storage-1.storage:50052,storage-2.storage:50052"
    ).split(",")
    replica_addrs = [a.strip() for a in replica_addrs if a.strip()]

    cluster = ClusterState()
    cluster.set_replicas(replica_addrs)
    logger.info(f"controller managing replicas: {replica_addrs}")

    # start monitoring
    monitor = HealthMonitor(
        cluster,
        interval=int(os.environ.get("HEARTBEAT_INTERVAL", 5)),
        threshold=int(os.environ.get("FAILURE_THRESHOLD", 3))
    )
    monitor.start()

    logger.info("controller running")

    # just keep running and log status periodically
    try:
        while True:
            time.sleep(10)
            healthy = cluster.get_healthy()
            logger.info(f"status: {len(healthy)}/{len(cluster.get_all())} replicas healthy - {healthy}")
    except KeyboardInterrupt:
        monitor.stop()
        logger.info("shutting down")


if __name__ == "__main__":
    main()