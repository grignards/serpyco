import enum
import typing

import dataclasses

_metadata_name = "serpyco"


class FieldHints(object):
    def __init__(
        self,
        dict_key: typing.Optional[str],
        ignore: bool = False,
        getter: typing.Callable = None,
        description: typing.Optional[str] = None,
        examples: typing.Optional[typing.List[str]] = None,
        pattern: typing.Optional[str] = None,
        min_length: typing.Optional[int] = None,
        max_length: typing.Optional[int] = None,
        minimum: typing.Optional[int] = None,
        maximum: typing.Optional[int] = None,
    ) -> None:
        self.dict_key = dict_key
        self.ignore = ignore
        self.getter = getter
        self.description = description
        self.examples = examples
        self.pattern = pattern
        self.min_length = min_length
        self.max_length = max_length
        self.minimum = minimum
        self.maximum = maximum


class StringPattern(str, enum.Enum):
    """
    Predefined patterns for a string field.
    These are just helpers as completely matching emails/uris
    with a pattern is almost a lost cause.
    """

    EMAIL = r"^.+@.+$"
    HOSTNAME = r"^([0-9a-z][-\w]*[0-9a-z]\.)+[a-z0-9\-]{2,15}$"
    IPV4 = r"((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)(\.|$)){4}"
    IPV6 = (
        r"(([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}"
        r"|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:)"
        r"{1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}"
        r"(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}"
        r"(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}"
        r"(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}"
        r"(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:"
        r"((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:)"
        r"|fe80:(:[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|"
        r"::(ffff(:0{1,4}){0,1}:){0,1}((25[0-5]|(2[0-4]|"
        r"1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])"
        r"|([0-9a-fA-F]{1,4}:){1,4}:((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.)"
        r"{3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9]))"
    )
    URI = (
        # protocol identifier (optional)
        # short syntax // still required
        r"^(?:(?:(?:https?|ftp):)?\\/\\/)"
        # user:pass BasicAuth (optional)
        r"(?:\\S+(?::\\S*)?@)?"
        r"(?:"
        # IP address exclusion
        # private & local networks
        r"(?!(?:10|127)(?:\\.\\d{1,3}){3})"
        r"(?!(?:169\\.254|192\\.168)(?:\\.\\d{1,3}){2})"
        r"(?!172\\.(?:1[6-9]|2\\d|3[0-1])(?:\\.\\d{1,3}){2})"
        # IP address dotted notation octets
        # excludes loopback network 0.0.0.0
        # excludes reserved space >= 224.0.0.0
        # excludes network & broacast addresses
        # (first & last IP address of each class)
        r"(?:[1-9]\\d?|1\\d\\d|2[01]\\d|22[0-3])"
        r"(?:\\.(?:1?\\d{1,2}|2[0-4]\\d|25[0-5])){2}"
        r"(?:\\.(?:[1-9]\\d?|1\\d\\d|2[0-4]\\d|25[0-4]))"
        r"|"
        # host & domain names, may end with dot
        # can be replaced by a shortest alternative
        # (?![-_])(?:[-\\w\\u00a1-\\uffff]{0,63}[^-_]\\.)+
        r"(?:"
        r"(?:"
        r"[a-z0-9\\u00a1-\\uffff]"
        r"[a-z0-9\\u00a1-\\uffff_-]{0,62}"
        r")?"
        r"[a-z0-9\\u00a1-\\uffff]\\."
        r")+"
        # TLD identifier name, may end with dot
        r"(?:[a-z\\u00a1-\\uffff]{2,}\\.?)"
        r")"
        # port number (optional)
        r"(?::\\d{2,5})?"
        # resource path (optional)
        r"(?:[/?#]\\S*)?$"
    )


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
    hints = FieldHints(
        dict_key=dict_key,
        ignore=ignore,
        getter=getter,
        description=description,
        examples=examples,
    )

    for attr in vars(hints).keys():
        if attr not in ["dict_key", "ignore", "getter", "description", "examples"]:
            setattr(hints, attr, kwargs.pop(attr, None))

    metadata[_metadata_name] = hints
    kwargs["metadata"] = metadata
    return dataclasses.field(*args, **kwargs)


def string_field(
    dict_key: typing.Optional[str] = None,
    ignore: bool = False,
    getter: typing.Callable = None,
    description: typing.Optional[str] = None,
    examples: typing.List[str] = None,
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
