from dataclasses import dataclass

from serpyco import Serializer


@dataclass
class Point(object):
    x: float
    y: float


serializer = Serializer(Point)
print(serializer.dump(Point(x=3.14, y=1.5)))
{"x": 3.14, "y": 1.5}
