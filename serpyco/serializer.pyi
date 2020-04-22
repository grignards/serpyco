import typing

from .encoder import FieldEncoder
from .util import JsonDict

D = typing.TypeVar("D")

DictOrIterable = typing.Union[JsonDict, typing.Iterable[JsonDict]]
DictOrList = typing.Union[JsonDict, typing.List[JsonDict]]

class Serializer(typing.Generic[D]):
    def __init__(
        self,
        dataclass: typing.Type[D],
        omit_none: bool = True,
        type_encoders: typing.Optional[typing.Dict[type, FieldEncoder]] = None,
        only: typing.Optional[typing.List[str]] = None,
        exclude: typing.Optional[typing.List[str]] = None,
        strict: bool = False,
        load_as_type: typing.Optional[type] = None,
    ) -> None: ...
    def json_schema(self, many: bool = False) -> JsonDict: ...
    def get_dict_path(self, obj_path: typing.Sequence[str]) -> typing.List[str]: ...
    def get_object_path(self, dict_path: typing.Sequence[str]) -> typing.List[str]: ...
    @classmethod
    def register_global_type(cls, field_type: type, encoder: FieldEncoder) -> None: ...
    @classmethod
    def unregister_global_type(cls, field_type: type) -> None: ...
    def dataclass(self) -> type: ...
    def dump(
        self,
        obj: typing.Union[D, typing.Iterable[D]],
        validate: bool = False,
        many: bool = False,
    ) -> DictOrList: ...
    def load(
        self, data: DictOrIterable, validate: bool = True, many: bool = False
    ) -> typing.Union[D, typing.List[D]]: ...
    def dump_json(
        self,
        obj: typing.Union[D, typing.Iterable[D]],
        validate: bool = False,
        many: bool = False,
    ) -> str: ...
    def load_json(
        self, js: str, validate: bool = True, many: bool = False
    ) -> typing.Union[D, typing.List[D]]: ...
