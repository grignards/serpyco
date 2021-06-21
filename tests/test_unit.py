# -*- coding: utf-8 -*-

import dataclasses
import datetime
import enum
import json
import re
import typing
import uuid
from unittest import mock

import pytest

import serpyco

iso8601_pattern = (
    r"^[0-9]{4}-[0-9][0-9]-[0-9][0-9]T"  # YYYY-MM-DD
    r"[0-9][0-9]:[0-9][0-9]:[0-9][0-9](\.[0-9]+)"  # HH:mm:ss.ssss
    r"?(([+-][0-9][0-9]:[0-9][0-9])|Z)?$"  # timezone
)


class Enum(enum.Enum):
    """
    An enumerate.
    """

    ONE = 1
    TWO = 2


@dataclasses.dataclass
class Simple:
    """
    Basic class.
    """

    name: str


@dataclasses.dataclass
class Types:
    """
    Testing class for supported serializer types.
    """

    integer: int
    string: str
    number: float
    boolean: bool
    enum_: Enum
    uid: uuid.UUID
    items: typing.List[str]
    nested: Simple
    nesteds: typing.List[Simple]
    mapping: typing.Dict[str, str]
    datetime_: datetime.datetime
    optional: typing.Optional[int] = None


@pytest.fixture
def types_object() -> Types:
    return Types(
        integer=42,
        string="foo",
        number=12.34,
        boolean=True,
        enum_=Enum.TWO,
        uid=uuid.UUID("12345678123456781234567812345678"),
        items=["one", "two"],
        nested=Simple(name="bar"),
        nesteds=[Simple(name="hello"), Simple(name="world")],
        mapping={"foo": "bar"},
        datetime_=datetime.datetime(2018, 11, 1, 14, 23, 43, 123456),
    )


@dataclasses.dataclass
class First:
    """Circular reference test class"""

    second: "Second"


@dataclasses.dataclass
class Second:
    """Circular reference test class"""

    first: First


@dataclasses.dataclass
class TreeNode:
    """Circular reference test class"""

    sub_nodes: typing.List["TreeNode"]


def test_unit__dump__ok__nominal_case(types_object: Types) -> None:
    serializer = serpyco.Serializer(Types)
    assert {
        "integer": 42,
        "string": "foo",
        "number": 12.34,
        "boolean": True,
        "enum_": 2,
        "uid": "12345678-1234-5678-1234-567812345678",
        "items": ["one", "two"],
        "nested": {"name": "bar"},
        "nesteds": [{"name": "hello"}, {"name": "world"}],
        "mapping": {"foo": "bar"},
        "optional": None,
        "datetime_": "2018-11-01T14:23:43.123456",
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
            "uid": "12345678-1234-5678-1234-567812345678",
            "items": ["one", "two"],
            "nested": {"name": "bar"},
            "nesteds": [{"name": "hello"}, {"name": "world"}],
            "mapping": {"foo": "bar"},
            "datetime_": "2018-11-01T14:23:43.123456",
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
                "uid": "12345678-1234-5678-1234-567812345678",
                "items": ["one", "two"],
                "nested": {"name": "bar"},
                "nesteds": [{"name": "hello"}, {"name": "world"}],
                "mapping": {"foo": "bar"},
                "datetime_": "2018-11-01T14:23:43.123456",
            }
        )
    )


def test_unit__from_dump__ok__with_many(types_object: Types) -> None:
    serializer = serpyco.Serializer(Types)

    data = serializer.dump([types_object, types_object], many=True)

    assert [types_object, types_object] == serializer.load(data, many=True)


def test_unit__from_dump_json__ok__with_many(types_object: Types) -> None:
    serializer = serpyco.Serializer(Types)

    data = serializer.dump_json([types_object, types_object], many=True)

    assert [types_object, types_object] == serializer.load_json(data, many=True)


def test_unit__json_schema__ok__nominal_case() -> None:
    serializer = serpyco.Serializer(Types)
    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "comment": "test_unit.Types",
        "definitions": {
            "test_unit.Simple": {
                "comment": "test_unit.Simple",
                "description": "Basic class.",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
                "additionalProperties": True,
                "type": "object",
            }
        },
        "description": "Testing class for supported serializer types.",
        "properties": {
            "boolean": {"type": "boolean"},
            "datetime_": {
                "format": "date-time",
                "type": "string",
                "pattern": iso8601_pattern,
            },
            "enum_": {
                "description": "An enumerate.",
                "enum": [1, 2],
                "type": "integer",
            },
            "uid": {"type": "string", "format": "uuid"},
            "integer": {"type": "integer"},
            "items": {"items": {"type": "string"}, "type": "array"},
            "mapping": {"additionalProperties": {"type": "string"}, "type": "object"},
            "nested": {"$ref": "#/definitions/test_unit.Simple"},
            "nesteds": {
                "items": {"$ref": "#/definitions/test_unit.Simple"},
                "type": "array",
            },
            "number": {"type": "number"},
            "optional": {
                "anyOf": [{"type": "integer"}, {"type": "null"}],
                "default": None,
            },
            "string": {"type": "string"},
        },
        "required": [
            "integer",
            "string",
            "number",
            "boolean",
            "enum_",
            "uid",
            "items",
            "nested",
            "nesteds",
            "mapping",
            "datetime_",
        ],
        "additionalProperties": True,
        "type": "object",
    } == serializer.json_schema(many=False)


def test_unit__json_schema__ok__with_many() -> None:
    serializer = serpyco.Serializer(Types)
    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "definitions": {
            "test_unit.Simple": {
                "comment": "test_unit.Simple",
                "description": "Basic class.",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
                "type": "object",
                "additionalProperties": True,
            }
        },
        "items": {
            "comment": "test_unit.Types",
            "description": "Testing class for supported serializer types.",
            "properties": {
                "boolean": {"type": "boolean"},
                "datetime_": {
                    "format": "date-time",
                    "type": "string",
                    "pattern": iso8601_pattern,
                },
                "enum_": {
                    "description": "An enumerate.",
                    "enum": [1, 2],
                    "type": "integer",
                },
                "uid": {"type": "string", "format": "uuid"},
                "integer": {"type": "integer"},
                "items": {"items": {"type": "string"}, "type": "array"},
                "mapping": {
                    "additionalProperties": {"type": "string"},
                    "type": "object",
                },
                "nested": {"$ref": "#/definitions/test_unit.Simple"},
                "nesteds": {
                    "items": {"$ref": "#/definitions/test_unit.Simple"},
                    "type": "array",
                },
                "number": {"type": "number"},
                "optional": {
                    "anyOf": [{"type": "integer"}, {"type": "null"}],
                    "default": None,
                },
                "string": {"type": "string"},
            },
            "required": [
                "integer",
                "string",
                "number",
                "boolean",
                "enum_",
                "uid",
                "items",
                "nested",
                "nesteds",
                "mapping",
                "datetime_",
            ],
            "additionalProperties": True,
            "type": "object",
        },
        "type": "array",
    } == serializer.json_schema(many=True)


def test_unit__json_schema__ok__circular_reference() -> None:
    builder = serpyco.SchemaBuilder(First)
    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "comment": "test_unit.First",
        "definitions": {
            "test_unit.Second": {
                "comment": "test_unit.Second",
                "description": "Circular reference test class",
                "properties": {"first": {"$ref": "#"}},
                "required": ["first"],
                "type": "object",
                "additionalProperties": True,
            }
        },
        "description": "Circular reference test class",
        "properties": {"second": {"$ref": "#/definitions/test_unit.Second"}},
        "required": ["second"],
        "additionalProperties": True,
        "type": "object",
    } == builder.json_schema()
    nested = builder.nested_builders()
    assert 1 == len(nested)
    assert "test_unit.Second" == nested[0][0]
    assert isinstance(nested[0][1], serpyco.SchemaBuilder)


def test_unit__json_schema__ok__circular_reference_one_class() -> None:
    builder = serpyco.SchemaBuilder(TreeNode)
    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "comment": "test_unit.TreeNode",
        "definitions": {},
        "description": "Circular reference test class",
        "properties": {"sub_nodes": {"items": {"$ref": "#"}, "type": "array"}},
        "required": ["sub_nodes"],
        "additionalProperties": True,
        "type": "object",
    } == builder.json_schema()


def test_unit__dump_json__ok__validate() -> None:
    serializer = serpyco.Serializer(Simple)

    assert serializer.dump(Simple(name="foo"), validate=True)
    assert serializer.dump_json(Simple(name="foo"), validate=True)

    with pytest.raises(serpyco.ValidationError):
        serializer.dump(Simple(name=42), validate=True)  # type: ignore
    with pytest.raises(serpyco.ValidationError):
        serializer.dump_json(Simple(name=42), validate=True)  # type: ignore


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
    class WithUnion:
        """Union test class"""

        foo: typing.Union[str, int]

    serializer = serpyco.Serializer(WithUnion)

    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "comment": "test_unit.WithUnion",
        "definitions": {},
        "description": "Union test class",
        "properties": {"foo": {"anyOf": [{"type": "string"}, {"type": "integer"}]}},
        "required": ["foo"],
        "type": "object",
        "additionalProperties": True,
    } == serializer.json_schema()

    assert {"foo": 42} == serializer.dump(WithUnion(foo=42), validate=True)
    assert {"foo": "bar"} == serializer.dump(WithUnion(foo="bar"), validate=True)
    assert WithUnion(foo="bar") == serializer.load({"foo": "bar"})
    with pytest.raises(serpyco.ValidationError):
        serializer.dump(WithUnion(foo=12.34), validate=True)  # type: ignore
    with pytest.raises(serpyco.ValidationError):
        serializer.load({"foo": 12.34})


def test_unit__tuple__ok__nominal_case() -> None:
    @dataclasses.dataclass
    class WithTuple:
        """Tuple test class"""

        tuple_: typing.Tuple[str, int]

    serializer = serpyco.Serializer(WithTuple)
    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "comment": "test_unit.WithTuple",
        "definitions": {},
        "description": "Tuple test class",
        "properties": {
            "tuple_": {
                "type": "array",
                "items": [{"type": "string"}, {"type": "integer"}],
                "minItems": 2,
                "maxItems": 2,
            }
        },
        "required": ["tuple_"],
        "additionalProperties": True,
        "type": "object",
    } == serializer.json_schema()
    assert WithTuple(tuple_=("foo", 1)) == serializer.load({"tuple_": ["foo", 1]})


def test_unit__uniform_tuple__ok__nominal_case() -> None:
    @dataclasses.dataclass
    class WithTuple:
        """Tuple test class"""

        tuple_: typing.Tuple[str, ...]

    serializer = serpyco.Serializer(WithTuple)
    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "comment": "test_unit.WithTuple",
        "definitions": {},
        "description": "Tuple test class",
        "properties": {"tuple_": {"type": "array", "items": {"type": "string"}}},
        "required": ["tuple_"],
        "type": "object",
        "additionalProperties": True,
    } == serializer.json_schema()
    assert WithTuple(tuple_=("foo", "bar")) == serializer.load(
        {"tuple_": ["foo", "bar"]}
    )


def test_unit__set__ok__nominal_case() -> None:
    @dataclasses.dataclass
    class WithSet:
        """Set test class"""

        set_: typing.Set[str]

    serializer = serpyco.Serializer(WithSet)

    assert WithSet(set_={"foo", "bar"}) == serializer.load({"set_": ["foo", "bar"]})


def test_unit__string_field_format_and_validators__ok__nominal_case() -> None:
    email = mock.Mock()
    datetime_ = mock.Mock()

    @dataclasses.dataclass
    class Nested:
        """Nested"""

        name: str = serpyco.string_field(
            format_=serpyco.StringFormat.DATETIME, validator=datetime_
        )

    @dataclasses.dataclass
    class WithStringField:
        """String field test class"""

        foo: str = serpyco.string_field(
            format_=serpyco.StringFormat.EMAIL,
            validator=email,
            pattern="^[A-Z]",
            min_length=3,
            max_length=24,
        )
        nested: Nested  # type:ignore

    serializer = serpyco.Serializer(WithStringField)

    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "comment": "test_unit.WithStringField",
        "description": "String field test class",
        "definitions": {
            "test_unit.Nested": {
                "comment": "test_unit.Nested",
                "description": "Nested",
                "properties": {"name": {"type": "string", "format": "date-time"}},
                "required": ["name"],
                "type": "object",
                "additionalProperties": True,
            }
        },
        "properties": {
            "foo": {
                "type": "string",
                "format": "email",
                "pattern": "^[A-Z]",
                "minLength": 3,
                "maxLength": 24,
            },
            "nested": {"$ref": "#/definitions/test_unit.Nested"},
        },
        "required": ["foo", "nested"],
        "type": "object",
        "additionalProperties": True,
    } == serializer.json_schema()

    assert serializer.load({"foo": "Foo@foo.bar", "nested": {"name": "foo"}})
    email.assert_called_once_with("Foo@foo.bar")
    datetime_.assert_called_once_with("foo")


def test_unit__number_field__ok__nominal_case() -> None:
    @dataclasses.dataclass
    class WithNumberField:
        """Number field test class"""

        foo: int = serpyco.number_field(minimum=0, maximum=12)

    serializer = serpyco.Serializer(WithNumberField)

    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "comment": "test_unit.WithNumberField",
        "definitions": {},
        "description": "Number field test class",
        "properties": {"foo": {"type": "integer", "minimum": 0, "maximum": 12}},
        "required": ["foo"],
        "type": "object",
        "additionalProperties": True,
    } == serializer.json_schema()

    assert serializer.load({"foo": 5})


def test_unit__field_dict_key__ok__nominal_case() -> None:
    @dataclasses.dataclass
    class WithDictKeyField:
        """Dict key test class"""

        foo: str = serpyco.field(dict_key="bar")

    serializer = serpyco.Serializer(WithDictKeyField)
    assert {"bar": "hello"} == serializer.dump(WithDictKeyField(foo="hello"))
    assert WithDictKeyField(foo="hello") == serializer.load({"bar": "hello"})


def test_unit__type_encoders__ok__nominal_case() -> None:
    class Encoder(serpyco.FieldEncoder):
        def json_schema(self) -> dict:
            return {}

        def dump(self, value):
            return "foo"

    serializer = serpyco.Serializer(Simple, type_encoders={str: Encoder()})

    assert {"name": "foo"} == serializer.dump(Simple(name="bar"))
    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "comment": "test_unit.Simple",
        "description": "Basic class.",
        "definitions": {},
        "properties": {"name": {}},
        "required": ["name"],
        "type": "object",
        "additionalProperties": True,
    } == serializer.json_schema()

    second = serpyco.Serializer(Simple)
    assert {"name": "bar"} == second.dump(Simple(name="bar"))
    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "comment": "test_unit.Simple",
        "description": "Basic class.",
        "definitions": {},
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
        "type": "object",
        "additionalProperties": True,
    } == second.json_schema()

    @dataclasses.dataclass
    class Nest:
        """Nest"""

        name: str
        nested: Simple = serpyco.nested_field(type_encoders={str: Encoder()})

    serializer = serpyco.Serializer(Nest)
    assert {"name": "bar", "nested": {"name": "foo"}} == serializer.dump(
        Nest(name="bar", nested=Simple("bar"))
    )
    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "comment": "test_unit.Nest",
        "description": "Nest",
        "definitions": {
            "test_unit.Simple": {
                "comment": "test_unit.Simple",
                "description": "Basic class.",
                "properties": {"name": {}},
                "required": ["name"],
                "type": "object",
                "additionalProperties": True,
            }
        },
        "properties": {
            "name": {"type": "string"},
            "nested": {"$ref": "#/definitions/test_unit.Simple"},
        },
        "required": ["name", "nested"],
        "type": "object",
        "additionalProperties": True,
    } == serializer.json_schema()


def test_unit__global_type_encoders__ok__nominal_case() -> None:
    class Encoder(serpyco.FieldEncoder):
        def json_schema(self) -> dict:
            return {}

        def dump(self, value):
            return "foo"

    serpyco.Serializer.register_global_type(str, Encoder())

    serializer = serpyco.Serializer(Simple)

    assert {"name": "foo"} == serializer.dump(Simple(name="bar"))
    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "comment": "test_unit.Simple",
        "description": "Basic class.",
        "definitions": {},
        "properties": {"name": {}},
        "required": ["name"],
        "type": "object",
        "additionalProperties": True,
    } == serializer.json_schema()

    second = serpyco.Serializer(Simple)
    assert {"name": "foo"} == second.dump(Simple(name="bar"))
    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "comment": "test_unit.Simple",
        "description": "Basic class.",
        "definitions": {},
        "properties": {"name": {}},
        "required": ["name"],
        "type": "object",
        "additionalProperties": True,
    } == second.json_schema()

    serpyco.Serializer.unregister_global_type(str)

    third = serpyco.Serializer(Simple)
    assert {"name": "bar"} == third.dump(Simple(name="bar"))
    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "comment": "test_unit.Simple",
        "description": "Basic class.",
        "definitions": {},
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
        "type": "object",
        "additionalProperties": True,
    } == third.json_schema()


def test_unit__ignore__ok__nominal_case():
    @dataclasses.dataclass
    class Ignore:
        """Ignore test class"""

        foo: str = serpyco.field(ignore=True)

    serializer = serpyco.Serializer(Ignore)
    assert {} == serializer.dump(Ignore(foo="bar"))
    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "comment": "test_unit.Ignore",
        "description": "Ignore test class",
        "definitions": {},
        "properties": {},
        "type": "object",
        "additionalProperties": True,
        "required": [],
    } == serializer.json_schema()


def test_unit__only__ok__nominal_case():
    @dataclasses.dataclass
    class Only:
        """Only test class"""

        foo: str
        bar: str

    serializer = serpyco.Serializer(Only, only=["foo"])
    assert {"foo": "bar"} == serializer.dump(Only(foo="bar", bar="foo"))
    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "comment": "test_unit.Only",
        "description": "Only test class",
        "definitions": {},
        "properties": {"foo": {"type": "string"}},
        "required": ["foo"],
        "type": "object",
        "additionalProperties": True,
    } == serializer.json_schema()


def test_unit__field_description_and_examples__ok__nominal_case():
    @dataclasses.dataclass
    class Desc:
        """Description test class"""

        foo: str = serpyco.field(
            description="This is a foo", examples=["can be foo", "or bar"]
        )

    serializer = serpyco.Serializer(Desc)
    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "comment": "test_unit.Desc",
        "definitions": {},
        "description": "Description test class",
        "properties": {
            "foo": {
                "description": "This is a foo",
                "examples": ["can be foo", "or bar"],
                "type": "string",
            }
        },
        "required": ["foo"],
        "type": "object",
        "additionalProperties": True,
    } == serializer.json_schema()


def test_unit__field_default__ok__nominal_case():
    @dataclasses.dataclass
    class Desc:
        """Description test class"""

        foo: str = "foo"
        bar: str = dataclasses.field(default_factory=lambda: "bar")
        datetime_: datetime.datetime = datetime.datetime(2018, 11, 24, 19, 0, 0, 0)

    serializer = serpyco.Serializer(Desc)
    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "comment": "test_unit.Desc",
        "definitions": {},
        "description": "Description test class",
        "properties": {
            "foo": {"default": "foo", "type": "string"},
            "bar": {"type": "string"},
            "datetime_": {
                "default": "2018-11-24T19:00:00",
                "type": "string",
                "format": "date-time",
                "pattern": iso8601_pattern,
            },
        },
        "type": "object",
        "additionalProperties": True,
        "required": [],
    } == serializer.json_schema()


def test_unit__decorators__ok__nominal_case():
    @dataclasses.dataclass
    class Decorated:
        foo: typing.Optional[str]
        bar: int

        @staticmethod
        @serpyco.pre_dump
        def add_two_to_bar(obj: "Decorated") -> "Decorated":
            obj.bar += 2
            return obj

        @staticmethod
        @serpyco.post_dump
        def del_foo_key(data: dict) -> dict:
            del data["foo"]
            return data

        @staticmethod
        @serpyco.pre_load
        def add_foo_if_missing(data: dict) -> dict:
            if "foo" not in data:
                data["foo"] = "default"
            return data

        @staticmethod
        @serpyco.post_load
        def substract_two_from_bar(obj: "Decorated") -> "Decorated":
            obj.bar -= 2
            return obj

    serializer = serpyco.Serializer(Decorated)

    assert {"bar": 5} == serializer.dump(Decorated(foo="hello", bar=3))

    assert '{"bar":5}' == serializer.dump_json(Decorated(foo="hello", bar=3))

    assert Decorated(foo="default", bar=1) == serializer.load({"bar": 3})

    assert Decorated(foo="default", bar=1) == serializer.load_json('{"bar":3}')


def test_unit__exclude__ok__nominal_case():
    @dataclasses.dataclass
    class Exclude:
        """Exclude test class"""

        foo: str
        bar: str

    serializer = serpyco.Serializer(Exclude, exclude=["foo"])
    assert {"bar": "foo"} == serializer.dump(Exclude(foo="bar", bar="foo"))
    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "comment": "test_unit.Exclude",
        "description": "Exclude test class",
        "definitions": {},
        "properties": {"bar": {"type": "string"}},
        "required": ["bar"],
        "type": "object",
        "additionalProperties": True,
    } == serializer.json_schema()


def test_unit__nested_field__ok__nominal_case():
    @dataclasses.dataclass
    class Nested:
        """Nested test class"""

        foo: str
        bar: str

    @dataclasses.dataclass
    class Parent:
        """Parent test class"""

        first: Nested = serpyco.nested_field(only=["foo"])
        second: Nested = serpyco.nested_field(exclude=["foo"])

    serializer = serpyco.Serializer(Parent)
    assert {"first": {"foo": "foo"}, "second": {"bar": "bar"}} == serializer.dump(
        Parent(first=Nested(foo="foo", bar="bar"), second=Nested(foo="foo", bar="bar"))
    )
    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "comment": "test_unit.Parent",
        "description": "Parent test class",
        "definitions": {
            "test_unit.Nested_exclude_foo": {
                "type": "object",
                "additionalProperties": True,
                "comment": "test_unit.Nested",
                "description": "Nested test class",
                "properties": {"bar": {"type": "string"}},
                "required": ["bar"],
            },
            "test_unit.Nested_exclude_bar": {
                "type": "object",
                "additionalProperties": True,
                "comment": "test_unit.Nested",
                "description": "Nested test class",
                "properties": {"foo": {"type": "string"}},
                "required": ["foo"],
            },
        },
        "properties": {
            "first": {"$ref": "#/definitions/test_unit.Nested_exclude_bar"},
            "second": {"$ref": "#/definitions/test_unit.Nested_exclude_foo"},
        },
        "required": ["first", "second"],
        "type": "object",
        "additionalProperties": True,
    } == serializer.json_schema()


def test_unit__get_dict_object_path__ok__nominal_case():
    @dataclasses.dataclass
    class Nested:
        foo: str = serpyco.field(dict_key="bar")

    @dataclasses.dataclass
    class Parent:
        nested: Nested = serpyco.field(dict_key="n")
        nesteds: typing.List[Nested] = serpyco.field(dict_key="ns")
        mapped: typing.Dict[str, Nested] = serpyco.field(dict_key="mp")

    serializer = serpyco.Serializer(Parent)

    assert ["n", "bar"] == serializer.get_dict_path(["nested", "foo"])
    assert ["nested", "foo"] == serializer.get_object_path(["n", "bar"])
    assert ["ns", "bar"] == serializer.get_dict_path(["nesteds", "foo"])
    assert ["nesteds", "foo"] == serializer.get_object_path(["ns", "bar"])
    assert ["mp", "bar"] == serializer.get_dict_path(["mapped", "foo"])
    assert ["mapped", "foo"] == serializer.get_object_path(["mp", "bar"])


def test_unit__dict_encoder__ok__nominal_case():
    class CustomEncoder(serpyco.FieldEncoder):
        def dump(self, value):
            return value

        def load(self, value):
            return value

    @dataclasses.dataclass
    class Nested:
        foo: str

    @dataclasses.dataclass
    class Parent:
        mapping: typing.Dict[str, Nested]
        custom: typing.Dict[int, Nested]

    serializer = serpyco.Serializer(Parent, type_encoders={int: CustomEncoder()})
    assert {
        "mapping": {"foo": {"foo": "bar"}},
        "custom": {42: {"foo": "foo"}},
    } == serializer.dump(
        Parent(mapping={"foo": Nested(foo="bar")}, custom={42: Nested(foo="foo")})
    )


def test_unit__rapidjson_validator__err_message():
    @dataclasses.dataclass
    class Foo:
        name: str

    val = serpyco.validator.RapidJsonValidator(serpyco.SchemaBuilder(Foo))
    with pytest.raises(
        serpyco.ValidationError,
        match=r'value "42" at path "#/name" has type "int", expected "string"',
    ):
        val.validate({"name": 42})


def test_unit__field_cast_on_load__ok__nominal_case():
    @dataclasses.dataclass
    class CastOnLoad:
        value: int = serpyco.field(cast_on_load=True)

    serializer = serpyco.Serializer(CastOnLoad)
    assert CastOnLoad(value=42) == serializer.load({"value": "42"})


def test_unit__field_cast_on_load__err_exception_during_casting():
    @dataclasses.dataclass
    class CastOnLoad:
        value: int = serpyco.field(cast_on_load=True)

    serializer = serpyco.Serializer(CastOnLoad)
    with pytest.raises(serpyco.ValidationError):
        serializer.load({"value": "hello"})


def test_unit__custom_definition_name__ok__nominal_case():
    @dataclasses.dataclass
    class Nested:
        """Nested"""

        value: int

    @dataclasses.dataclass
    class Class:
        """Class"""

        nested: Nested

    get_definition_name = mock.Mock(return_value="Custom")
    builder = serpyco.SchemaBuilder(Class, get_definition_name=get_definition_name)

    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "comment": "test_unit.Class",
        "definitions": {
            "Custom": {
                "comment": "test_unit.Nested",
                "description": "Nested",
                "properties": {"value": {"type": "integer"}},
                "required": ["value"],
                "type": "object",
                "additionalProperties": True,
            }
        },
        "description": "Class",
        "properties": {"nested": {"$ref": "#/definitions/Custom"}},
        "required": ["nested"],
        "type": "object",
        "additionalProperties": True,
    } == builder.json_schema()
    get_definition_name.assert_called_with(Nested, (), [])


def test_unit__not_init_fields__ok__nominal_case():
    @dataclasses.dataclass
    class Class:
        """Class"""

        one: str
        two: int = dataclasses.field(init=False)

    serializer = serpyco.Serializer(Class)
    obj = Class(one="hello")
    obj.two = 12
    assert obj == serializer.load({"one": "hello", "two": 12})
    assert {"one": "hello", "two": 12} == serializer.dump(obj)


def test_unit__schema__ok__with_default_dataclass():
    @dataclasses.dataclass
    class Nested:
        """Nested"""

        name: str = "Hello"

    @dataclasses.dataclass
    class Class:
        """Class"""

        one: str
        nested: Nested = dataclasses.field(default_factory=Nested)

    serializer = serpyco.Serializer(Class)
    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "comment": "test_unit.Class",
        "definitions": {
            "test_unit.Nested": {
                "comment": "test_unit.Nested",
                "description": "Nested",
                "properties": {"name": {"default": "Hello", "type": "string"}},
                "type": "object",
                "additionalProperties": True,
                "required": [],
            }
        },
        "description": "Class",
        "properties": {
            "nested": {"$ref": "#/definitions/test_unit.Nested"},
            "one": {"type": "string"},
        },
        "required": ["one"],
        "type": "object",
        "additionalProperties": True,
    } == serializer.json_schema()


def test_unit__generic_dataclass__ok__nominal_case():
    T = typing.TypeVar("T")

    @dataclasses.dataclass
    class Gen(typing.Generic[T]):
        "Generic."
        foo: str
        bar: T

    serializer = serpyco.Serializer(Gen[int])
    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "comment": "test_unit.Gen",
        "definitions": {},
        "description": "Generic.",
        "properties": {"bar": {"type": "integer"}, "foo": {"type": "string"}},
        "required": ["foo", "bar"],
        "type": "object",
        "additionalProperties": True,
    } == serializer.json_schema()

    @dataclasses.dataclass
    class WithGen:
        "With a generic."
        nested: Gen[int]

    serializer = serpyco.Serializer(WithGen)
    assert {
        "comment": "test_unit.WithGen",
        "$schema": "http://json-schema.org/draft-04/schema#",
        "definitions": {
            "test_unit.Gen[int]": {
                "comment": "test_unit.Gen",
                "description": "Generic.",
                "properties": {"bar": {"type": "integer"}, "foo": {"type": "string"}},
                "required": ["foo", "bar"],
                "type": "object",
                "additionalProperties": True,
            }
        },
        "description": "With a generic.",
        "properties": {"nested": {"$ref": "#/definitions/test_unit.Gen[int]"}},
        "required": ["nested"],
        "type": "object",
        "additionalProperties": True,
    } == serializer.json_schema()
    assert WithGen(nested=Gen(foo="bar", bar=12)) == serializer.load(
        {"nested": {"foo": "bar", "bar": 12}}
    )

    @dataclasses.dataclass(init=False)
    class SList(typing.Generic[T]):
        """List."""

        items: typing.List[T]
        item_nb: int

        def __init__(self, items: typing.List[T]) -> None:
            self.items = items
            self.item_nb = len(items)

    serializer = serpyco.Serializer(SList[int])
    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "comment": "test_unit.SList",
        "definitions": {},
        "description": "List.",
        "properties": {
            "item_nb": {"type": "integer"},
            "items": {"items": {"type": "integer"}, "type": "array"},
        },
        "required": ["items", "item_nb"],
        "type": "object",
        "additionalProperties": True,
    } == serializer.json_schema()
    assert {"items": [0, 1], "item_nb": 2} == serializer.dump(SList([0, 1]))


def test_unit__schema__ok__none_default():
    @dataclasses.dataclass
    class Def:
        """Def."""

        foo: typing.Optional[int] = None

    serializer = serpyco.Serializer(Def)
    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "comment": "test_unit.Def",
        "definitions": {},
        "description": "Def.",
        "properties": {
            "foo": {"anyOf": [{"type": "integer"}, {"type": "null"}], "default": None}
        },
        "type": "object",
        "required": [],
        "additionalProperties": True,
    } == serializer.json_schema()


def test_unit__union_field_encoder__ok__nominal_case():

    dummy = mock.Mock()
    dummy.load.side_effect = lambda v: int(v)
    dummy_raise_at_load = mock.Mock()
    dummy_raise_at_load.load.side_effect = Exception
    encoder = serpyco.serializer.UnionFieldEncoder(
        [(int, dummy), (str, dummy_raise_at_load)]
    )
    encoder.dump(42)
    dummy.dump.assert_called_once_with(42)
    dummy_raise_at_load.dump.assert_not_called

    encoder.load(42)
    dummy.load.assert_called_once_with(42)
    dummy_raise_at_load.load.assert_not_called

    dummy.load.reset_mock()
    with pytest.raises(serpyco.ValidationError):
        encoder.load("hello")
        dummy.load.assert_called_once_with("hello")
        dummy_raise_at_load.load.assert_called_once_with("hello")


def test_unit__union_field_encoder__err__validation_error():

    dummy_raise_at_load = mock.Mock()
    dummy_raise_at_load.load.side_effect = Exception
    encoder = serpyco.serializer.UnionFieldEncoder(
        [(int, dummy_raise_at_load), (str, dummy_raise_at_load)]
    )
    with pytest.raises(serpyco.ValidationError):
        encoder.load("hello")


def test_unit__optional__custom_encoder__ok__nominal_case():
    @dataclasses.dataclass
    class OptionalCustom:
        """OptionalCustom."""

        name: typing.Optional[str]

    class CustomEncoder(serpyco.FieldEncoder):
        def json_schema(self):
            return {"type": "string"}

    serializer = serpyco.Serializer(
        OptionalCustom, type_encoders={str: CustomEncoder()}
    )

    assert serializer.json_schema() == {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "comment": "test_unit.OptionalCustom",
        "definitions": {},
        "description": "OptionalCustom.",
        "properties": {"name": {"anyOf": [{"type": "string"}, {"type": "null"}]}},
        "type": "object",
        "additionalProperties": True,
        "required": ["name"],
    }


def test_unit__serializer__err__nested_not_dataclass():
    class Nested:
        pass

    @dataclasses.dataclass
    class Foo:
        n: Nested

    with pytest.raises(serpyco.NoEncoderError):
        serpyco.Serializer(Foo)

    with pytest.raises(serpyco.SchemaError):
        b = serpyco.SchemaBuilder(Foo)
        b._create_json_schema()


def test_unit__schema__ok__allowed_values():
    @dataclasses.dataclass
    class WithAllowedValues:
        """WithAllowedValues."""

        foo: int = serpyco.number_field(allowed_values=[1, 2, 3])

    serializer = serpyco.Serializer(WithAllowedValues)

    assert serializer.json_schema() == {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "comment": "test_unit.WithAllowedValues",
        "definitions": {},
        "description": "WithAllowedValues.",
        "properties": {"foo": {"type": "integer", "enum": [1, 2, 3]}},
        "required": ["foo"],
        "type": "object",
        "additionalProperties": True,
    }


def test_unit__schema__ok__allowed_values_with_enum():
    class Enumerate(enum.Enum):
        """Enum."""

        ONE = 1
        TWO = 2
        THREE = 3

    @dataclasses.dataclass
    class WithAllowedValues:
        """WithAllowedValues."""

        foo: Enumerate = serpyco.field(allowed_values=[Enumerate.ONE, Enumerate.TWO])

    serializer = serpyco.Serializer(WithAllowedValues)

    assert serializer.json_schema() == {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "comment": "test_unit.WithAllowedValues",
        "definitions": {},
        "description": "WithAllowedValues.",
        "properties": {
            "foo": {"type": "integer", "enum": [1, 2], "description": "Enum."}
        },
        "required": ["foo"],
        "type": "object",
        "additionalProperties": True,
    }


def test_unit__cast_on_load__ok__with_optional():
    @dataclasses.dataclass
    class OptionalCastOnLoad:
        foo: typing.Optional[int] = serpyco.field(cast_on_load=True)

    serializer = serpyco.Serializer(OptionalCastOnLoad)

    assert OptionalCastOnLoad(foo=2) == serializer.load({"foo": "2"})


def test_unit__dict__ok__with_field_encoder():
    class NeedFieldEncoder(str, enum.Enum):
        FOO = "FOO"
        BAR = "BAR"

    @dataclasses.dataclass
    class WithFieldEncoder:
        foo: typing.Dict[str, NeedFieldEncoder]
        bar: typing.Dict[NeedFieldEncoder, str]
        foobar: typing.Dict[NeedFieldEncoder, NeedFieldEncoder]

    serializer = serpyco.Serializer(WithFieldEncoder)

    obj = WithFieldEncoder(
        foo={"f": NeedFieldEncoder.FOO},
        bar={NeedFieldEncoder.BAR: "b"},
        foobar={NeedFieldEncoder.FOO: NeedFieldEncoder.BAR},
    )

    dict_ = {"foo": {"f": "FOO"}, "bar": {"BAR": "b"}, "foobar": {"FOO": "BAR"}}

    assert serializer.dump(obj) == dict_

    assert serializer.load(dict_) == obj


def test_unit__optional__ok__with_validator():
    validate = mock.Mock()

    @dataclasses.dataclass
    class WithVal:
        foo: typing.Optional[str] = serpyco.field(validator=validate, default="bar")

    serializer = serpyco.Serializer(WithVal)

    assert serializer.load({}) == WithVal()
    validate.assert_not_called()


def test_unit__optional__err__validation_error_message():
    @dataclasses.dataclass
    class Opt:
        foo: typing.Optional[str] = serpyco.string_field(min_length=5)

    serializer = serpyco.Serializer(Opt)

    with pytest.raises(
        serpyco.ValidationError,
        match=re.escape(
            r'value "bar" at path "#/foo" must have its length >= 5 but length is 3'
        ),
    ):
        serializer.load({"foo": "bar"})


def test_unit__embedded_dataclass_list__ok__with_validator():

    validator = mock.Mock()

    @dataclasses.dataclass
    class Foo:
        bar: str = serpyco.field(validator=validator)

    @dataclasses.dataclass
    class ListFoo:
        foos: typing.List[Foo]

    serializer = serpyco.Serializer(ListFoo)
    serializer.load({"foos": [{"bar": "hello"}, {"bar": "world"}]})
    assert 2 == validator.call_count


def test_unit__validation__ok__several_errors():
    @dataclasses.dataclass
    class Foo:
        bar: str
        foo: int

    serializer = serpyco.Serializer(Foo)
    with pytest.raises(
        serpyco.ValidationError,
        match=re.escape(
            r'- value "12" at path "#/bar" has type "int", expected "string"\n'
            r'- value "hello" at path "#/foo" has type "str", expected "integer"'
        ),
    ):
        serializer.load({"bar": 12, "foo": "hello"})


def test_unit__validation__ok__empty_content():
    @dataclasses.dataclass
    class Foo:
        bar: str

    with pytest.raises(serpyco.ValidationError):
        serpyco.Serializer(Foo).load({})


def test_unit__validation_error_message__err__optional_sub_dataclass():
    @dataclasses.dataclass
    class Foo:
        bar: str

    @dataclasses.dataclass
    class Bar:
        hello: int
        foo: typing.Optional[Foo]

    with pytest.raises(
        serpyco.ValidationError,
        match=re.escape(r'value "{}" at path "#/foo" must define property "bar"'),
    ):
        serpyco.Serializer(Bar).load({"hello": 42, "foo": {}})


def test_unit__strict_validation__err__additional_property():
    @dataclasses.dataclass
    class Foo:
        bar: str

    serializer = serpyco.Serializer(Foo, strict=True)
    with pytest.raises(
        serpyco.ValidationError,
        match=re.escape(r'properties "hello" cannot be defined'),
    ):
        serializer.load({"hello": 42, "bar": "foo"})

    assert serializer.load({"bar": "foo"}) == Foo("foo")


def test_unit__dump_load__object_set():
    @dataclasses.dataclass
    class Bar:
        baz: str

        def __hash__(self):
            return hash(self.baz)

    @dataclasses.dataclass
    class Foo:
        bar: typing.Set[Bar]

    serializer = serpyco.Serializer(Foo)
    foo = Foo({Bar("baz")})
    assert serializer.dump(foo) == {"bar": [{"baz": "baz"}]}
    assert serializer.load({"bar": [{"baz": "baz"}]}) == foo


def test_unit__load__err__missing_parameter():
    @dataclasses.dataclass
    class Foo:
        name: str
        value: int

    serializer = serpyco.Serializer(Foo)
    with pytest.raises(TypeError):
        serializer.load({"name": "hello"}, validate=False)


def test_unit__load__ok__custom_type():
    class Bar:
        def __init__(self, id):
            self.id = id

        def __eq__(self, other):
            return isinstance(other, Bar) and other.id == self.id

    class Foo:
        def __init__(self, name, bar):
            self.name = name
            self.bar = bar

        def __eq__(self, other):
            return (
                isinstance(other, Foo)
                and other.name == self.name
                and other.bar == self.bar
            )

    @dataclasses.dataclass
    class BarSchema:
        id: int

    @dataclasses.dataclass
    class FooSchema:
        name: str
        bar: BarSchema = serpyco.nested_field(load_as_type=Bar)

    serializer = serpyco.Serializer(FooSchema, load_as_type=Foo)

    assert Foo("hello", Bar(1)) == serializer.load({"name": "hello", "bar": {"id": 1}})


def test_unit__load__ok__frozen_dataclass():
    @dataclasses.dataclass(frozen=True)
    class Frozen:
        name: str

    serializer = serpyco.Serializer(Frozen)

    assert Frozen("hello") == serializer.load({"name": "hello"})


def test_unit__ok__schema_optional_dict_dataclass():
    @dataclasses.dataclass
    class Foo:
        name: str

    @dataclasses.dataclass
    class FooDict:
        foos: typing.Optional[typing.Dict[str, Foo]]

    @dataclasses.dataclass
    class Bar:
        foo_dict: FooDict

    schema = serpyco.SchemaBuilder(Bar).json_schema()
    assert "test_unit.Foo" in list(schema["definitions"].keys())


def test_unit_load__ok__excluded_fields():
    @dataclasses.dataclass
    class Foo:
        name: str
        description: str = ""

    serializer = serpyco.Serializer(Foo, exclude=["description"])
    assert Foo(name="foo") == serializer.load(
        {"name": "foo", "description": "excluded"}
    )

    serializer = serpyco.Serializer(Foo, only=["name"])
    assert Foo(name="foo") == serializer.load(
        {"name": "foo", "description": "excluded"}
    )

    @dataclasses.dataclass
    class Bar:
        name: str
        description: str = serpyco.field(ignore=True, default="")

    serializer = serpyco.Serializer(Bar)
    assert Bar(name="foo") == serializer.load(
        {"name": "foo", "description": "excluded"}
    )


def test_unit_load__err__excluded_fields_without_default():
    @dataclasses.dataclass
    class Foo:
        name: str
        description: str

    serializer = serpyco.Serializer(Foo, exclude=["description"])
    with pytest.raises(TypeError):
        serializer.load({"name": "foo", "description": "excluded"})

    serializer = serpyco.Serializer(Foo, only=["name"])
    with pytest.raises(TypeError):
        serializer.load({"name": "foo", "description": "excluded"})

    @dataclasses.dataclass
    class Bar:
        name: str
        description: str = serpyco.field(ignore=True)

    serializer = serpyco.Serializer(Bar)
    with pytest.raises(TypeError):
        serializer.load({"name": "foo", "description": "excluded"})


def test_unit__ok__serializer_mixin():
    @dataclasses.dataclass
    class Foo(serpyco.SerializerMixin):
        name: str

    assert {"name": "Hello"} == Foo(name="Hello").dump()
    assert Foo(name="Hello") == Foo.load({"name": "Hello"})
    assert '{"name":"Hello"}' == Foo(name="Hello").dump_json()
    assert Foo(name="Hello") == Foo.load_json('{"name":"Hello"}')


def test_unit_json_schema__ok__ignore_sub_field():
    @dataclasses.dataclass
    class Bar:
        """Bar"""

        value: int
        comment: str = serpyco.field(ignore=True)

    @dataclasses.dataclass
    class Foo:
        """Foo"""

        name: str
        bar: Bar

    schema_builder = serpyco.SchemaBuilder(Foo)
    assert schema_builder.json_schema() == {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "additionalProperties": True,
        "comment": "test_unit.Foo",
        "definitions": {
            "test_unit.Bar_exclude_comment": {
                "additionalProperties": True,
                "comment": "test_unit.Bar",
                "description": "Bar",
                "properties": {"value": {"type": "integer"}},
                "required": ["value"],
                "type": "object",
            }
        },
        "description": "Foo",
        "properties": {
            "bar": {"$ref": "#/definitions/test_unit.Bar_exclude_comment"},
            "name": {"type": "string"},
        },
        "required": ["name", "bar"],
        "type": "object",
    }


def test_unit_load__ok__post_init():
    @dataclasses.dataclass
    class Foo:
        def __post_init__(self) -> None:
            self.name = "post_init_called"

        name: str

    foo = serpyco.Serializer(Foo).load({"name": "not_called"})
    assert "post_init_called" == foo.name


def test_unit_serializer__ok__ignored_not_dataclass_field():
    class Foo:
        def __init__(self) -> None:
            self.name = "Foo"

    @dataclasses.dataclass
    class Bar:
        value: int
        foo: Foo = serpyco.field(ignore=True)

    serpyco.Serializer(Bar)


def test_unit_field_description__ok__nominal_case():
    @dataclasses.dataclass
    class Foo:
        value: int = serpyco.field(description="An integer")

    schema = serpyco.SchemaBuilder(Foo).json_schema()
    assert "An integer" == schema["properties"]["value"]["description"]


def test_unit_optional_dataclass_list__ok__nominal_case():
    @dataclasses.dataclass
    class SubTest:
        value: str

    @dataclasses.dataclass
    class Test:
        value: typing.List[typing.Optional[SubTest]]

    serializer = serpyco.Serializer(Test)
    assert serializer.dump(Test([None])) == {"value": [None]}


def test_unit_union_with_none__ok__nominal_case():
    @dataclasses.dataclass
    class SubTest1:
        value1: str

    @dataclasses.dataclass
    class SubTest2:
        value2: str

    @dataclasses.dataclass
    class Test:
        value: typing.List[typing.Optional[typing.Union[SubTest1, SubTest2]]]

    serializer = serpyco.Serializer(Test)
    assert serializer.dump(Test(value=[None, SubTest1("1"), SubTest2("2")])) == {
        "value": [
            None,
            {"value1": "1"},
            {"value2": "2"},
        ]
    }


def test_unit_untyped_collections__ok__nominal_case():
    @dataclasses.dataclass
    class Untyped:
        """Untyped collection fields"""

        udict: dict
        tdict: typing.Dict
        ulist: list
        tlist: typing.List
        uset: set
        tset: typing.Set

    serializer = serpyco.Serializer(Untyped)
    assert serializer.dump(
        Untyped(
            udict={}, tdict={"foo": 1}, ulist=[], tlist=[0, 2], uset=set(), tset={0, 12}
        )
    ) == {
        "udict": {},
        "tdict": {"foo": 1},
        "ulist": [],
        "tlist": [0, 2],
        "uset": [],
        "tset": [0, 12],
    }

    assert serializer.json_schema() == {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "additionalProperties": True,
        "comment": "test_unit.Untyped",
        "definitions": {},
        "description": "Untyped collection fields",
        "properties": {
            "tdict": {"additionalProperties": {}, "type": "object"},
            "tlist": {"additionalProperties": {}, "type": "array"},
            "tset": {"additionalProperties": {}, "type": "array"},
            "udict": {"additionalProperties": {}, "type": "object"},
            "ulist": {"additionalProperties": {}, "type": "array"},
            "uset": {"additionalProperties": {}, "type": "array"},
        },
        "required": ["udict", "tdict", "ulist", "tlist", "uset", "tset"],
        "type": "object",
    }
