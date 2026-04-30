from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Item(_message.Message):
    __slots__ = ("item_id", "seller_id", "title", "category", "description", "starting_price", "current_price", "quantity", "status", "version")
    ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    SELLER_ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    STARTING_PRICE_FIELD_NUMBER: _ClassVar[int]
    CURRENT_PRICE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    item_id: str
    seller_id: str
    title: str
    category: str
    description: str
    starting_price: float
    current_price: float
    quantity: int
    status: str
    version: int
    def __init__(self, item_id: _Optional[str] = ..., seller_id: _Optional[str] = ..., title: _Optional[str] = ..., category: _Optional[str] = ..., description: _Optional[str] = ..., starting_price: _Optional[float] = ..., current_price: _Optional[float] = ..., quantity: _Optional[int] = ..., status: _Optional[str] = ..., version: _Optional[int] = ...) -> None: ...

class CreateItemRequest(_message.Message):
    __slots__ = ("seller_id", "title", "category", "description", "starting_price", "quantity", "status")
    SELLER_ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    STARTING_PRICE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    seller_id: str
    title: str
    category: str
    description: str
    starting_price: float
    quantity: int
    status: str
    def __init__(self, seller_id: _Optional[str] = ..., title: _Optional[str] = ..., category: _Optional[str] = ..., description: _Optional[str] = ..., starting_price: _Optional[float] = ..., quantity: _Optional[int] = ..., status: _Optional[str] = ...) -> None: ...

class CreateItemResponse(_message.Message):
    __slots__ = ("success", "item_id", "message")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    item_id: str
    message: str
    def __init__(self, success: bool = ..., item_id: _Optional[str] = ..., message: _Optional[str] = ...) -> None: ...

class GetItemRequest(_message.Message):
    __slots__ = ("item_id",)
    ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    item_id: str
    def __init__(self, item_id: _Optional[str] = ...) -> None: ...

class GetItemResponse(_message.Message):
    __slots__ = ("success", "item", "message")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    ITEM_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    item: Item
    message: str
    def __init__(self, success: bool = ..., item: _Optional[_Union[Item, _Mapping]] = ..., message: _Optional[str] = ...) -> None: ...

class SearchItemsRequest(_message.Message):
    __slots__ = ("keyword", "category")
    KEYWORD_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    keyword: str
    category: str
    def __init__(self, keyword: _Optional[str] = ..., category: _Optional[str] = ...) -> None: ...

class SearchItemsResponse(_message.Message):
    __slots__ = ("success", "items", "message")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    items: _containers.RepeatedCompositeFieldContainer[Item]
    message: str
    def __init__(self, success: bool = ..., items: _Optional[_Iterable[_Union[Item, _Mapping]]] = ..., message: _Optional[str] = ...) -> None: ...

class UpdateItemRequest(_message.Message):
    __slots__ = ("item_id", "description", "quantity", "status", "current_price", "expected_version")
    ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    CURRENT_PRICE_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_VERSION_FIELD_NUMBER: _ClassVar[int]
    item_id: str
    description: str
    quantity: int
    status: str
    current_price: float
    expected_version: int
    def __init__(self, item_id: _Optional[str] = ..., description: _Optional[str] = ..., quantity: _Optional[int] = ..., status: _Optional[str] = ..., current_price: _Optional[float] = ..., expected_version: _Optional[int] = ...) -> None: ...

class UpdateItemResponse(_message.Message):
    __slots__ = ("success", "item", "message")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    ITEM_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    item: Item
    message: str
    def __init__(self, success: bool = ..., item: _Optional[_Union[Item, _Mapping]] = ..., message: _Optional[str] = ...) -> None: ...

class PlaceBidRequest(_message.Message):
    __slots__ = ("item_id", "bidder_id", "bid_amount")
    ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    BIDDER_ID_FIELD_NUMBER: _ClassVar[int]
    BID_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    item_id: str
    bidder_id: str
    bid_amount: float
    def __init__(self, item_id: _Optional[str] = ..., bidder_id: _Optional[str] = ..., bid_amount: _Optional[float] = ...) -> None: ...

class PlaceBidResponse(_message.Message):
    __slots__ = ("success", "current_price", "message")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    CURRENT_PRICE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    current_price: float
    message: str
    def __init__(self, success: bool = ..., current_price: _Optional[float] = ..., message: _Optional[str] = ...) -> None: ...

class JoinAuctionRequest(_message.Message):
    __slots__ = ("item_id", "bidder_id")
    ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    BIDDER_ID_FIELD_NUMBER: _ClassVar[int]
    item_id: str
    bidder_id: str
    def __init__(self, item_id: _Optional[str] = ..., bidder_id: _Optional[str] = ...) -> None: ...

class AuctionUpdate(_message.Message):
    __slots__ = ("item_id", "current_price", "bidder_id", "event_type", "message", "version")
    ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    CURRENT_PRICE_FIELD_NUMBER: _ClassVar[int]
    BIDDER_ID_FIELD_NUMBER: _ClassVar[int]
    EVENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    item_id: str
    current_price: float
    bidder_id: str
    event_type: str
    message: str
    version: int
    def __init__(self, item_id: _Optional[str] = ..., current_price: _Optional[float] = ..., bidder_id: _Optional[str] = ..., event_type: _Optional[str] = ..., message: _Optional[str] = ..., version: _Optional[int] = ...) -> None: ...
