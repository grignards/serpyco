# -*- coding: utf-8 -*-

import datetime
import enum
import json
import typing

import pytest

import dataclasses
import dateutil
import serpyco


class Enum(enum.Enum):
    """
    An enumerate.
    """

    ONE = 1
    TWO = 2


@dataclasses.dataclass
class Simple(object):
    """
    Basic class.
    """

    name: str


@dataclasses.dataclass
class Types(object):
    """
    Testing class for supported serializer types.
    """

    integer: int
    string: str
    number: float
    boolean: bool
    enum_: Enum
    items: typing.List[str]
    nested: Simple
    nesteds: typing.List[Simple]
    mapping: typing.Dict[str, str]
    datetime_: datetime.datetime
    optional: typing.Optional[int] = None


@dataclasses.dataclass
class First(object):
    """Cycle test class"""

    second: "Second"


@dataclasses.dataclass
class Second(object):
    """Cycle test class"""

    first: First


@pytest.fixture
def types_object() -> Types:
    return Types(
        integer=42,
        string="foo",
        number=12.34,
        boolean=True,
        enum_=Enum.TWO,
        items=["one", "two"],
        nested=Simple(name="bar"),
        nesteds=[Simple(name="hello"), Simple(name="world")],
        mapping={"foo": "bar"},
        datetime_=datetime.datetime(
            2018, 11, 1, 14, 23, 43, 123456, tzinfo=dateutil.tz.tzutc()
        ),
    )


def test_unit__dump__ok__nominal_case(types_object: Types) -> None:
    serializer = serpyco.Serializer(Types)
    assert {
        "integer": 42,
        "string": "foo",
        "number": 12.34,
        "boolean": True,
        "enum_": 2,
        "items": ["one", "two"],
        "nested": {"name": "bar"},
        "nesteds": [{"name": "hello"}, {"name": "world"}],
        "mapping": {"foo": "bar"},
        "datetime_": "2018-11-01T14:23:43.123456+00:00",
    } == serializer.dump(types_object)


def test_unit__dump__ok__with_none(types_object: Types) -> None:
    serializer = serpyco.Serializer(Types, omit_none=False)
    data = serializer.dump(types_object)
    assert "optional" in data
    assert None is data["optional"]


def test_unit__dump_json__ok__nominal_case(types_object: Types) -> None:
    serializer = serpyco.Serializer(Types)

    data = serializer.dump(types_object)
    assert json.dumps(data, separators=(",", ":")) == serializer.dump_json(types_object)


def test_unit__load__ok__nominal_case(types_object: Types) -> None:
    serializer = serpyco.Serializer(Types)
    assert types_object == serializer.load(
        {
            "integer": 42,
            "string": "foo",
            "number": 12.34,
            "boolean": True,
            "enum_": 2,
            "items": ["one", "two"],
            "nested": {"name": "bar"},
            "nesteds": [{"name": "hello"}, {"name": "world"}],
            "mapping": {"foo": "bar"},
            "datetime_": "2018-11-01T14:23:43.123456Z",
        }
    )


def test_unit__load_json__ok__nominal_case(types_object: Types) -> None:
    serializer = serpyco.Serializer(Types)
    assert types_object == serializer.load_json(
        json.dumps(
            {
                "integer": 42,
                "string": "foo",
                "number": 12.34,
                "boolean": True,
                "enum_": 2,
                "items": ["one", "two"],
                "nested": {"name": "bar"},
                "nesteds": [{"name": "hello"}, {"name": "world"}],
                "mapping": {"foo": "bar"},
                "datetime_": "2018-11-01T14:23:43.123456Z",
            }
        )
    )


def test_unit__from_dump__ok__with_many(types_object: Types) -> None:
    serializer = serpyco.Serializer(Types, many=True)

    data = serializer.dump([types_object, types_object])

    assert [types_object, types_object] == serializer.load(data)


def test_unit__from_dump_json__ok__with_many(types_object: Types) -> None:
    serializer = serpyco.Serializer(Types, many=True)

    data = serializer.dump_json([types_object, types_object])

    assert [types_object, types_object] == serializer.load_json(data)


def test_unit__json_schema__ok__nominal_case() -> None:
    serializer = serpyco.Serializer(Types)
    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "definitions": {
            "Simple": {
                "description": "Basic class.",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
                "type": "object",
            }
        },
        "description": "Testing class for supported serializer types.",
        "properties": {
            "boolean": {"type": "boolean"},
            "datetime_": {"format": "date-time", "type": "string"},
            "enum_": {
                "description": "An enumerate.",
                "enum": [1, 2],
                "type": "integer",
            },
            "integer": {"type": "integer"},
            "items": {"items": {"type": "string"}, "type": "array"},
            "mapping": {"additionalProperties": {"type": "string"}, "type": "object"},
            "nested": {"$ref": "#/definitions/Simple"},
            "nesteds": {"items": {"$ref": "#/definitions/Simple"}, "type": "array"},
            "number": {"type": "number"},
            "optional": {"type": "integer"},
            "string": {"type": "string"},
        },
        "required": [
            "integer",
            "string",
            "number",
            "boolean",
            "enum_",
            "items",
            "nested",
            "nesteds",
            "mapping",
            "datetime_",
        ],
        "type": "object",
    } == serializer.json_schema()


def test_unit__json_schema__ok__with_many() -> None:
    serializer = serpyco.Serializer(Types, many=True)
    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "definitions": {
            "Simple": {
                "description": "Basic class.",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
                "type": "object",
            }
        },
        "items": {
            "description": "Testing class for supported serializer types.",
            "properties": {
                "boolean": {"type": "boolean"},
                "datetime_": {"format": "date-time", "type": "string"},
                "enum_": {
                    "description": "An enumerate.",
                    "enum": [1, 2],
                    "type": "integer",
                },
                "integer": {"type": "integer"},
                "items": {"items": {"type": "string"}, "type": "array"},
                "mapping": {
                    "additionalProperties": {"type": "string"},
                    "type": "object",
                },
                "nested": {"$ref": "#/definitions/Simple"},
                "nesteds": {"items": {"$ref": "#/definitions/Simple"}, "type": "array"},
                "number": {"type": "number"},
                "optional": {"type": "integer"},
                "string": {"type": "string"},
            },
            "required": [
                "integer",
                "string",
                "number",
                "boolean",
                "enum_",
                "items",
                "nested",
                "nesteds",
                "mapping",
                "datetime_",
            ],
            "type": "object",
        },
        "type": "array",
    } == serializer.json_schema()


def test_unit__json_schema__ok__cycle() -> None:
    ser = serpyco.Serializer(First)
    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "definitions": {
            "Second": {
                "description": "Cycle test class",
                "properties": {"first": {"$ref": "#"}},
                "required": ["first"],
                "type": "object",
            }
        },
        "description": "Cycle test class",
        "properties": {"second": {"$ref": "#/definitions/Second"}},
        "required": ["second"],
        "type": "object",
    } == ser.json_schema()


def test_unit__dump_json__ok__validate() -> None:
    serializer = serpyco.Serializer(Simple)

    assert serializer.dump(Simple(name="foo"), validate=True)
    assert serializer.dump_json(Simple(name="foo"), validate=True)

    with pytest.raises(serpyco.ValidationError):
        serializer.dump(Simple(name=42), validate=True)
    with pytest.raises(serpyco.ValidationError):
        serializer.dump_json(Simple(name=42), validate=True)


def test_unit__load_json__ok__validate() -> None:
    serializer = serpyco.Serializer(Simple)

    assert serializer.load({"name": "foo"}, validate=True)
    assert serializer.load_json('{"name": "foo"}', validate=True)

    with pytest.raises(serpyco.ValidationError):
        serializer.load({"name": 42}, validate=True)
    with pytest.raises(serpyco.ValidationError):
        serializer.load_json('{"name": 42}', validate=True)


def test_unit__union__ok__nominal_case() -> None:
    @dataclasses.dataclass
    class WithUnion(object):
        """Union test class"""

        foo: typing.Union[str, int]

    serializer = serpyco.Serializer(WithUnion)

    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "definitions": {},
        "description": "Union test class",
        "properties": {"foo": {"oneOf": [{"type": "string"}, {"type": "integer"}]}},
        "required": ["foo"],
        "type": "object",
    } == serializer.json_schema()

    assert {"foo": 42} == serializer.dump(WithUnion(foo=42), validate=True)
    assert {"foo": "bar"} == serializer.dump(WithUnion(foo="bar"), validate=True)
    with pytest.raises(serpyco.ValidationError):
        serializer.dump(WithUnion(foo=12.34), validate=True)


def test_unit__tuple__ok__nominal_case() -> None:
    @dataclasses.dataclass
    class WithTuple(object):
        """Tuple test class"""

        tuple_: typing.Tuple[str]

    serializer = serpyco.Serializer(WithTuple)

    assert WithTuple(tuple_=("foo", "bar")) == serializer.load(
        {"tuple_": ["foo", "bar"]}
    )


def test_unit__string_field__ok__nominal_case() -> None:
    @dataclasses.dataclass
    class WithStringField(object):
        """String field test class"""

        foo: str = serpyco.string_field(
            format_=serpyco.StringFormat.EMAIL,
            pattern="^[A-Z]",
            min_length=3,
            max_length=24,
        )

    serializer = serpyco.Serializer(WithStringField)

    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "definitions": {},
        "description": "String field test class",
        "properties": {
            "foo": {
                "type": "string",
                "format": "email",
                "pattern": "^[A-Z]",
                "minLength": 3,
                "maxLength": 24,
            }
        },
        "required": ["foo"],
        "type": "object",
    } == serializer.json_schema()

    assert serializer.load({"foo": "Foo@foo.bar"})


def test_unit__number_field__ok__nominal_case() -> None:
    @dataclasses.dataclass
    class WithNumberField(object):
        """Number field test class"""

        foo: int = serpyco.number_field(minimum=0, maximum=12)

    serializer = serpyco.Serializer(WithNumberField)

    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "definitions": {},
        "description": "Number field test class",
        "properties": {"foo": {"type": "integer", "minimum": 0, "maximum": 12}},
        "required": ["foo"],
        "type": "object",
    } == serializer.json_schema()

    assert serializer.load({"foo": 5})
