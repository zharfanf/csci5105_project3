import hashlib
import os
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
ITEM_ID = 0


# def storage_target(key: str) -> str:
#     n = int(hashlib.md5(key.encode()).hexdigest(), 16)
#     return STORAGE_TARGETS[n % len(STORAGE_TARGETS)]

def storage_target(key: str) -> str:
    if key == "write":
        return STORAGE_TARGETS[0]
    return STORAGE_TARGETS[0]

# helper functions for converting between dicts and protobuf messages
def to_proto(d):
    return marketplace_pb2.Item(
        item_id=d.get("item_id", ITEM_ID),
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


class Frontend(marketplace_pb2_grpc.FrontendServiceServicer):
    # ASSUME THERE IS ONLY 1 MACHINE AT THE MOMENT
    def __init__(self):
        # Maybe hashing the item_id wouldn't be a bad idea
        # self.ITEM_ID = 0
        pass
    
    def submit_task(self, task, **kwargs):
        with futures.ThreadPoolExecutor(workers=3) as executor:
            # Submit tasks with different completion times
            futures = [executor.submit(task, target, **kwargs) for target in STORAGE_TARGETS]
            
            print("Waiting up to 2 seconds for tasks to finish...")
            
            # wait() pauses the main program for up to 3 seconds, then moves on
            done, not_done = futures.wait(futures, timeout=2.0)
            
            # Process the ones that finished
            print(f"\n--- Finished Tasks ({len(done)}) ---")
            for future in done:
                print(future.result())
                
            # Acknowledge the ones that didn't, and let them be
            print(f"\n--- Tasks left behind ({len(not_done)}) ---")
            print("These are still running in the background, but we aren't waiting.")

            return done, not_done

    
    def CreateItem_helper(self, target, item):
        with grpc.insecure_channel(target) as channel:
            stub = marketplace_pb2_grpc.StorageServiceStub(channel)
            response = stub.Write(marketplace_pb2.StorageWriteRequest(
                item=item, operation="create", proposed_version=1))
            
            return response

    def CreateItem(self, request, context):
        requestItem = to_proto(request)

        response_done, _ = self.submit_task(self.CreateItem_helper, item=requestItem)
        if(response_done[0].success):
            ITEM_ID += 1

        return marketplace_pb2.CreateItemResponse(
            success=response_done[0].success, 
            item_id=response_done[0].item.item_id, 
            message=response_done[0].message)


    def GetItem_helper(self, target, item_id):
        with grpc.insecure_channel(target) as channel:
            stub = marketplace_pb2_grpc.StorageServiceStub(channel)
            response = stub.Read(marketplace_pb2.StorageReadRequest(item_id=item_id))

            return response
        
    def GetItem(self, request, context):
        response_done, _ = self.submit_task(self.GetItem_helper, item=request.item_id)

        # check if the results are consistent, if not then repair, pass this for now
        
        return marketplace_pb2.GetItemResponse(
            success=response_done[0].success,
            item=response_done[0].item,
            message=response_done[0].message)
    
    
    def SearchItems_helper(self, target, keyword, category):
        with grpc.insecure_channel(target) as channel:
            stub = marketplace_pb2_grpc.StorageServiceStub(channel)
            response = stub.Search(marketplace_pb2.StorageSearchRequest(
                keyword=keyword,
                category=category
            ))

            return response
        
    def SearchItems(self, request, context):
        response_done, _ = self.submit_task(self.SearchItems_helper, keyword=request.keyword, category=request.category)

        print(f"{POD_NAME} SEARCHED -> {target}", flush=True)
        return marketplace_pb2.SearchItemsResponse(
            success=response_done[0].success, 
            items=response_done[0].items)
    
    
    def UpdateItem_helper(self, target, item):
        with grpc.insecure_channel(target) as channel:
            stub = marketplace_pb2_grpc.StorageServiceStub(channel)
            response = stub.Write(marketplace_pb2.StorageWriteRequest(
                item=item, operation="update", proposed_version=1))
            
            return response
        
    def UpdateItem(self, request, context):
        requestItem = to_proto(request)

        response_done, _ = self.submit_task(self.UpdateItem_helper, item=requestItem)
        
        print(f"{POD_NAME} UPDATED ITEM -> {STORAGE_TARGETS}", flush=True)
        return marketplace_pb2.UpdateItemResponse(
            success=response_done[0].success, 
            item=response_done[0].item, 
            message=response_done[0].message)
    
    
    def PlaceBid_helper(self, target, item):
        with grpc.insecure_channel(target) as channel:
            stub = marketplace_pb2_grpc.StorageServiceStub(channel)
            response = stub.Write(marketplace_pb2.StorageWriteRequest(
                item=item, operation="bid", proposed_version=1))
            
            return response
    
    def PlaceBid(self, request, context):
        requestItem = to_proto(request)

        response_done, _ = self.submit_task(self.PlaceBid_helper, item=requestItem)
        
        print(f"{POD_NAME} PLACED A BID -> {STORAGE_TARGETS}", flush=True)
        return marketplace_pb2.PlaceBidResponse(
            success=response_done[0].success, 
            current_price=response_done[0].current_price, 
            message=response_done[0].message)
    
    # def JoinAuction(self, request, context):
    #     requestItem = to_proto(request)

    #     target = storage_target("write")
    #     with grpc.insecure_channel(target) as channel:
    #         stub = marketplace_pb2_grpc.StorageServiceStub(channel)
    #         response = stub.Write(marketplace_pb2.StorageWriteRequest(
    #             item=requestItem, operation="bid", proposed_version=1))
        
        
    #     print(f"{POD_NAME} PLACED A BID -> {target}", flush=True)
    #     return marketplace_pb2.PlaceBidResponse(
    #         success=response.success, 
    #         current_price=response.current_price, 
    #         message=response.message)


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    marketplace_pb2_grpc.add_FrontendServiceServicer_to_server(Frontend(), server)
    server.add_insecure_port(f"[::]:{PORT}")
    server.start()
    print(f"frontend {POD_NAME} listening on {PORT}", flush=True)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
