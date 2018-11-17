# -*- coding: utf-8 -*-

from dataclasses import dataclass
from pprint import pprint

from serpyco import Serializer


@dataclass
class Point(object):
    x: float
    y: float


serializer = Serializer(Point)

pprint(serializer.json_schema())
pprint(serializer.load({"x": 3.14, "y": 1.5}))
try:
    serializer.load({"x": 3.14, "y": "wrong"})
except Exception as ex:
    pprint(ex)
pprint(serializer.dump(Point(x=3.14, y=1.5)))
try:
    serializer.dump(Point(x=3.14, y="wrong"), validate=True)
except Exception as ex:
    pprint(ex)
