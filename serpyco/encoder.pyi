import typing

from .util import JsonDict

class FieldEncoder:
    """Base class for encoding fields to and from JSON encodable values"""

    def dump(self, value: typing.Any) -> typing.Any: ...
    def load(self, value: typing.Any) -> typing.Any: ...
    def json_schema(self) -> JsonDict: ...
