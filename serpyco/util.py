import typing

JsonDict = typing.Dict[str, typing.Any]


JSON_ENCODABLE_TYPES = {
    str: {"type": "string"},
    int: {"type": "integer"},
    bool: {"type": "boolean"},
    float: {"type": "number"},
}


JsonEncodable = typing.Union[int, float, str, bool]


def _issubclass_safe(field_type, types) -> bool:
    try:
        return issubclass(field_type, types)
    except (TypeError, AttributeError):
        return False


def _is_generic(field_type, types) -> bool:
    try:
        return issubclass(field_type.__origin__, types)
    except (TypeError, AttributeError):
        return False


def _is_union(field_type) -> bool:
    try:
        return field_type.__origin__ is typing.Union
    except AttributeError:
        return False


def _is_optional(field_type) -> bool:
    return (
        _is_union(field_type)
        and 2 == len(field_type.__args__)
        and issubclass(field_type.__args__[1], type(None))
    )
