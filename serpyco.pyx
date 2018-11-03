# cython: boundscheck=False
# cython: language_level=3
# cython: profile=True

import datetime
import enum
import typing
import uuid

import cython
import dateutil.parser
import dataclasses
import rapidjson


class BaseSerpycoError(Exception):
    pass


class JsonSchemaError(BaseSerpycoError):
    pass


class NoEncoderError(BaseSerpycoError):
    pass


class ValidationError(BaseSerpycoError):
    pass


cdef class FieldEncoder(object):
    """Base class for encoding fields to and from JSON encodable values"""

    cpdef dump(self, value: typing.Any):
        """
        Convert the given value to a JSON encodable value
        """
        raise NotImplementedError()

    cpdef load(self, value: typing.Any):
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


JsonDict = typing.Dict[str, typing.Any]


class Validator(object):
    """
    Validates a dict/json string against a dataclass definition.
    """

    _custom_schemas: JsonDict = {}

    def __init__(self, data_class: typing.ClassVar, many: bool=False) -> None:
        self._data_class = data_class
        self._json_schema: typing.Optional[str] = None
        self._many = many
        self._validator: typing.Optional[rapidjson.Validator] = None
        self._fields = [
            (f.name, f.metadata.get(__name__, FieldHints(dict_key=f.name)))
            for f in dataclasses.fields(data_class)
        ]

    def validate(self, data: typing.Union[dict, list]) -> None:
        self.validate_json(rapidjson.dumps(data))

    def validate_json(self, json_string: str) -> None:
        if not self._validator:
            js = rapidjson.dumps(self.json_schema())
            self._validator = rapidjson.Validator(js)
        try:
            self._validator(json_string)
        except rapidjson.ValidationError as exc:
            raise ValidationError(str(exc))

    def json_schema(self) -> JsonDict:
        if not self._json_schema:
            self._json_schema = self._create_json_schema()
        return self._json_schema

    @classmethod
    def register_custom_schema(
        cls,
        type_: typing.ClassVar,
        schema: JsonDict
    ) -> None:
        cls._custom_schemas[type_] = schema

    def _create_json_schema(
        self,
        embeddable=False,
        parent_validators: typing.List["Validator"]=None,
    ) -> dict:
        """Returns the JSON schema for the dataclass, along with the schema
        of any nested dataclasses within the "definitions" field.

        Enable the embeddable flag to generate the schema in a format
        for embedding into other schemas or documents supporting
        JSON schema such as Swagger specs,
        """
        parent_validators = parent_validators or []
        parent_validators.append(self)

        definitions: JsonDict = {}  # noqa: E704
        type_hints = typing.get_type_hints(self._data_class)

        properties = {}
        required = []
        for field_name, hints in self._fields:
            field_type = type_hints[field_name]
            properties[hints.dict_key], is_required = self._get_field_schema(
                field_type,
                parent_validators
            )

            # Update definitions to objects
            item_types = [field_type]
            if _is_optional(field_type):
                item_types = [field_type.__args__[0]]
            elif _is_union(field_type):
                item_types = field_type.__args__
            elif _issubclass_safe(field_type, (typing.Dict, typing.Mapping)):
                item_types = [field_type.__args__[1]]
            elif (_issubclass_safe(field_type, (typing.Sequence, typing.List)) and not  # noqa: E501
                  _issubclass_safe(field_type, str)):
                item_types = [field_type.__args__[0]]

            for item_type in item_types:
                # Prevent recursion from forward refs &
                # circular type dependencies
                if (
                    dataclasses.is_dataclass(item_type) and
                    item_type.__name__ not in definitions
                ):
                    for validator in parent_validators:
                        if validator._data_class == item_type:
                            break
                    else:
                        sub = Validator(item_type)
                        item_schema = sub._create_json_schema(
                            embeddable=True,
                            parent_validators=parent_validators
                        )
                        definitions[item_type.__name__] = None
                        definitions.update(item_schema)
            if is_required:
                required.append(hints.dict_key)
        schema = {
            "type": "object",
            "properties": properties
        }
        if required:
            schema["required"] = required
        if self._data_class.__doc__:
            schema["description"] = self._data_class.__doc__.strip()

        if embeddable:
            schema = {**definitions, self._data_class.__name__: schema}
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

    def _get_field_schema(
        self,
        field_type: typing.Any,
        parent_validators: typing.List["Validator"]
    ) -> typing.Tuple[JsonDict, bool]:
        field_schema: JsonDict = {"type": "object"}
        required = True
        field_type_name = self._get_field_type_name(field_type)
        if dataclasses.is_dataclass(field_type):
            if field_type == parent_validators[0]._data_class:
                ref = "#"
            else:
                ref = "#/definitions/{}".format(field_type_name)
            field_schema = {
                "type": "object",
                "$ref": ref
            }
        else:
            if _is_optional(field_type):
                field_schema = self._get_field_schema(
                    field_type.__args__[0],
                    parent_validators
                )[0]
                required = False
            elif _is_union(field_type):
                schemas = [
                    self._get_field_schema(item_type, parent_validators)[0]
                    for item_type in field_type.__args__
                ]
                field_schema["oneOf"] = schemas
                del field_schema["type"]
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
                    elif member_type in self._custom_schemas:
                        field_schema.update(
                            self._custom_schemas[member_types.pop()]
                        )
                field_schema["enum"] = values
                if field_type.__doc__:
                    field_schema["description"] = field_type.__doc__.strip()
            elif field_type in JSON_ENCODABLE_TYPES:
                field_schema = JSON_ENCODABLE_TYPES[field_type]
            elif _issubclass_safe(field_type, (typing.Dict, typing.Mapping)):
                field_schema = {"type": "object"}
                if field_type.__args__[1] is not typing.Any:
                    add = self._get_field_schema(
                        field_type.__args__[1],
                        parent_validators
                    )[0]
                    field_schema["additionalProperties"] = add
            elif _issubclass_safe(field_type, (typing.Sequence, typing.List)):
                field_schema = {"type": "array"}
                if field_type.__args__[0] is not typing.Any:
                    items = self._get_field_schema(
                        field_type.__args__[0],
                        parent_validators
                    )[0]
                    field_schema["items"] = items
            elif field_type in self._custom_schemas:
                field_schema.update(self._custom_schemas[field_type])
            elif hasattr(field_type, "__supertype__"):  # NewType fields
                field_schema, _ = self._get_field_schema(
                    field_type.__supertype__,
                    parent_validators
                )
            else:
                msg = f"Unable to create schema for '{field_type}'"
                raise JsonSchemaError(msg)
        return field_schema, required

    @staticmethod
    def _get_field_type_name(field_type: typing.Any) -> typing.Optional[str]:
        try:
            return field_type.__name__
        except AttributeError:
            try:
                return field_type._name
            except AttributeError:
                return None


@cython.final
cdef class Serializer(object):
    """
    Serializer class for dataclasses instances.
    """

    cdef list _fields
    cdef object _data_class
    cdef bint _many
    cdef bint _omit_none
    cdef object _validator
    cdef list _parent_serializers
    _field_encoders = {
        datetime.datetime: DateTimeFieldEncoder(),
        uuid.UUID: UuidFieldEncoder()
    }
    for f, e in _field_encoders.items():
        Validator.register_custom_schema(f, e.json_schema)

    def __init__(
        self,
        data_class: typing.ClassVar,
        many: bool=False,
        omit_none: bool=True,
        _parent_serializers: typing.List["Serializer"]=None
    ):
        """
        Constructs a serializer for the given data class.
        :param data_class data class this serializer will handle
        :param many if True, serializer will handle lists of the data_class
        :param omit_none if False, keep None values in the serialized dicts
        """
        if not dataclasses.is_dataclass(data_class):
            raise BaseSerpycoError(f"{data_class} is not a dataclass")
        self._data_class = data_class
        self._many = many
        self._omit_none = omit_none
        self._parent_serializers = _parent_serializers or []
        self._parent_serializers.append(self)
        type_hints = typing.get_type_hints(data_class)
        self._fields = []

        for f in dataclasses.fields(data_class):
            field_type = type_hints[f.name]
            hints = f.metadata.get(__name__, FieldHints(dict_key=f.name))
            encoder = self._get_encoder(field_type)
            self._fields.append((f.name, hints.dict_key, encoder))

        self._validator = Validator(data_class, many=many)

    def json_schema(self) -> JsonDict:
        return self._validator.json_schema()

    @classmethod
    def register_encoder(
        cls,
        field_type: typing.ClassVar,
        encoder: FieldEncoder
    ) -> None:
        cls._field_encoders[field_type] = encoder
        Validator.register_custom_schema(field_type, encoder.json_schema)

    @property
    def data_class(self) -> typing.ClassVar:
        return self._data_class

    cpdef inline dump(
        self,
        obj: typing.Union[object, typing.Iterable],
        validate: bool=False
    ):
        if self._many:
            data = [self._dump(o) for o in obj]
        else:
            data = self._dump(obj)
        if validate:
            self._validator.validate(data)
        return data

    cpdef inline load(
        self,
        data: typing.Union[dict, typing.Iterable],
        validate: bool=True
    ):
        if validate:
            self._validator.validate(data)

        if self._many:
            return [self._load(d) for d in data]
        return self._load(data)

    cpdef inline str dump_json(
        self,
        obj: typing.Union[object, typing.Iterable],
        validate: bool=False
    ):
        if self._many:
            data = [self._dump(o) for o in obj]
        else:
            data = self._dump(obj)

        js = rapidjson.dumps(data)
        if validate:
            self._validator.validate_json(js)

        return js

    cpdef inline object load_json(self, js: str, validate: bool=True):
        """
        Constructs
        """
        if validate:
            self._validator.validate_json(js)
        data = rapidjson.loads(js)
        if self._many:
            return [self._load(value) for value in data]
        return self._load(data)

    cdef inline dict _dump(self, obj: typing.Any):
        data = {}
        for field_name, dict_key, encoder in self._fields:
            value = getattr(obj, field_name)
            if value is None:
                if self._omit_none:
                    continue
                else:
                    encoded = None
            elif encoder:
                encoded = encoder.dump(value)
            else:
                encoded = value
            data[dict_key] = encoded
        return data

    cdef inline object _load(self, data: typing.Any):
        decoded_data = {}
        for field_name, dict_key, encoder in self._fields:
            encoded_value = data.get(dict_key)
            if encoder:
                decoded_data[field_name] = encoder.load(encoded_value)
            else:
                decoded_data[field_name] = encoded_value
        return self._data_class(**decoded_data)

    def _get_encoder(self, field_type):
        try:
            return self._field_encoders[field_type]
        except KeyError:
            pass
        if _issubclass_safe(field_type, enum.Enum):
            # Must be first as enums can inherit from another type
            return EnumFieldEncoder(field_type)
        elif _issubclass_safe(field_type, tuple(JSON_ENCODABLE_TYPES.keys())):
            return None
        elif _is_optional(field_type):
            return self._get_encoder(field_type.__args__[0])
        elif _is_union(field_type):
            type_encoders = [
                (item_type, self._get_encoder(item_type))
                for item_type in field_type.__args__
            ]
            return UnionFieldEncoder(type_encoders)
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
            # See if one of our "ancestors" handles this type.
            # This avoids infinite recursion if data_classes establish a cycle
            for serializer in self._parent_serializers:
                if serializer.data_class == field_type:
                    break
            else:
                serializer = Serializer(
                    field_type,
                    omit_none=self._omit_none,
                    _parent_serializers=self._parent_serializers
                )
            return DataClassFieldEncoder(serializer)
        raise NoEncoderError(f"No encoder for '{field_type}'")


JSON_ENCODABLE_TYPES = {
    str: {"type": "string"},
    int: {"type": "number", "format": "integer"},
    bool: {"type": "boolean"},
    float: {"type": "number", "format": "float"}
}


JsonEncodable = typing.Union[int, float, str, bool]


def _issubclass_safe(field_type, classes) -> bool:
    try:
        return issubclass(field_type, classes)
    except (TypeError, AttributeError):
        return False


def _is_union(field_type) -> bool:
    # issubclass doesn't work with Union...
    field_type_name = str(field_type)
    return (
        field_type_name.startswith("Union") or
        field_type_name.startswith("typing.Union")
    )


def _is_optional(field_type) -> bool:
    return (
        _is_union(field_type) and
        2 == len(field_type.__args__) and
        issubclass(field_type.__args__[1], type(None))
    )


@cython.final
cdef class EnumFieldEncoder(FieldEncoder):
    cdef object _enum_type

    def __init__(self, enum_type):
        self._enum_type = enum_type

    cpdef inline dump(self, value: typing.Any):
        return value.value

    cpdef inline load(self, value: typing.Any):
        return self._enum_type(value)

    def json_schema(self) -> JsonDict:
        return {}


@cython.final
cdef class DataClassFieldEncoder(FieldEncoder):
    cdef Serializer _serializer

    def __init__(self, serializer: Serializer):
        self._serializer = serializer

    cpdef inline load(self, value: typing.Any):
        return self._serializer._load(value)

    cpdef inline dump(self, value: typing.Any):
        return self._serializer._dump(value)

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

    cpdef inline load(self, value: typing.Any):
        return self._sequence_type(map(self._item_encoder.load, value))

    cpdef inline dump(self, value: typing.Any):
        return self._sequence_type(map(self._item_encoder.dump, value))


@cython.final
cdef class DictFieldEncoder(FieldEncoder):
    cdef FieldEncoder _key_encoder
    cdef FieldEncoder _value_encoder

    def __init__(self, key_encoder, value_encoder):
        self._key_encoder = key_encoder
        self._value_encoder = value_encoder

    cpdef inline load(self, value: JsonEncodable):
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

    cpdef inline dump(self, value: typing.Any):
        if self._key_encoder and self._value_encoder:
            return {
                self._key_encoder.dump(k): self._value_encoder.dump(v)
                for k, v in value.items()
            }
        elif self._key_encoder and not self._value_encoder:
            return {
                self._key_encoder.dump(k): v
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

    cpdef inline dump(self, value):
        out = value.isoformat()

        # Assume UTC if timezone is missing
        if value.tzinfo is None:
            return out + "+00:00"
        return out

    cpdef inline load(self, value):
        if isinstance(value, datetime.datetime):
            return value
        else:
            return dateutil.parser.parse(typing.cast(str, value))

    @property
    def json_schema(self) -> JsonDict:
        return {"type": "string", "format": "date-time"}


@cython.final
cdef class UuidFieldEncoder(FieldEncoder):

    cpdef inline dump(self, value):
        return str(value)

    cpdef inline load(self, value):
        return uuid.UUID(value)

    @property
    def json_schema(self):
        return {"type": "string", "format": "uuid"}


@cython.final
cdef class UnionFieldEncoder(FieldEncoder):

    cdef list _type_encoders

    def __init__(
        self,
        type_encoders: typing.List[typing.Tuple[typing.ClassVar, FieldEncoder]]
    ):
        self._type_encoders = type_encoders

    cpdef inline dump(self, value):
        for value_type, encoder in self._type_encoders:
            if isinstance(value, value_type):
                return encoder.dump(value) if encoder else value
        raise ValidationError(f"{value_type} is not a Union member")

    cpdef inline load(self, value):
        for value_type, encoder in self._type_encoders:
            if isinstance(value, value_type):
                return encoder.load(value) if encoder else value
        raise ValidationError(f"{value_type} is not a Union member")


class FieldHints(object):
    def __init__(self, dict_key: typing.Optional[str]) -> None:
        self.dict_key = dict_key
