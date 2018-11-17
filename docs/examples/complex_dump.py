import enum
import typing
from dataclasses import dataclass

from serpyco import Serializer


@dataclass
class Point(object):
    x: float
    y: float


class PolygonColor(enum.Enum):
    RED = 1
    GREEN = 2
    BLUE = 3


@dataclass
class Polygon(object):
    points: typing.List[Point]
    color: PolygonColor
    name: typing.Optional[str] = None


serializer = Serializer(Polygon)
serializer.dump(
    Polygon(points=[Point(1, 2), Point(2, 3), Point(4, 5)], color=PolygonColor.RED)
)
{"color": 1, "points": [{"x": 1, "y": 2}, {"x": 2, "y": 3}, {"x": 4, "y": 5}]}
