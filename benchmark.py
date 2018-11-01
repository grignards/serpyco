import rapidjson
import json
import timeit
import typing
import dataslots
import dataclasses
import pprint

import serpyco


@dataslots.with_slots
@dataclasses.dataclass
class Nested(object):
    """
    A nested type for test
    """

    name: str


@dataslots.with_slots
@dataclasses.dataclass
class Test(object):
    """
    A test class
    """

    name: str
    value: int
    f: float
    b: bool
    nest: typing.List[Nested]
    many: typing.List[int]
    option: typing.Optional[str] = None


serializer = serpyco.Serializer(Test)
pprint.pprint(serializer.json_schema())
t = Test(
    name="Foo", value=42, f=12.34, b=True, nest=[Nested(name="Bar")], many=[1, 2, 3]
)
print(serializer.dump(t, validate=True))
print(serializer.load(serializer.dump(t)))
assert t == serializer.load(serializer.dump(t))
number = 10000
time = timeit.timeit("serializer.dump(t)", globals=globals(), number=number) / number
print("{0:.2f} us/statement".format(1e6 * time))

t.nest = [Nested(name="Bar_{}".format(index)) for index in range(0, 1000)]
d = serializer.dump(t, validate=True)
js = serializer.dump_json(t, validate=True)
number = 10000
time = (
    timeit.timeit(
        "serializer.dump_json(t, validate=False)", globals=globals(), number=number
    )
    / number
)
print("serializer.dump_json: {0:.2f} us/statement".format(1e6 * time))
time = timeit.timeit("json.dumps(d)", globals=globals(), number=number) / number
print("json.dumps: {0:.2f} us/statement".format(1e6 * time))
time = (
    timeit.timeit(
        "serializer.load_json(js, validate=False)", globals=globals(), number=number
    )
    / number
)
print("serializer.load_json: {0:.2f} us/statement".format(1e6 * time))
time = timeit.timeit("json.loads(js)", globals=globals(), number=number) / number
print("json.loads: {0:.2f} us/statement".format(1e6 * time))
