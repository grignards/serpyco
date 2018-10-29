from pprint import pprint

from dataclasses import dataclass

from dataclasses_serializer import Serializer


@dataclass
class Point(object):
    x: float
    y: float


serializer = Serializer(Point)

pprint(serializer.json_schema())
pprint(serializer.from_dict({"x": 3.14, "y": 1.5}))
try:
    serializer.from_dict({"x": 3.14, "y": "wrong"})
except Exception as ex:
    pprint(ex)
