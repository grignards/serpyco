# -*- coding: utf-8 -*-

from pprint import pprint

from dataclasses import dataclass
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
