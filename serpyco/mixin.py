import typing

from serpyco.serializer import Serializer

T = typing.TypeVar("T", bound="SerializerMixin")


class SerializerMixin:
    """Base class that provides load/dump, load_json/dump_json methods."""

    _serializer: typing.ClassVar[typing.Optional[Serializer]] = None  # type: ignore

    @classmethod
    def load(
        cls: typing.Type[T], data: typing.Dict[str, typing.Any], validate: bool = True
    ) -> T:
        """Load the given dict an return a new object."""
        return typing.cast(T, cls.serializer().load(data, validate=validate))

    def dump(self, validate: bool = False) -> typing.Dict[str, typing.Any]:
        """Dump the object to a dict."""
        return typing.cast(
            typing.Dict[str, typing.Any],
            self.serializer().dump(self, validate=validate),
        )

    @classmethod
    def load_json(cls: typing.Type[T], json_string: str, validate: bool = True) -> T:
        """Load the given JSON string an return a new object."""
        return typing.cast(
            T, cls.serializer().load_json(json_string, validate=validate)
        )

    def dump_json(self, validate: bool = False) -> str:
        """Dump the object to a JSON string."""
        return self.serializer().dump_json(self, validate=validate)

    @classmethod
    def serializer(cls: typing.Type[T]) -> Serializer:  # type: ignore
        """Serializer instance for this class."""
        if not cls._serializer:
            cls._serializer = Serializer(cls)
        return cls._serializer
