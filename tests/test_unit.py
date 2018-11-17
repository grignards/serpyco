# -*- coding: utf-8 -*-

import dataclasses
import datetime
import enum
import json
import typing
import uuid

import dateutil
import pytest

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
    uid: uuid.UUID
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
        uid=uuid.UUID("12345678123456781234567812345678"),
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
        "uid": "12345678-1234-5678-1234-567812345678",
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
            "uid": "12345678-1234-5678-1234-567812345678",
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
                "uid": "12345678-1234-5678-1234-567812345678",
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
            "uid": {"type": "string", "format": "uuid"},
            "integer": {"type": "integer"},
            "items": {"items": {"type": "string"}, "type": "array"},
            "mapping": {"additionalProperties": {"type": "string"}, "type": "object"},
            "nested": {"$ref": "#/definitions/Simple"},
            "nesteds": {"items": {"$ref": "#/definitions/Simple"}, "type": "array"},
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
                "uid": {"type": "string", "format": "uuid"},
                "integer": {"type": "integer"},
                "items": {"items": {"type": "string"}, "type": "array"},
                "mapping": {
                    "additionalProperties": {"type": "string"},
                    "type": "object",
                },
                "nested": {"$ref": "#/definitions/Simple"},
                "nesteds": {"items": {"$ref": "#/definitions/Simple"}, "type": "array"},
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
            "type": "object",
        },
        "type": "array",
    } == serializer.json_schema()


def test_unit__json_schema__ok__cycle() -> None:
    builder = serpyco.SchemaBuilder(First)
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
    } == builder.json_schema()
    nested = builder.nested_builders()
    assert 1 == len(nested)
    assert "Second" == nested[0][0]
    assert isinstance(nested[0][1], serpyco.SchemaBuilder)


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
    assert WithUnion(foo="bar") == serializer.load({"foo": "bar"})
    with pytest.raises(serpyco.ValidationError):
        serializer.dump(WithUnion(foo=12.34), validate=True)
    with pytest.raises(serpyco.ValidationError):
        serializer.load({"foo": 12.34})


def test_unit__tuple__ok__nominal_case() -> None:
    @dataclasses.dataclass
    class WithTuple(object):
        """Tuple test class"""

        tuple_: typing.Tuple[str]

    serializer = serpyco.Serializer(WithTuple)

    assert WithTuple(tuple_=("foo", "bar")) == serializer.load(
        {"tuple_": ["foo", "bar"]}
    )


def test_unit__set__ok__nominal_case() -> None:
    @dataclasses.dataclass
    class WithSet(object):
        """Set test class"""

        set_: typing.Set[str]

    serializer = serpyco.Serializer(WithSet)

    assert WithSet(set_={"foo", "bar"}) == serializer.load({"set_": ["foo", "bar"]})


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


def test_unit__field_dict_key__ok__nominal_case() -> None:
    @dataclasses.dataclass
    class WithDictKeyField(object):
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
        "description": "Basic class.",
        "definitions": {},
        "properties": {"name": {}},
        "required": ["name"],
        "type": "object",
    } == serializer.json_schema()

    second = serpyco.Serializer(Simple)
    assert {"name": "bar"} == second.dump(Simple(name="bar"))
    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "description": "Basic class.",
        "definitions": {},
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
        "type": "object",
    } == second.json_schema()


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
        "description": "Basic class.",
        "definitions": {},
        "properties": {"name": {}},
        "required": ["name"],
        "type": "object",
    } == serializer.json_schema()

    second = serpyco.Serializer(Simple)
    assert {"name": "foo"} == second.dump(Simple(name="bar"))
    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "description": "Basic class.",
        "definitions": {},
        "properties": {"name": {}},
        "required": ["name"],
        "type": "object",
    } == second.json_schema()

    serpyco.Serializer.unregister_global_type(str)

    third = serpyco.Serializer(Simple)
    assert {"name": "bar"} == third.dump(Simple(name="bar"))
    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "description": "Basic class.",
        "definitions": {},
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
        "type": "object",
    } == third.json_schema()


def test_unit__ignore__ok__nominal_case():
    @dataclasses.dataclass
    class Ignore(object):
        """Ignore test class"""

        foo: str = serpyco.field(ignore=True)

    serializer = serpyco.Serializer(Ignore)
    assert {} == serializer.dump(Ignore(foo="bar"))
    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "description": "Ignore test class",
        "definitions": {},
        "properties": {},
        "type": "object",
    } == serializer.json_schema()


def test_unit__only__ok__nominal_case():
    @dataclasses.dataclass
    class Only(object):
        """Only test class"""

        foo: str
        bar: str

    serializer = serpyco.Serializer(Only, only=["foo"])
    assert {"foo": "bar"} == serializer.dump(Only(foo="bar", bar="foo"))
    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "description": "Only test class",
        "definitions": {},
        "properties": {"foo": {"type": "string"}},
        "required": ["foo"],
        "type": "object",
    } == serializer.json_schema()


def test_unit__field_description_and_examples__ok__nominal_case():
    @dataclasses.dataclass
    class Desc(object):
        """Description test class"""

        foo: str = serpyco.field(
            description="This is a foo", examples=["can be foo", "or bar"]
        )

    serializer = serpyco.Serializer(Desc)
    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
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
    } == serializer.json_schema()


def test_unit__field_default__ok__nominal_case():
    @dataclasses.dataclass
    class Desc(object):
        """Description test class"""

        foo: str = "foo"
        bar: str = dataclasses.field(default_factory=lambda: "bar")
        datetime_: datetime.datetime = datetime.datetime(2018, 11, 24, 19, 0, 0, 0)

    serializer = serpyco.Serializer(Desc)
    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "definitions": {},
        "description": "Description test class",
        "properties": {
            "foo": {"default": "foo", "type": "string"},
            "bar": {"default": "bar", "type": "string"},
            "datetime_": {
                "default": "2018-11-24T19:00:00+00:00",
                "type": "string",
                "format": "date-time",
            },
        },
        "required": ["foo", "bar", "datetime_"],
        "type": "object",
    } == serializer.json_schema()


def test_unit__decorators__ok__nominal_case():
    @dataclasses.dataclass
    class Decorated(object):
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

    assert Decorated(foo="default", bar=1) == serializer.load({"bar": 3})


def test_unit__exclude__ok__nominal_case():
    @dataclasses.dataclass
    class Exclude(object):
        """Exclude test class"""

        foo: str
        bar: str

    serializer = serpyco.Serializer(Exclude, exclude=["foo"])
    assert {"bar": "foo"} == serializer.dump(Exclude(foo="bar", bar="foo"))
    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "description": "Exclude test class",
        "definitions": {},
        "properties": {"bar": {"type": "string"}},
        "required": ["bar"],
        "type": "object",
    } == serializer.json_schema()


def test_unit__nested_field__ok__nominal_case():
    @dataclasses.dataclass
    class Nested(object):
        """Nested test class"""

        foo: str
        bar: str

    @dataclasses.dataclass
    class Parent(object):
        """Parent test class"""

        first: Nested = serpyco.nested_field(only=["foo"])
        second: Nested = serpyco.nested_field(exclude=["foo"])

    serializer = serpyco.Serializer(Parent)
    assert {"first": {"foo": "foo"}, "second": {"bar": "bar"}} == serializer.dump(
        Parent(first=Nested(foo="foo", bar="bar"), second=Nested(foo="foo", bar="bar"))
    )
    assert {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "description": "Parent test class",
        "definitions": {
            "Nested_exclude_foo": {
                "type": "object",
                "description": "Nested test class",
                "properties": {"bar": {"type": "string"}},
                "required": ["bar"],
            },
            "Nested_only_foo": {
                "type": "object",
                "description": "Nested test class",
                "properties": {"foo": {"type": "string"}},
                "required": ["foo"],
            },
        },
        "properties": {
            "first": {"$ref": "#/definitions/Nested_only_foo"},
            "second": {"$ref": "#/definitions/Nested_exclude_foo"},
        },
        "required": ["first", "second"],
        "type": "object",
    } == serializer.json_schema()


def test_unit__get_dict_object_path__ok__nominal_case():
    @dataclasses.dataclass
    class Nested(object):
        foo: str = serpyco.field(dict_key="bar")

    @dataclasses.dataclass
    class Parent(object):
        nested: Nested = serpyco.field(dict_key="n")

    serializer = serpyco.Serializer(Parent)

    assert ["n", "bar"] == serializer.get_dict_path(["nested", "foo"])
    assert ["nested", "foo"] == serializer.get_object_path(["n", "bar"])


def test_unit__dict_encoder__ok__nominal_case():
    class CustomEncoder(serpyco.FieldEncoder):
        def dump(self, value):
            return value

        def load(self, value):
            return value

    @dataclasses.dataclass
    class Nested(object):
        foo: str

    @dataclasses.dataclass
    class Parent(object):
        mapping: typing.Dict[str, Nested]
        custom: typing.Dict[int, Nested]

    serializer = serpyco.Serializer(Parent, type_encoders={int: CustomEncoder()})
    assert {
        "mapping": {"foo": {"foo": "bar"}},
        "custom": {42: {"foo": "foo"}},
    } == serializer.dump(
        Parent(mapping={"foo": Nested(foo="bar")}, custom={42: Nested(foo="foo")})
    )
