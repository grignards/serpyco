from dataclasses import dataclass
from serpyco import Serializer, string_field, StringPattern, ValidationError


@dataclass
class StringFields(object):
    name: str
    mail: str = string_field(pattern=StringPattern.IPV4)


serializer = Serializer(StringFields)
print(serializer.load({"name": "foo", "mail": "foo@bar.cc"}))

try:
    serializer.load({"name": "foo", "mail": "notamail"}, validate=True)
except ValidationError as exc:
    print(exc)
