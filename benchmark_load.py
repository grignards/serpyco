import dataslots
import timeit
import typing

import dataclasses

import serpyco


@dataslots.with_slots
@dataclasses.dataclass
class Nested(object):
    name: str


@dataslots.with_slots
@dataclasses.dataclass
class Test(object):

    name: str
    value: int
    f: float
    b: bool
    nest: typing.List[Nested]
    many: typing.List[int]
    option: typing.Optional[str] = None


serializer = serpyco.Serializer(Test)

t = Test(
    name="Foo", value=42, f=12.34, b=True, nest=[Nested(name="Bar")], many=[1, 2, 3]
)
t.nest = [Nested(name="Bar_{}".format(index)) for index in range(0, 1000)]
js = serializer.to_json(t, validate=True)
number = 10000
time = (
    timeit.timeit(
        "serializer.from_json(js, validate=True)", globals=globals(), number=number
    )
    / number
)
