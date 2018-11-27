# -*- coding: utf-8 -*-

import typing

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
    try:
        return issubclass(getattr(field_type, "__origin__"), types)
    except (TypeError, AttributeError):
        return False


def _is_union(field_type: type) -> bool:
    try:
        return getattr(field_type, "__origin__") is typing.Union
    except AttributeError:
        return False


def _is_optional(field_type: type) -> bool:
    is_union = _is_union(field_type)
    try:
        args = getattr(field_type, "__args__")
    except AttributeError:
        return False
    return is_union and 2 == len(args) and issubclass(args[1], type(None))


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
