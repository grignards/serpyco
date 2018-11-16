import enum
import typing

import dataclasses

_metadata_name = "serpyco"


@dataclasses.dataclass
class FieldHints(object):
    dict_key: typing.Optional[str] = None
    ignore: bool = False
    getter: typing.Optional[typing.Callable] = None
    description: typing.Optional[str] = None
    examples: typing.List[str] = dataclasses.field(default_factory=list)
    format_: typing.Optional[str] = None
    pattern: typing.Optional[str] = None
    min_length: typing.Optional[int] = None
    max_length: typing.Optional[int] = None
    minimum: typing.Optional[int] = None
    maximum: typing.Optional[int] = None
    only: typing.List[str] = dataclasses.field(default_factory=list)
    exclude: typing.List[str] = dataclasses.field(default_factory=list)


_field_hints_names = set(f.name for f in dataclasses.fields(FieldHints))


class StringFormat(str, enum.Enum):
    """Possible formats for a string field"""

    DATETIME = "date-time"
    EMAIL = "email"
    HOSTNAME = "hostname"
    IPV4 = "ipv4"
    IPV6 = "ipv6"
    URI = "uri"


def field(
    dict_key: str = None,
    ignore: bool = False,
    getter: typing.Optional[typing.Callable] = None,
    description: typing.Optional[str] = None,
    examples: typing.List[str] = None,
    *args,
    **kwargs,
) -> dataclasses.Field:
    """
    Convenience function to setup Serializer hints on dataclass fields.
    Call it at field declaration as you would do with dataclass.field().
    Additional parameters will be passed verbatim to dataclass.field().

    :param dict_key: key of the field in the dumped dictionary
    :param ignore: if True, the field won't be considered by serpico
    :param getter: callable used to get values of this field.
        Must take one object argument
    :param description: a description for the field. Will be included
        in the generated JSON schema
    :param examples: a list of example usages for the field. Will be included
        in the generated JSON schema
    """
    metadata = kwargs.get("metadata", {})

    hints_args = {
        key: value
        for key, value in kwargs.items()
        if key in _field_hints_names and value is not None
    }

    field_args = {
        key: value for key, value in kwargs.items() if key not in _field_hints_names
    }

    hints = FieldHints(
        dict_key=dict_key,
        ignore=ignore,
        getter=getter,
        description=description,
        examples=examples,
        **hints_args,
    )

    metadata = field_args.get("metadata", {})
    metadata[_metadata_name] = hints
    field_args["metadata"] = metadata
    return dataclasses.field(*args, **field_args)


def string_field(
    dict_key: typing.Optional[str] = None,
    ignore: bool = False,
    getter: typing.Callable = None,
    description: typing.Optional[str] = None,
    examples: typing.List[str] = None,
    format_: typing.Optional[StringFormat] = None,
    pattern: typing.Optional[str] = None,
    min_length: typing.Optional[int] = None,
    max_length: typing.Optional[int] = None,
    *args,
    **kwargs,
) -> dataclasses.Field:
    """
    Convenience function to setup Serializer hints for a str dataclass field.
    Call it at field declaration as you would do with dataclass.field().
    Additional parameters will be passed verbatim to dataclass.field().

    :param dict_key: key of the field in the dumped dictionary
    :param ignore: if True, this field won't be considered by serpico
    :param getter: callable used to get values of this field.
        Must take one object argument
    :param description: a description for the field. Will be included
        in the generated JSON schema
    :param examples: a list of example usages for the field. Will be included
        in the generated JSON schema
    :param format_: additional semantic validation for strings
    :param pattern: restricts the strings of this field to the
        given regular expression
    :param min_length: minimum string length
    :param max_length: maximum string length
    """
    return field(
        dict_key,
        ignore,
        getter,
        description,
        examples,
        *args,
        format_=format_,
        pattern=pattern,
        min_length=min_length,
        max_length=max_length,
        **kwargs,
    )


def number_field(
    dict_key: typing.Optional[str] = None,
    ignore: bool = False,
    getter: typing.Callable = None,
    description: typing.Optional[str] = None,
    examples: typing.List[str] = None,
    minimum: typing.Optional[int] = None,
    maximum: typing.Optional[int] = None,
    *args,
    **kwargs,
) -> dataclasses.Field:
    """
    Convenience function to setup Serializer hints for a number (int/float)
    dataclass field.
    Call it at field declaration as you would do with dataclass.field().
    Additional parameters will be passed verbatim to dataclass.field().

    :param dict_key: key of the field in the dumped dictionary
    :param ignore: if True, this field won't be considered by serpico
    :param getter: callable used to get values of this field.
        Must take one object argument
    :param description: a description for the field. Will be included
        in the generated JSON schema
    :param examples: a list of example usages for the field. Will be included
        in the generated JSON schema
    :param minimum: minimum allowed value (inclusive)
    :param maximum: maximum allowed value (inclusive)
    """
    return field(
        dict_key,
        ignore,
        getter,
        description,
        examples,
        *args,
        minimum=minimum,
        maximum=maximum,
        **kwargs,
    )


def nested_field(
    only: typing.Optional[typing.List[str]] = None,
    exclude: typing.Optional[typing.List[str]] = None,
    dict_key: typing.Optional[str] = None,
    ignore: bool = False,
    getter: typing.Callable = None,
    description: typing.Optional[str] = None,
    examples: typing.List[str] = None,
    *args,
    **kwargs,
) -> dataclasses.Field:
    return field(
        dict_key,
        ignore,
        getter,
        description,
        examples,
        *args,
        only=only,
        exclude=exclude,
        **kwargs,
    )
