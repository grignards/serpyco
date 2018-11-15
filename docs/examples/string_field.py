from dataclasses import dataclass
from serpyco import Serializer, string_field, ValidationError


@dataclass
class StringFields(object):
    simple: str
    name: str = string_field(pattern="^[A-Z]")


serializer = Serializer(StringFields)
print(serializer.load({"name": "Foo", "simple": "whatever"}, validate=True))

try:
    serializer.load({"name": "foo", "simple": "foo"}, validate=True)
except ValidationError as exc:
    print(f"ValidationError: {exc}")

