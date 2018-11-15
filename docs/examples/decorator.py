from dataclasses import dataclass

from serpyco import Serializer, post_dump


@dataclass
class Custom(object):
    firstname: str
    lastname: str

    @post_dump
    def make_name(data: dict) -> dict:
        first = data["firstname"]
        last = data["lastname"]
        return {"name": f"{first} {last}"}


serializer = Serializer(Custom)
print(serializer.dump(Custom(firstname="foo", lastname="bar")))
