# -*- coding: utf-8 -*-
import dataclasses
import typing

import typing_inspect  # type: ignore

from serpyco.exception import NotADataClassError

JsonDict = typing.Dict[str, typing.Any]


JSON_ENCODABLE_TYPES = {
    str: {"type": "string"},
    int: {"type": "integer"},
    bool: {"type": "boolean"},
    float: {"type": "number"},
}


JsonEncodable = typing.Union[int, float, str, bool]

TypeOrTypes = typing.Union[
    type, typing.Tuple[typing.Union[type, typing.Tuple[typing.Any, ...]], ...]
]

FieldValidator = typing.Callable[[typing.Any], None]


def _issubclass_safe(field_type: type, types: TypeOrTypes) -> bool:
    try:
        return issubclass(field_type, types)
    except (TypeError, AttributeError):
        return False


def _is_generic(field_type: type, types: TypeOrTypes) -> bool:
    return (
        typing_inspect.is_generic_type(field_type)
        or typing_inspect.is_tuple_type(field_type)
    ) and issubclass(typing_inspect.get_origin(field_type), types)


def _is_union(field_type: type) -> bool:
    return typing_inspect.is_union_type(field_type)  # type: ignore


def _is_optional(field_type: type) -> bool:
    return typing_inspect.is_optional_type(field_type)  # type: ignore


@dataclasses.dataclass(init=False)
class _DataClassParams(object):
    type_: type
    arguments: typing.Tuple[type, ...]
    parameters: typing.Tuple[typing.Any, ...]

    def __init__(self, type_: type) -> None:
        self.arguments = typing_inspect.get_args(type_, evaluate=True)
        self.type_ = typing_inspect.get_origin(type_) or type_
        self.parameters = typing_inspect.get_parameters(self.type_)
        if not dataclasses.is_dataclass(self.type_):
            raise NotADataClassError(f"{self.type_} is not a dataclass")

    def resolve_type(self, field_type: typing.Any) -> typing.Any:
        # Resolve type in case of generic
        try:
            index = self.parameters.index(field_type)
            field_type = self.arguments[index]
        except ValueError:
            pass
        return field_type


def _get_values(components: typing.List[str], data: typing.Any) -> typing.Any:
    if not components:
        yield data
        return
    component = components[0]
    if isinstance(data, typing.Mapping):
        yield from _get_values(components[1:], data[component])
    elif isinstance(data, typing.Sequence):
        if "*" == component:
            for d in data:
                yield from _get_values(components[1:], d)
        else:
            yield from _get_values(components[1:], data[int(component)])
