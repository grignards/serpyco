from dataclasses import dataclass

from serpyco import Serializer, ValidationError, number_field


@dataclass
class NumberFields(object):
    simple: int
    range: float = number_field(minimum=0, maximum=10)


serializer = Serializer(NumberFields)
print(serializer.load({"simple": 98, "range": 5}, validate=True))

try:
    serializer.load({"simple": 100, "range": 12}, validate=True)
except ValidationError as exc:
    print(f"ValidationError: {exc}")
