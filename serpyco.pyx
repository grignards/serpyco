# cython: boundscheck=False
# cython: language_level=3

import datetime
import enum
import typing
import uuid

import cython
import dateutil.parser
import dataclasses
import rapidjson


class JsonSchemaError(Exception):
    pass


class NoEncoderError(Exception):
    pass


class ValidationError(Exception):
    pass


cdef class FieldEncoder(object):
    """Base class for encoding fields to and from JSON encodable values"""

    cpdef to_wire(self, value: typing.Any):
        """
        Convert the given value to a JSON encodable value
        """
        raise NotImplementedError()

    cpdef to_python(self, value: typing.Any):
        """
        Convert the given JSON value to its python counterpart
        """
        raise NotImplementedError()

    @property
    def json_schema(self) -> JsonDict:
        """
        Return the JSON schema for this encoder"s handled value type(s).
        """
        raise NotImplementedError()


def field(dict_key: str=None, *args, **kwargs):
    """
    Convenience function to setup Serializer hints on dataclass fields.
    Call it at field declaration as you would do with dataclass.field().
    :param dict_key: key of the field in the output dictionaries.
    """
    metadata = kwargs.get("metadata", {})
    metadata[__name__] = FieldHints(dict_key=dict_key)
    kwargs["metadata"] = metadata
    return dataclasses.field(*args, **kwargs)


@cython.final
cdef class Serializer(object):
    """
    Serializer class for dataclasses instances.
    """

    cdef list _fields
    cdef object _data_class
    cdef bint _many
    cdef bint _omit_none
    cdef dict _json_schema
    cdef object _validator
    _field_encoders = {
        datetime.datetime: DateTimeFieldEncoder(),
        uuid.UUID: UuidFieldEncoder()
    }

    def __init__(self, data_class, many: bool=False, omit_none: bool=True):
        self._data_class = data_class
        self._many = many
        self._omit_none = omit_none
        type_hints = typing.get_type_hints(data_class)
        self._fields = []
        for f in dataclasses.fields(data_class):
            if f.name.startswith("_"):
                continue
            field_type = type_hints[f.name]
            hints = f.metadata.get(__name__, FieldHints(dict_key=f.name))
            self._fields.append((
                f.name,
                hints.dict_key,
                self._get_encoder(field_type)
            ))

        schema = self._create_json_schema(data_class, type_hints)
        self._validator = rapidjson.Validator(rapidjson.dumps(schema))
        self._json_schema = schema

    @classmethod
    def register_encoder(
        cls,
        field_type: typing.ClassVar,
        encoder: FieldEncoder
    ) -> None:
        cls._field_encoders[field_type] = encoder

    def json_schema(self) -> JsonDict:
        return self._json_schema

    cpdef inline to_dict(
        self,
        obj: typing.Union[object, typing.Iterable],
        validate: bool=False
    ):
        if self._many:
            data = [self._to_dict(o) for o in obj]
        else:
            data = self._to_dict(obj)
        if validate:
            self._validate(rapidjson.dumps(data))
        return data

    cpdef inline from_dict(
        self,
        data: typing.Union[dict, typing.Iterable],
        validate: bool=True
    ):
        if validate:
            self._validate(rapidjson.dumps(data))

        if self._many:
            return [self._from_dict(d) for d in data]
        return self._from_dict(data)

    cpdef inline str to_json(
        self,
        obj: typing.Union[object, typing.Iterable],
        validate: bool=False
    ):
        if self._many:
            data = [self._to_dict(o) for o in obj]
        else:
            data = self._to_dict(obj)

        js = rapidjson.dumps(data)
        if validate:
            self._validate(js)

        return js

    cpdef inline object from_json(self, js: str, validate: bool=True):
        """
        Constructs
        """
        if validate:
            self._validate(js)
        data = rapidjson.loads(js)
        if self._many:
            return [self._from_dict(value) for value in data]
        return self._from_dict(data)

    cdef inline dict _to_dict(self, obj: typing.Any):
        data = {}
        for field_name, dict_key, encoder in self._fields:
            value = getattr(obj, field_name)
            if value is None:
                if self._omit_none:
                    continue
                else:
                    encoded = None
            elif encoder:
                encoded = encoder.to_wire(value)
            else:
                encoded = value
            data[dict_key] = encoded
        return data

    cdef inline object _from_dict(self, data: typing.Any):
        decoded_data = {}
        for field_name, dict_key, encoder in self._fields:
            encoded_value = data.get(dict_key)
            if encoder:
                decoded_data[field_name] = encoder.to_python(encoded_value)
            else:
                decoded_data[field_name] = encoded_value
        return self._data_class(**decoded_data)

    def _get_encoder(self, field_type):
        try:
            return self._field_encoders[field_type]
        except KeyError:
            pass
        if _issubclass_safe(field_type, tuple(JSON_ENCODABLE_TYPES.keys())):
            return None
        elif _is_optional(field_type):
            return self._get_encoder(field_type.__args__[0])
        elif _issubclass_safe(field_type, enum.Enum):
            return EnumFieldEncoder(field_type)
        elif _issubclass_safe(field_type, (typing.Mapping, typing.Dict)):
            key_encoder = self._get_encoder(field_type.__args__[0])
            value_encoder = self._get_encoder(field_type.__args__[1])
            if key_encoder or value_encoder:
                return DictFieldEncoder(key_encoder, value_encoder)
            return None
        elif _issubclass_safe(field_type, (typing.Sequence, typing.List)):
            item_encoder = self._get_encoder(field_type.__args__[0])
            if item_encoder:
                return ListFieldEncoder(item_encoder, field_type)
            else:
                return None
        elif dataclasses.is_dataclass(field_type):
            return DataClassFieldEncoder(field_type, omit_none=self._omit_none)
        raise NoEncoderError(f"No encoder for '{field_type}'")

    @classmethod
    def _get_field_schema(
        cls,
        field_type: typing.Any
    ) -> typing.Tuple[JsonDict, bool]:
        field_schema: JsonDict = {"type": "object"}
        required = True
        field_type_name = cls._get_field_type_name(field_type)
        if dataclasses.is_dataclass(field_type):
            field_schema = {
                "type": "object",
                "$ref": "#/definitions/{}".format(field_type_name)
            }
        else:
            if _is_optional(field_type):
                field_schema = cls._get_field_schema(field_type.__args__[0])[0]
                required = False
            elif field_type in JSON_ENCODABLE_TYPES:
                field_schema = JSON_ENCODABLE_TYPES[field_type]
            elif _issubclass_safe(field_type, enum.Enum):
                member_types = set()
                values = []
                for member in field_type:
                    member_types.add(type(member.value))
                    values.append(member.value)
                if len(member_types) == 1:
                    member_type = member_types.pop()
                    if member_type in JSON_ENCODABLE_TYPES:
                        field_schema.update(JSON_ENCODABLE_TYPES[member_type])
                    elif member_type in cls._field_encoders:
                        field_schema.update(
                            cls._field_encoders[member_types.pop()].json_schema
                        )
                field_schema["enum"] = values
                if field_type.__doc__:
                    field_schema["description"] = field_type.__doc__.strip()
            elif _issubclass_safe(field_type, (typing.Dict, typing.Mapping)):
                field_schema = {"type": "object"}
                if field_type.__args__[1] is not typing.Any:
                    add = cls._get_field_schema(field_type.__args__[1])[0]
                    field_schema["additionalProperties"] = add
            elif _issubclass_safe(field_type, (typing.Sequence, typing.List)):
                field_schema = {"type": "array"}
                if field_type.__args__[0] is not typing.Any:
                    items = cls._get_field_schema(field_type.__args__[0])[0]
                    field_schema["items"] = items
            elif field_type in cls._field_encoders:
                field_schema.update(
                    cls._field_encoders[field_type].json_schema
                )
            elif hasattr(field_type, "__supertype__"):  # NewType fields
                field_schema, _ = cls._get_field_schema(field_type.__supertype__)  # noqa:E501
            else:
                msg = f"Unable to create schema for '{field_type}'"
                raise JsonSchemaError(msg)
        return field_schema, required

    def _create_json_schema(
        self,
        data_class: typing.ClassVar,
        type_hints: dict,
        embeddable=False
    ) -> dict:
        """Returns the JSON schema for the dataclass, along with the schema
        of any nested dataclasses within the "definitions" field.

        Enable the embeddable flag to generate the schema in a format
        for embedding into other schemas or documents supporting
        JSON schema such as Swagger specs,
        """
        definitions: JsonDict = {}  # noqa: E704

        properties = {}
        required = []
        for field_name, dict_key, _ in self._fields:
            field_type = type_hints[field_name]
            properties[dict_key], _ = self._get_field_schema(field_type)
            item_type = field_type
            if _is_optional(field_type):
                item_type = field_type.__args__[0]
            elif _issubclass_safe(field_type, (typing.Dict, typing.Mapping)):
                item_type = field_type.__args__[1]
            elif (_issubclass_safe(field_type, (typing.Sequence, typing.List)) and not  # noqa: E501
                  _issubclass_safe(field_type, str)):
                item_type = field_type.__args__[0]

            if dataclasses.is_dataclass(item_type):
                # Prevent recursion from forward refs & circular
                # type dependencies
                if item_type.__name__ not in definitions:
                    item_type_hints = typing.get_type_hints(item_type)
                    ser = Serializer(item_type)
                    definitions[item_type.__name__] = None
                    item_schema = ser._create_json_schema(
                        item_type,
                        item_type_hints,
                        embeddable=True
                    )
                    definitions.update(item_schema)
            if is_required:
                required.append(dict_key)
        schema = {
            "type": "object",
            "properties": properties
        }
        if required:
            schema["required"] = required
        if data_class.__doc__:
            schema["description"] = data_class.__doc__.strip()

        if embeddable:
            schema = {**definitions, data_class.__name__: schema}
        elif not self._many:
            schema = {**schema, **{
                "definitions": definitions,
                "$schema": "http://json-schema.org/draft-04/schema#"
            }}
        else:
            schema = {
                "definitions": definitions,
                "$schema": "http://json-schema.org/draft-04/schema#",
                "type": "array",
                "items": schema,
            }

        return schema

    @staticmethod
    def _get_field_type_name(field_type: typing.Any) -> typing.Optional[str]:
        try:
            return field_type.__name__
        except AttributeError:
            try:
                return field_type._name
            except AttributeError:
                return None

    def _validate(self, json_string: str) -> None:
        try:
            self._validator(json_string)
        except rapidjson.ValidationError as exc:
            raise ValidationError(str(exc))

JSON_ENCODABLE_TYPES = {
    str: {"type": "string"},
    int: {"type": "number", "format": "integer"},
    bool: {"type": "boolean"},
    float: {"type": "number", "format": "float"}
}

JsonEncodable = typing.Union[int, float, str, bool]
JsonDict = typing.Dict[str, typing.Any]


def _issubclass_safe(field_type, classes) -> bool:
    try:
        return issubclass(field_type, classes)
    except (TypeError, AttributeError):
        return False


def _is_optional(field_type) -> bool:
    field_type_name = str(field_type)
    return (
        field_type_name.startswith("Union") or
        field_type_name.startswith("typing.Union")
    ) and issubclass(field_type.__args__[1], type(None))


@cython.final
cdef class EnumFieldEncoder(FieldEncoder):
    cdef object _enum_type

    def __init__(self, enum_type):
        self._enum_type = enum_type

    cpdef inline to_wire(self, value: typing.Any):
        return value.value

    cpdef inline to_python(self, value: typing.Any):
        return self._enum_type(value)

    def json_schema(self) -> JsonDict:
        return {}


@cython.final
cdef class DataClassFieldEncoder(FieldEncoder):
    cdef Serializer _serializer

    def __init__(self, data_class, omit_none: bool):
        self._serializer = Serializer(data_class, omit_none=omit_none)

    cpdef inline to_python(self, value: typing.Any):
        return self._serializer._from_dict(value)

    cpdef inline to_wire(self, value: typing.Any):
        return self._serializer._to_dict(value)

    def json_schema(self) -> JsonDict:
        return self.serializer.json_schema()


@cython.final
cdef class ListFieldEncoder(FieldEncoder):
    cdef FieldEncoder _item_encoder
    cdef object _sequence_type

    def __init__(self, item_encoder, sequence_type):
        self._item_encoder = item_encoder
        if issubclass(sequence_type, typing.List):
            self._sequence_type = list
        else:
            self._sequence_type = sequence_type

    cpdef inline to_python(self, value: typing.Any):
        return self._sequence_type(map(self._item_encoder.to_python, value))

    cpdef inline to_wire(self, value: typing.Any):
        return self._sequence_type(map(self._item_encoder.to_wire, value))


@cython.final
cdef class DictFieldEncoder(FieldEncoder):
    cdef FieldEncoder _key_encoder
    cdef FieldEncoder _value_encoder

    def __init__(self, key_encoder, value_encoder):
        self._key_encoder = key_encoder
        self._value_encoder = value_encoder

    cpdef inline to_python(self, value: JsonEncodable):
        if self._key_encoder and self._value_encoder:
            return {
                self._key_encoder(k): self._value_encoder(v)
                for k, v in value.items()
            }
        elif self._key_encoder and not self._value_encoder:
            return {
                self._key_encoder(k): v
                for k, v in value.items()
            }
        elif not self._key_encoder and self._value_encoder:
            return {
                k: self._value_encoder(v)
                for k, v in value.items()
            }
        else:
            return value

    cpdef inline to_wire(self, value: typing.Any):
        if self._key_encoder and self._value_encoder:
            return {
                self._key_encoder.to_wire(k): self._value_encoder.to_wire(v)
                for k, v in value.items()
            }
        elif self._key_encoder and not self._value_encoder:
            return {
                self._key_encoder.to_wire(k): v
                for k, v in value.items()
            }
        elif not self._key_encoder and self._value_encoder:
            return {
                k: self._value_encoder(v)
                for k, v in value.items()
            }
        else:
            return value


@cython.final
cdef class DateTimeFieldEncoder(FieldEncoder):
    """Encodes datetimes to RFC3339 format"""

    cpdef inline to_wire(self, value):
        out = value.isoformat()

        # Assume UTC if timezone is missing
        if value.tzinfo is None:
            return out + "00:00"
        return out

    cpdef inline to_python(self, value):
        if isinstance(value, datetime.datetime):
            return value
        else:
            return dateutil.parser.parse(typing.cast(str, value))

    @property
    def json_schema(self) -> JsonDict:
        return {"type": "string", "format": "date-time"}


@cython.final
cdef class UuidFieldEncoder(FieldEncoder):

    cpdef inline to_wire(self, value):
        return str(value)

    cpdef inline to_python(self, value):
        return uuid.UUID(value)

    @property
    def json_schema(self):
        return {"type": "string", "format": "uuid"}


class FieldHints(object):
    def __init__(self, dict_key: typing.Optional[str]) -> None:
        self.dict_key = dict_key
