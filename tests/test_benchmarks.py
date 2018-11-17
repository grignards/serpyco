# -*- coding: utf-8 -*-

import dataclasses
import typing

import dataslots

import serpyco


@dataslots.with_slots
@dataclasses.dataclass
class Nested(object):
    """
    A nested type for Dataclass
    """

    name: str


@dataslots.with_slots
@dataclasses.dataclass
class Dataclass(object):
    """
    A Dataclass class
    """

    name: str
    value: int
    f: float
    b: bool
    nest: typing.List[Nested]
    many: typing.List[int]
    option: typing.Optional[str] = None


serializer = serpyco.Serializer(Dataclass)
validator = serpyco.validator.RapidJsonValidator(serializer.json_schema())
test_object = Dataclass(
    name="Foo",
    value=42,
    f=12.34,
    b=True,
    nest=[Nested(name="Bar_{}".format(index)) for index in range(0, 1000)],
    many=[1, 2, 3],
)
test_dict = serializer.dump(test_object)
test_json = serializer.dump_json(test_object)

# Avoid overhead of first validation
validator.validate_json(test_json)
serializer.load(test_dict)


def test_dump(benchmark):
    benchmark(serializer.dump, test_object)


def test_dump_json(benchmark):
    benchmark(serializer.dump_json, test_object)


def test_load(benchmark):
    benchmark(serializer.load, test_dict, validate=False)


def test_load_json(benchmark):
    benchmark(serializer.load_json, test_json, validate=False)


def test_validate(benchmark):
    benchmark(validator.validate, test_dict)


def test_validate_json(benchmark):
    benchmark(validator.validate_json, test_json)
