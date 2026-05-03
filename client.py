import sys
import os
import grpc

import marketplace_pb2
import marketplace_pb2_grpc

# If running in devcontainer use host.docker.internal
# If running on host machine use localhost
TARGET = os.environ.get("TARGET",  "localhost:50051")
# TARGET = "host.docker.internal:50051"
# TARGET = "localhost:50051"

# ## Conversion the request to target request
#         requestItem = marketplace_pb2.Item(
#                     item_id = f"{self.ITEM_ID}",
#                     seller_id = request.seller_id,
#                     title = request.title,
#                     category = request.category,
#                     description = request.description,
#                     starting_price = request.starting_price,
#                     current_price = request.starting_price,
#                     quantity = request.quantity,
#                     status = request.status,
#                     version = 1
#         )

def main():
    # if len(sys.argv) < 3:
    #     print("put <key> <value>")
    #     print("get <key>")
    #     return
    

    # key=sys.argv[2]
    # if key=="put":
    #     value=sys.argv[3]
    # else:
    #     value=""
    
    with grpc.insecure_channel(TARGET) as channel:
        stub = marketplace_pb2_grpc.FrontendServiceStub(channel)
        response = stub.CreateItem(marketplace_pb2.CreateItemRequest(
            seller_id = "123",
            title = "test_item123",
            category = "test_cat",
            description = "test_description",
            starting_price = 100.0,
            quantity = 109,
            status = "available"
        ))
        print({"success": response.success, "item_id": response.item_id})

        item_id = response.item_id

        response = stub.GetItem(marketplace_pb2.GetItemRequest(item_id=item_id))
        print({"success": response.success, "item": response.item})

        response = stub.CreateItem(marketplace_pb2.CreateItemRequest(
            seller_id = "124",
            title = "test_item124",
            category = "test_cat",
            description = "test_description dsfdsfdsf",
            starting_price = 110.0,
            quantity = 19999,
            status = "available"
        ))
        print({"success": response.success, "item_id": response.item_id})

        response = stub.CreateItem(marketplace_pb2.CreateItemRequest(
            seller_id = "125",
            title = "test_item item item item",
            category = "test_cat",
            description = "test_description cat cat cat cat",
            starting_price = 120.0,
            quantity = 110,
            status = "available"
        ))
        print({"success": response.success, "item_id": response.item_id})

        response = stub.SearchItems(marketplace_pb2.SearchItemsRequest(
            keyword="item",
            category="test_cat"
        ))
        print({"success": response.success, "item_id": response.items})


if __name__ == "__main__":
    main()
