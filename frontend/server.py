import hashlib
import os
import time
from concurrent import futures

import grpc

import marketplace_pb2
import marketplace_pb2_grpc

import random

POD_NAME = os.environ.get("POD_NAME", "frontend")
PORT = os.environ.get("PORT", "50051")
STORAGE_PORT = os.environ.get("STORAGE_PORT", "50052")
STORAGE_TARGETS = [
    f"storage-0.storage:{STORAGE_PORT}",
    f"storage-1.storage:{STORAGE_PORT}",
    f"storage-2.storage:{STORAGE_PORT}",
]
STORAGE_COUNT = 3
WRITE_QUORUM = (STORAGE_COUNT // 2) + 1
READ_QUORUM = (STORAGE_COUNT // 2) + 1


# def storage_target(key: str) -> str:
#     n = int(hashlib.md5(key.encode()).hexdigest(), 16)
#     return STORAGE_TARGETS[n % len(STORAGE_TARGETS)]


class Frontend(marketplace_pb2_grpc.FrontendServiceServicer):
    # ASSUME THERE IS ONLY 1 MACHINE AT THE MOMENT
    def __init__(self):
        # Maybe hashing the item_id wouldn't be a bad idea
        self.self.ITEM_ID = 0
    
    def submit_task(self, task, quorum, timeout=2.0, **kwargs):
        successes = []
        failures = []
        submitted = {}

        with futures.ThreadPoolExecutor(max_workers=STORAGE_COUNT) as executor:
            for target in STORAGE_TARGETS:
                submitted[executor.submit(task, target, **kwargs)] = target

            try:
                for future in futures.as_completed(submitted, timeout=timeout):
                    target = submitted[future]
                    try:
                        response = future.result()
                        if response.success:
                            successes.append(response)
                        else:
                            failures.append(response)
                            print(f"{POD_NAME} replica {target} returned failure: {response.message}", flush=True)
                    except Exception as exc:
                        print(f"{POD_NAME} task failed on {target}: {exc}", flush=True)

                    if len(successes) >= quorum:
                        break
            except TimeoutError:
                pass

        # return successful responses if quorum met, otherwise return failures for error reporting
        if len(successes) >= quorum:
            return successes
        return failures

    
    def CreateItem_helper(self, target, item):
        with grpc.insecure_channel(target) as channel:
            stub = marketplace_pb2_grpc.StorageServiceStub(channel)
            response = stub.Write(marketplace_pb2.StorageWriteRequest(
                item=item, operation="create", proposed_version=1))
            
            return response

    def CreateItem(self, request, context):
        requestItem = marketplace_pb2.Item(
            item_id=f"{self.ITEM_ID}",
            seller_id=request.seller_id,
            title=request.title,
            category=request.category,
            description=request.description,
            starting_price=request.starting_price,
            current_price=request.starting_price,
            quantity=request.quantity,
            status=request.status,
            version=1,
        )

        response = self.submit_task(self.CreateItem_helper, quorum=WRITE_QUORUM, item=requestItem)
         # handle all fails or not reach quorum
        if not response or not response[0].success:
            # failures or write quorum not reached
            return marketplace_pb2.CreateItemResponse(
                success=False,
                item_id="",
                message="write quorum not reached",
            )

        # increment the ITEM_ID
        self.ITEM_ID += 1

        return marketplace_pb2.CreateItemResponse(
            success=response[0].success, 
            item_id=response[0].item.item_id, 
            message=response[0].message)


    def GetItem_helper(self, target, item_id):
        with grpc.insecure_channel(target) as channel:
            stub = marketplace_pb2_grpc.StorageServiceStub(channel)
            response = stub.Read(marketplace_pb2.StorageReadRequest(item_id=item_id))

            return response
        
    def GetItem(self, request, context):
        response = self.submit_task(self.GetItem_helper, quorum=READ_QUORUM, item_id=request.item_id)
        success_reads = [r for r in response if r.success]

        if len(success_reads) < READ_QUORUM:
            return marketplace_pb2.GetItemResponse(
                success=False,
                message="read quorum not reached or item not found",
            )

        # check if the version numbers are consistent
        latest = max(success_reads, key=lambda r: r.item.version)

        versions = {response.item.version for response in success_reads}
        if len(versions) != 1:
            # repair all replicas
            self.submit_task(self.RepairItem, quorum=1, item=latest.item)

        return marketplace_pb2.GetItemResponse(
            success=True,
            item=latest.item,
            message=latest.message)
    
    
    def SearchItems_helper(self, target, keyword, category):
        with grpc.insecure_channel(target) as channel:
            stub = marketplace_pb2_grpc.StorageServiceStub(channel)
            response = stub.Search(marketplace_pb2.StorageSearchRequest(
                keyword=keyword,
                category=category
            ))

            return response
        
    def SearchItems(self, request, context):
        response = self.submit_task(
            self.SearchItems_helper,
            quorum=READ_QUORUM,
            keyword=request.keyword,
            category=request.category,
        )

        # handle all fails or not reach quorum
        if not response or not response[0].success:
            return marketplace_pb2.SearchItemsResponse(success=False, items=[], message="read quorum not reached")

        print(f"{POD_NAME} SEARCHED -> {STORAGE_TARGETS}", flush=True)
        return marketplace_pb2.SearchItemsResponse(
            success=response[0].success,
            items=response[0].items,
            message="ok")
    
    
    def UpdateItem_helper(self, target, item, proposed_version):
        with grpc.insecure_channel(target) as channel:
            stub = marketplace_pb2_grpc.StorageServiceStub(channel)
            response = stub.Write(marketplace_pb2.StorageWriteRequest(
                item=item, operation="update", proposed_version=proposed_version))
            
            return response
        
    def UpdateItem(self, request, context):
        requestItem = marketplace_pb2.Item(
            item_id=request.item_id,
            seller_id="",
            title="",
            category="",
            description=request.description,
            starting_price=0.0,
            current_price=request.current_price,
            quantity=request.quantity,
            status=request.status,
            version=request.expected_version,
        )

        response = self.submit_task(
            self.UpdateItem_helper,
            quorum=WRITE_QUORUM,
            item=requestItem,
            proposed_version=request.expected_version + 1,
        )

         # handle all fails or not reach quorum
        if not response or not response[0].success:
            return marketplace_pb2.UpdateItemResponse(
                success=False,
                message="write quorum not reached",
            )
        
        print(f"{POD_NAME} UPDATED ITEM -> {STORAGE_TARGETS}", flush=True)
        return marketplace_pb2.UpdateItemResponse(
            success=response[0].success, 
            item=response[0].item, 
            message=response[0].message)
    
    
    def PlaceBid_helper(self, target, item):
        with grpc.insecure_channel(target) as channel:
            stub = marketplace_pb2_grpc.StorageServiceStub(channel)
            response = stub.Write(marketplace_pb2.StorageWriteRequest(
                item=item, operation="bid", proposed_version=1))
            
            return response
    
    def PlaceBid(self, request, context):
        requestItem = marketplace_pb2.Item(
            item_id=request.item_id,
            current_price=request.bid_amount,
            seller_id="",
            title="",
            category="",
            description="",
            starting_price=0.0,
            quantity=0,
            status="",
            version=0,
        )

        response = self.submit_task(self.PlaceBid_helper, quorum=WRITE_QUORUM, item=requestItem)

         # handle all fails or not reach quorum
        if not response or not response[0].success:
            return marketplace_pb2.PlaceBidResponse(
                success=False,
                current_price=0.0,
                message="write quorum not reached",
            )
        
        print(f"{POD_NAME} PLACED A BID -> {STORAGE_TARGETS}", flush=True)
        return marketplace_pb2.PlaceBidResponse(
            success=response[0].success, 
            current_price=response[0].item.current_price,
            message=response[0].message)
    
    def RepairItem(self, target, item):
        with grpc.insecure_channel(target) as channel:
            stub = marketplace_pb2_grpc.StorageServiceStub(channel)
            response = stub.Repair(marketplace_pb2.RepairRequest(item=item))
            
            return response
    
    
    
    def JoinAuction(self, request, context):
        """Stream auction updates for a bidder by polling storage with quorum reads."""
        last_version = -1
        last_price = -1.0

        def quorum_read():
            """Read from quorum of replicas, return highest-version successful response or None."""
            responses = self.submit_task(self.GetItem_helper, quorum=READ_QUORUM, item_id=request.item_id)
            success_reads = [r for r in responses if r.success]
            if not success_reads:
                return None
            return max(success_reads, key=lambda r: r.item.version)

        # initial read
        initial = quorum_read()
        if initial is None:
            yield marketplace_pb2.AuctionUpdate(
                item_id=request.item_id,
                bidder_id=request.bidder_id,
                event_type="error",
                message="item not found",
                version=0,
            )
            return

        if initial.item.status != "auction":
            yield marketplace_pb2.AuctionUpdate(
                item_id=request.item_id,
                current_price=initial.item.current_price,
                bidder_id=request.bidder_id,
                event_type="error",
                message="item is not in auction mode",
                version=initial.item.version,
            )
            return

        last_version = initial.item.version
        last_price = initial.item.current_price
        yield marketplace_pb2.AuctionUpdate(
            item_id=request.item_id,
            current_price=initial.item.current_price,
            bidder_id=request.bidder_id,
            event_type="joined",
            message="joined auction",
            version=initial.item.version,
        )

        while context.is_active():
            latest = quorum_read()
            if latest is None:
                yield marketplace_pb2.AuctionUpdate(
                    item_id=request.item_id,
                    bidder_id=request.bidder_id,
                    event_type="auction_end",
                    message="item unavailable",
                    version=last_version,
                )
                return

            item = latest.item
            if item.version != last_version or item.current_price != last_price:
                yield marketplace_pb2.AuctionUpdate(
                    item_id=item.item_id,
                    current_price=item.current_price,
                    bidder_id=request.bidder_id,
                    event_type="new_bid",
                    message="auction updated",
                    version=item.version,
                )
                last_version = item.version
                last_price = item.current_price

            if item.status != "auction":
                yield marketplace_pb2.AuctionUpdate(
                    item_id=item.item_id,
                    current_price=item.current_price,
                    bidder_id=request.bidder_id,
                    event_type="auction_end",
                    message="auction ended",
                    version=item.version,
                )
                return

            time.sleep(1.0)


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    marketplace_pb2_grpc.add_FrontendServiceServicer_to_server(Frontend(), server)
    server.add_insecure_port(f"[::]:{PORT}")
    server.start()
    print(f"frontend {POD_NAME} listening on {PORT}", flush=True)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
