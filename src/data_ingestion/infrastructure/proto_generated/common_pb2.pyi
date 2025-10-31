from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from typing import ClassVar as _ClassVar

DESCRIPTOR: _descriptor.FileDescriptor

class Exchange(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    EXCHANGE_UNSPECIFIED: _ClassVar[Exchange]
    UPBIT: _ClassVar[Exchange]

class ChangeType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    CHANGE_TYPE_UNSPECIFIED: _ClassVar[ChangeType]
    RISE: _ClassVar[ChangeType]
    EVEN: _ClassVar[ChangeType]
    FALL: _ClassVar[ChangeType]

class AskBid(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ASK_BID_UNSPECIFIED: _ClassVar[AskBid]
    ASK: _ClassVar[AskBid]
    BID: _ClassVar[AskBid]

class StreamType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    STREAM_TYPE_UNSPECIFIED: _ClassVar[StreamType]
    SNAPSHOT: _ClassVar[StreamType]
    REALTIME: _ClassVar[StreamType]
EXCHANGE_UNSPECIFIED: Exchange
UPBIT: Exchange
CHANGE_TYPE_UNSPECIFIED: ChangeType
RISE: ChangeType
EVEN: ChangeType
FALL: ChangeType
ASK_BID_UNSPECIFIED: AskBid
ASK: AskBid
BID: AskBid
STREAM_TYPE_UNSPECIFIED: StreamType
SNAPSHOT: StreamType
REALTIME: StreamType
