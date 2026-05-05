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
]


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


class Frontend(marketplace_pb2_grpc.FrontendServiceServicer):
    # ASSUME THERE IS ONLY 1 MACHINE AT THE MOMENT
    def __init__(self):
        # Maybe hashing the item_id wouldn't be a bad idea
        self.ITEM_ID = 0

    def CreateItem(self, request, context):
        # TODO:
        # Assumption: no duplicate items exists
        
        ## Incoming request
        # message CreateItemRequest {
        #     string seller_id = 1;
        #     string title = 2;
        #     string category = 3;
        #     string description = 4;
        #     double starting_price = 5;
        #     int32 quantity = 6;
        #     string status = 7;
        # }

        ## Turn into        
        # message StorageWriteRequest {
        #     Item item = 1;
        #     string operation = 2; // create, update, bid
        #     int64 proposed_version = 3;
        # }
        
        ## Conversion the request to target request
        requestItem = to_proto(request)
        target = storage_target("write")
        with grpc.insecure_channel(target) as channel:
            stub = marketplace_pb2_grpc.StorageServiceStub(channel)
            response = stub.Write(marketplace_pb2.StorageWriteRequest(
                item=requestItem, operation="create", proposed_version=1))
        
        # item_id = self.ITEM_ID
        if(response.success):
            self.ITEM_ID += 1
        
        print(f"{POD_NAME} CREATED ITEM -> {target}", flush=True)
        return marketplace_pb2.CreateItemResponse(
            success=response.success, 
            item_id=response.item.item_id, 
            message=response.message)

    def GetItem(self, request, context):
        target = storage_target("read")
        with grpc.insecure_channel(target) as channel:
            stub = marketplace_pb2_grpc.StorageServiceStub(channel)
            response = stub.Read(marketplace_pb2.StorageReadRequest(item_id=request.item_id))
            
        print(f"{POD_NAME} GET ITEM -> {target}", flush=True)
        return marketplace_pb2.GetItemResponse(
            success=response.success,
            item=response.item,
            message=response.message)

    def SearchItems(self, request, context):
        # message SearchItemsRequest {
        #     string keyword = 1;
        #     string category = 2;
        # }

        ## Turn Into
        
        target = storage_target("read")
        with grpc.insecure_channel(target) as channel:
            stub = marketplace_pb2_grpc.StorageServiceStub(channel)
            response = stub.Search(marketplace_pb2.StorageSearchRequest(
                keyword=request.keyword,
                category=request.category
            ))
        print(f"{POD_NAME} SEARCHED -> {target}", flush=True)
        return marketplace_pb2.SearchItemsResponse(
            success=response.success, 
            items=response.items)
    
    def UpdateItem(self, request, context):
        # TODO:
        # Assumption: no duplicate items exists
        
        ## Incoming request
        # message CreateItemRequest {
        #     string seller_id = 1;
        #     string title = 2;
        #     string category = 3;
        #     string description = 4;
        #     double starting_price = 5;
        #     int32 quantity = 6;
        #     string status = 7;
        # }

        ## Turn into        
        # message StorageWriteRequest {
        #     Item item = 1;
        #     string operation = 2; // create, update, bid
        #     int64 proposed_version = 3;
        # }
        
        ## Conversion the request to target request
        requestItem = to_proto(request)

        target = storage_target("write")
        with grpc.insecure_channel(target) as channel:
            stub = marketplace_pb2_grpc.StorageServiceStub(channel)
            response = stub.Write(marketplace_pb2.StorageWriteRequest(
                item=requestItem, operation="update", proposed_version=1))
        
        # item_id = self.ITEM_ID
        
        print(f"{POD_NAME} UPDATED ITEM -> {target}", flush=True)
        return marketplace_pb2.UpdateItemResponse(
            success=response.success, 
            item=response.item, 
            message=response.message)
    
    def PlaceBid(self, request, context):
        requestItem = to_proto(request)

        target = storage_target("write")
        with grpc.insecure_channel(target) as channel:
            stub = marketplace_pb2_grpc.StorageServiceStub(channel)
            response = stub.Write(marketplace_pb2.StorageWriteRequest(
                item=requestItem, operation="bid", proposed_version=1))
        
        
        print(f"{POD_NAME} PLACED A BID -> {target}", flush=True)
        return marketplace_pb2.PlaceBidResponse(
            success=response.success, 
            current_price=response.current_price, 
            message=response.message)
    
    def PlaceBid(self, request, context):
        requestItem = to_proto(request)

        target = storage_target("write")
        with grpc.insecure_channel(target) as channel:
            stub = marketplace_pb2_grpc.StorageServiceStub(channel)
            response = stub.Write(marketplace_pb2.StorageWriteRequest(
                item=requestItem, operation="bid", proposed_version=1))
        
        
        print(f"{POD_NAME} PLACED A BID -> {target}", flush=True)
        return marketplace_pb2.PlaceBidResponse(
            success=response.success, 
            current_price=response.current_price, 
            message=response.message)
    
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
