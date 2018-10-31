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

JSON_ENCODABLE_TYPES = {
    str: {'type': 'string'},
    int: {'type': 'number', 'format': 'integer'},
    bool: {'type': 'boolean'},
    float: {'type': 'number', 'format': 'float'}
}

JsonEncodable = typing.Union[int, float, str, bool]
JsonDict = typing.Dict[str, typing.Any]


def issubclass_safe(field_type, classes) -> bool:
    try:
        return issubclass(field_type, classes)
    except (TypeError, AttributeError):
        return False


def is_optional(field_type) -> bool:
    field_type_name = str(field_type)
    return (
        field_type_name.startswith("Union") or
        field_type_name.startswith("typing.Union")
    ) and issubclass(field_type.__args__[1], type(None))

class JsonSchemaError(Exception):
    pass



cdef class FieldEncoder(object):
    """Base class for encoding fields to and from JSON encodable values"""

    cpdef to_wire(self, value: typing.Any):
        raise NotImplementedError()

    cpdef to_python(self, value: typing.Any):
        return value

    @property
    def json_schema(self) -> JsonDict:
        raise NotImplementedError()


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

    def __init__(self, data_class):
        self._serializer = Serializer(data_class)

    cpdef inline to_python(self, value: typing.Any):
        return self._serializer._from_dict(value)

    cpdef inline to_wire(self, value: typing.Any):
        return self._serializer._to_dict(value, omit_none=True)

    def json_schema(self) -> JsonDict:
        return self.serializer.json_schema()


@cython.final
cdef class ListFieldEncoder(FieldEncoder):
    cdef FieldEncoder _item_encoder

    def __init__(self, item_encoder):
        self._item_encoder = item_encoder

    cpdef inline to_python(self, value: typing.Any):
        return [self._item_encoder.to_python(v) for v in value]

    cpdef inline to_wire(self, value: typing.Any):
        return [self._item_encoder.to_wire(v) for v in value]


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
        out = value.isoformat(timespec='seconds')

        # Assume UTC if timezone is missing
        if value.tzinfo is None:
            return out + "Z"
        return out

    cpdef inline to_python(self, value):
        if isinstance(value, datetime):
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
        return {'type': 'string', 'format': 'uuid'}


class FieldHints(object):
    def __init__(self, dict_key: typing.Optional[str]) -> None:
        self.dict_key = dict_key


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

    cdef list _fields
    cdef object _data_class
    cdef dict _json_schema
    cdef object _validator
    _field_encoders = {datetime: DateTimeFieldEncoder(), uuid.UUID: UuidFieldEncoder()}

    def __init__(self, data_class):
        self._data_class = data_class
        type_hints = typing.get_type_hints(data_class)
        self._fields = []
        for f in dataclasses.fields(data_class):
            if f.name.startswith("_"):
                continue
            field_type = type_hints[f.name]
            hints = f.metadata.get(__name__, FieldHints(dict_key=f.name))
            self._fields.append((f.name, hints.dict_key, self._get_encoder(field_type)))
        
        self._json_schema = self._create_json_schema(data_class, type_hints)
        self._validator = rapidjson.Validator(rapidjson.dumps(self._json_schema))

    @classmethod
    def register_encoder(cls, field_type: typing.ClassVar, encoder: FieldEncoder):
        cls._field_encoders[field_type] = encoder

    def json_schema(self):
        return self._json_schema

    cpdef inline dict to_dict(self, obj: typing.Any, validate: bool=False, omit_none: bool=True):
        data = self._to_dict(obj, omit_none)
        if validate:
            js = rapidjson.dumps(data)
            self._validator(js)
        return data
    
    cpdef inline object from_dict(self, data: dict, validate: bool=True):
        if validate:
            js = rapidjson.dumps(data)
            self._validator(js)
        return self._from_dict(data)

    cpdef inline str to_json(self, obj: typing.Any, omit_none: bool=True, validate: bool=False):
        js = rapidjson.dumps(self._to_dict(obj, omit_none))
        if validate:
            self._validator(js)
        return js

    cpdef inline object from_json(self, js: str, validate: bool=True):
        if validate:
            self._validator(js)
        d = rapidjson.loads(js)
        return self._from_dict(d)

    cdef inline dict _to_dict(self, obj: typing.Any, omit_none: bool):
        data = {}
        for field_name, dict_key, encoder in self._fields:
            value = getattr(obj, field_name)
            if value is None:
                if omit_none:
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

    @classmethod
    def _get_encoder(cls, field_type):
        try:
            return cls._field_encoders[field_type]
        except:
            pass
        if issubclass_safe(field_type, tuple(JSON_ENCODABLE_TYPES.keys())):
            return None
        elif is_optional(field_type):
            return cls._get_encoder(field_type.__args__[0])
        elif issubclass_safe(field_type, enum.Enum):
            return EnumFieldEncoder(field_type)
        elif issubclass_safe(field_type, (typing.Mapping, typing.Dict)):
            key_encoder = cls._get_encoder(field_type.__args__[0])
            value_encoder = cls._get_encoder(field_type.__args__[1])
            return DictFieldEncoder(key_encoder, value_encoder)
        elif issubclass_safe(field_type, (typing.Sequence, typing.List)):
            item_encoder = cls._get_encoder(field_type.__args__[0])
            if item_encoder:
                return ListFieldEncoder(item_encoder)
            else:
                return None
        elif dataclasses.is_dataclass(field_type):
            return DataClassFieldEncoder(field_type)
        else:
            return None

    @classmethod
    def _get_field_schema(cls, field_type: typing.Any) -> typing.Tuple[JsonDict, bool]:
        field_schema: JsonDict = {'type': 'object'}
        required = True
        field_type_name = cls._get_field_type_name(field_type)
        if dataclasses.is_dataclass(field_type):
            field_schema = {
                'type': 'object',
                '$ref': '#/definitions/{}'.format(field_type_name)
            }
        else:
            if is_optional(field_type):
                field_schema = cls._get_field_schema(field_type.__args__[0])[0]
                required = False
            elif field_type in JSON_ENCODABLE_TYPES:
                field_schema = JSON_ENCODABLE_TYPES[field_type]
            elif issubclass_safe(field_type, enum.Enum):
                member_types = set()
                values = []
                for member in field_type:
                    member_types.add(type(member.value))
                    values.append(member.value)
                if len(member_types) == 1:
                    member_type = member_types.pop()
                    if member_type in JSON_ENCODABLE_TYPES:
                        field_schema.update(JSON_ENCODABLE_TYPES[member_type])
                    else:
                        field_schema.update(cls._field_encoders[member_types.pop()].json_schema)
                field_schema['enum'] = values
            elif issubclass_safe(field_type, (typing.Dict, typing.Mapping)):
                field_schema = {'type': 'object'}
                if field_type.__args__[1] is not typing.Any:
                    field_schema['additionalProperties'] = cls._get_field_schema(field_type.__args__[1])[0]
            elif issubclass_safe(field_type, (typing.Sequence, typing.List)):
                field_schema = {'type': 'array'}
                if field_type.__args__[0] is not typing.Any:
                    field_schema['items'] = cls._get_field_schema(field_type.__args__[0])[0]
            elif field_type in cls._field_encoders:
                field_schema.update(cls._field_encoders[field_type].json_schema)
            elif hasattr(field_type, '__supertype__'):  # NewType fields
                field_schema, _ = cls._get_field_schema(field_type.__supertype__)
            else:
                raise JsonSchemaError(f"Unable to create schema for '{field_type}'")
        return field_schema, required

    def _create_json_schema(self, data_class, type_hints, embeddable=False) -> dict:
        """Returns the JSON schema for the dataclass, along with the schema of any nested dataclasses
        within the 'definitions' field.

        Enable the embeddable flag to generate the schema in a format for embedding into other schemas
        or documents supporting JSON schema such as Swagger specs
        """
        definitions: JsonDict = {}

        properties = {}
        required = []
        for field_name, dict_key, _ in self._fields:
            field_type = type_hints[field_name]
            properties[dict_key], is_required = self._get_field_schema(field_type)
            item_type = field_type
            if is_optional(field_type):
                item_type = field_type.__args__[0]
            elif issubclass_safe(field_type, (typing.Dict, typing.Mapping)):
                item_type = field_type.__args__[1]
            elif issubclass_safe(field_type, (typing.Sequence, typing.List)) and not issubclass_safe(field_type, str):
                item_type = field_type.__args__[0]
            
            if dataclasses.is_dataclass(item_type):
                # Prevent recursion from forward refs & circular type dependencies
                if item_type.__name__ not in definitions:
                    item_type_hints = typing.get_type_hints(item_type)
                    ser = Serializer(item_type)
                    definitions[item_type.__name__] = None
                    definitions.update(ser._create_json_schema(item_type, item_type_hints, embeddable=True))
            if is_required:
                required.append(dict_key)
        schema = {
            'type': 'object',
            'required': required,
            'properties': properties
        }
        if len(required) == 0:
            del schema["required"]
        if data_class.__doc__:
            schema['description'] = data_class.__doc__

        if embeddable:
            schema = {**definitions, data_class.__name__: schema}
        else:
            schema = {**schema, **{
                'definitions': definitions,
                '$schema': 'http://json-schema.org/draft-04/schema#'
            }}

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