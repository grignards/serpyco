# -*- coding: utf-8 -*-

import dataclasses
import typing

import dataslots

import serpyco

BENCHMARK_PEDANTIC_OPTIONS = {"rounds": 200, "warmup_rounds": 100, "iterations": 10}


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
validator = serpyco.validator.RapidJsonValidator(serpyco.SchemaBuilder(Dataclass))
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
    benchmark.pedantic(
        serializer.dump, args=(test_object,), **BENCHMARK_PEDANTIC_OPTIONS
    )


def test_dump_json(benchmark):
    benchmark.pedantic(
        serializer.dump_json, args=(test_object,), **BENCHMARK_PEDANTIC_OPTIONS
    )


def test_load(benchmark):
    benchmark.pedantic(
        serializer.load,
        args=(test_dict,),
        kwargs={"validate": False},
        **BENCHMARK_PEDANTIC_OPTIONS
    )


def test_load_json(benchmark):
    benchmark.pedantic(
        serializer.load_json,
        args=(test_json,),
        kwargs={"validate": False},
        **BENCHMARK_PEDANTIC_OPTIONS
    )


def test_validate(benchmark):
    benchmark.pedantic(
        validator.validate, args=(test_dict,), **BENCHMARK_PEDANTIC_OPTIONS
    )


def test_validate_json(benchmark):
    benchmark.pedantic(
        validator.validate_json, args=(test_json,), **BENCHMARK_PEDANTIC_OPTIONS
    )
