from google.protobuf import timestamp_pb2 as _timestamp_pb2
import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Trade(_message.Message):
    __slots__ = ("exchange", "code", "trade_price", "trade_volume", "ask_bid", "prev_closing_price", "change", "change_price", "trade_timestamp", "sequential_id", "stream_type", "received_timestamp")
    EXCHANGE_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    TRADE_PRICE_FIELD_NUMBER: _ClassVar[int]
    TRADE_VOLUME_FIELD_NUMBER: _ClassVar[int]
    ASK_BID_FIELD_NUMBER: _ClassVar[int]
    PREV_CLOSING_PRICE_FIELD_NUMBER: _ClassVar[int]
    CHANGE_FIELD_NUMBER: _ClassVar[int]
    CHANGE_PRICE_FIELD_NUMBER: _ClassVar[int]
    TRADE_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    SEQUENTIAL_ID_FIELD_NUMBER: _ClassVar[int]
    STREAM_TYPE_FIELD_NUMBER: _ClassVar[int]
    RECEIVED_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    exchange: _common_pb2.Exchange
    code: str
    trade_price: float
    trade_volume: float
    ask_bid: _common_pb2.AskBid
    prev_closing_price: float
    change: _common_pb2.ChangeType
    change_price: float
    trade_timestamp: _timestamp_pb2.Timestamp
    sequential_id: int
    stream_type: _common_pb2.StreamType
    received_timestamp: _timestamp_pb2.Timestamp
    def __init__(self, exchange: _Optional[_Union[_common_pb2.Exchange, str]] = ..., code: _Optional[str] = ..., trade_price: _Optional[float] = ..., trade_volume: _Optional[float] = ..., ask_bid: _Optional[_Union[_common_pb2.AskBid, str]] = ..., prev_closing_price: _Optional[float] = ..., change: _Optional[_Union[_common_pb2.ChangeType, str]] = ..., change_price: _Optional[float] = ..., trade_timestamp: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., sequential_id: _Optional[int] = ..., stream_type: _Optional[_Union[_common_pb2.StreamType, str]] = ..., received_timestamp: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class OrderBookLevel(_message.Message):
    __slots__ = ("price", "size")
    PRICE_FIELD_NUMBER: _ClassVar[int]
    SIZE_FIELD_NUMBER: _ClassVar[int]
    price: float
    size: float
    def __init__(self, price: _Optional[float] = ..., size: _Optional[float] = ...) -> None: ...

class OrderBookUpdate(_message.Message):
    __slots__ = ("exchange", "code", "total_ask_size", "total_bid_size", "asks", "bids", "stream_type", "event_timestamp", "received_timestamp")
    EXCHANGE_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    TOTAL_ASK_SIZE_FIELD_NUMBER: _ClassVar[int]
    TOTAL_BID_SIZE_FIELD_NUMBER: _ClassVar[int]
    ASKS_FIELD_NUMBER: _ClassVar[int]
    BIDS_FIELD_NUMBER: _ClassVar[int]
    STREAM_TYPE_FIELD_NUMBER: _ClassVar[int]
    EVENT_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    RECEIVED_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    exchange: _common_pb2.Exchange
    code: str
    total_ask_size: float
    total_bid_size: float
    asks: _containers.RepeatedCompositeFieldContainer[OrderBookLevel]
    bids: _containers.RepeatedCompositeFieldContainer[OrderBookLevel]
    stream_type: _common_pb2.StreamType
    event_timestamp: _timestamp_pb2.Timestamp
    received_timestamp: _timestamp_pb2.Timestamp
    def __init__(self, exchange: _Optional[_Union[_common_pb2.Exchange, str]] = ..., code: _Optional[str] = ..., total_ask_size: _Optional[float] = ..., total_bid_size: _Optional[float] = ..., asks: _Optional[_Iterable[_Union[OrderBookLevel, _Mapping]]] = ..., bids: _Optional[_Iterable[_Union[OrderBookLevel, _Mapping]]] = ..., stream_type: _Optional[_Union[_common_pb2.StreamType, str]] = ..., event_timestamp: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., received_timestamp: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...
