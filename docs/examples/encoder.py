import typing
from dataclasses import dataclass

from serpyco import FieldEncoder, Serializer


class Rational(object):
    def __init__(self, numerator: int, denominator: int):
        self.numerator = numerator
        self.denominator = denominator

    def __repr__(self) -> str:
        return f"Rational({self.numerator}/{self.denominator})"


class RationalEncoder(FieldEncoder):
    def load(self, value: typing.Tuple[int, int]) -> Rational:
        return Rational(value[0], value[1])

    def dump(self, rational: Rational) -> typing.Tuple[int, int]:
        return (rational.numerator, rational.denominator)

    def json_schema(self) -> dict:
        return {
            "type": "array",
            "maxItems": 2,
            "minItems": 2,
            "items": {"type": "integer"},
        }


@dataclass
class Custom(object):
    rational: Rational


serializer = Serializer(Custom, type_encoders={Rational: RationalEncoder()})
print(serializer.dump(Custom(rational=Rational(1, 2))))

print(serializer.load({"rational": (1, 2)}))
print(serializer.load({"rational": (1, 2.1)}))
