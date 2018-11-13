# -*- coding: utf-8 -*-
# cython: boundscheck=False
# cython: language_level=3
# cython: embedsignature=True
# cython: wraparound=False
# cython: nonecheck=False

import datetime
import enum
import re
import typing
import uuid

import cython
import dateutil.parser
import dataclasses
import rapidjson

from serpyco.decorator import _serpyco_tags, DecoratorType
from serpyco.exception import ValidationError, NoEncoderError, JsonSchemaError
from serpyco.field import FieldHints, _metadata_name
from serpyco.util import JSON_ENCODABLE_TYPES, JsonDict, JsonEncodable
from serpyco.util import _is_generic, _is_optional, _is_union, _issubclass_safe
from serpyco.validator import Validator

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

    def json_schema(self) -> JsonDict:
        """
        Return the JSON schema for this encoder"s handled value type(s).
        """
        raise NotImplementedError()


cdef class SField:
    cdef str field_name
    cdef str dict_key
    cdef FieldEncoder encoder
    cdef object getter

    def __init__(
        self,
        str field_name,
        str dict_key,
        FieldEncoder encoder,
        object getter=None
    ):
        self.field_name = field_name
        self.dict_key = dict_key
        self.encoder = encoder
        self.getter = getter


@cython.final
cdef class Serializer(object):
    """
    Serializer class for dataclasses instances.
    """

    cdef list _fields
    cdef object _dataclass
    cdef bint _many
    cdef bint _omit_none
    cdef object _validator
    cdef list _parent_serializers
    cdef list _pre_dumpers
    cdef list _post_dumpers
    cdef list _pre_loaders
    cdef list _post_loaders
    cdef dict _types
    _global_types = {
        datetime.datetime: DateTimeFieldEncoder(),
        uuid.UUID: UuidFieldEncoder()
    }
    for f, e in _global_types.items():
        Validator.register_global_type(f, e.json_schema())

    def __init__(
        self,
        dataclass: type,
        many: bool=False,
        omit_none: bool=True,
        type_encoders: typing.Dict[type, FieldEncoder]={},
        only: typing.Optional[typing.List[str]]=None,
        _parent_serializers: typing.List["Serializer"]=None
    ):
        """
        Constructs a serializer for the given data class.

        :param dataclass: data class this serializer will handle
        :param many: if True, serializer will handle lists of the dataclass
        :param omit_none: if False, keep None values in the serialized dicts
        :param type_encoders: encoders to use for given types
        :param only: list of fields to serialize.
            If None, all fields are serialized
        """
        if not dataclasses.is_dataclass(dataclass):
            raise TypeError(f"{dataclass} is not a dataclass")
        self._dataclass = dataclass
        self._many = many
        self._omit_none = omit_none
        self._types = type_encoders
        self._parent_serializers = _parent_serializers or []
        self._parent_serializers.append(self)
        type_hints = typing.get_type_hints(dataclass)
        self._fields = []

        for f in dataclasses.fields(dataclass):
            field_type = type_hints[f.name]
            hints = f.metadata.get(_metadata_name, FieldHints(dict_key=f.name))
            if hints.ignore or (only and f.name not in only):
                continue
            if hints.dict_key is None:
                hints.dict_key = f.name
            encoder = self._get_encoder(field_type)
            self._fields.append(SField(
                f.name,
                hints.dict_key,
                encoder,
                hints.getter
            ))

        self._validator = Validator(
            dataclass,
            many=many,
            only=only,
            type_schemas={
                type_: encoder.json_schema()
                for type_, encoder in self._types.items()
            }
        )

        # pre/post load/dump methods
        self._post_dumpers = []
        self._pre_dumpers = []
        self._post_loaders = []
        self._pre_loaders = []
        for attr_name in dir(dataclass):
            attr = getattr(dataclass, attr_name)
            try:
                tag = getattr(attr, _serpyco_tags)
                if DecoratorType.POST_DUMP==tag:
                    self._post_dumpers.append(attr)
                elif DecoratorType.PRE_DUMP==tag:
                    self._pre_dumpers.append(attr)
                elif DecoratorType.POST_LOAD==tag:
                    self._post_loaders.append(attr)
                elif DecoratorType.PRE_LOAD==tag:
                    self._pre_loaders.append(attr)
                else:
                    raise ValueError(f"Unknown decorator type {tag}")
            except AttributeError:
                continue

    def json_schema(self) -> JsonDict:
        """
        Returns the JSON schema of the underlying validator.
        """
        return self._validator.json_schema()

    @classmethod
    def register_global_type(
        cls,
        field_type: type,
        encoder: FieldEncoder
    ) -> None:
        """
        Registers a encoder/decoder for the given type.
        """
        cls._global_types[field_type] = encoder
        Validator.register_global_type(field_type, encoder.json_schema())

    @classmethod
    def unregister_global_type(cls, field_type: type) -> None:
        """
        Removes a previously registered encoder for the given type.
        """
        del cls._global_types[field_type]
        Validator.unregister_global_type(field_type)

    def dataclass(self) -> type:
        """
        Returns the dataclass used to construct this serializer.
        """
        return self._dataclass

    cpdef inline dump(
        self,
        obj: typing.Union[object, typing.Iterable[object]],
        validate: bool=False
    ):
        """
        Dumps the object(s) in the form of a dict/list only
        composed of builtin python types.

        :param validate: if True, the dumped data will be validated.
        """
        cdef list objs
        if self._many:
            objs = obj
            for pre_dump in self._pre_dumpers:
                objs = map(pre_dump, objs)
            data = [self._dump(o) for o in objs]
            for post_dump in self._post_dumpers:
                data = map(post_dump, data)
        else:
            for pre_dump in self._pre_dumpers:
                obj = pre_dump(obj)
            data = self._dump(obj)
            for post_dump in self._post_dumpers:
                data = post_dump(data)
        
        if validate:
            self._validator.validate(data)
        
        return data

    cpdef inline load(
        self,
        data: typing.Union[dict, typing.Iterable[dict]],
        validate: bool=True
    ):
        """
        Loads the given data and returns object(s) of this serializer's
        dataclass.

        :param validate: if True, the data will be validated before
            creating objects
        """
        cdef list datas
        cdef object obj
        if validate:
            self._validator.validate(data)

        if self._many:
            datas = data
            for pre_load in self._pre_loaders:
                datas = map(pre_load, datas)
            objs = [self._load(d) for d in datas]
            for post_load in self._post_loaders:
                objs = map(post_load, objs)
            return objs
        
        for pre_load in self._pre_loaders:
            data = pre_load(data)
        obj = self._load(data)
        for post_load in self._post_loaders:
            obj = post_load(obj)
        return obj

    cpdef inline str dump_json(
        self,
        obj: typing.Union[object, typing.Iterable[object]],
        validate: bool=False
    ):
        """
        Dumps the object(s) in the form of a JSON string.

        :param validate: if True, the dumped data will be validated
        """
        cdef list objs
        if self._many:
            objs = obj
            for pre_dump in self._pre_dumpers:
                objs = map(pre_dump, objs)
            data = [self._dump(o) for o in objs]
            for post_dump in self._post_dumpers:
                data = map(post_dump, data)
        else:
            for pre_dump in self._pre_dumpers:
                obj = pre_dump(obj)
            data = self._dump(obj)
            for post_dump in self._post_dumpers:
                data = post_dump(data)

        js = rapidjson.dumps(data)
        
        if validate:
            self._validator.validate_json(js)

        return js

    cpdef inline load_json(self, js: str, validate: bool=True):
        """
        Loads the given JSON string and returns object(s) of this serializer's
        dataclass.

        :param validate: if True, the JSON will be validated before
            creating objects
        """
        cdef list datas
        cdef list objs
        cdef object obj
        if validate:
            self._validator.validate_json(js)

        data = rapidjson.loads(js)
        if self._many:
            datas = data
            for pre_load in self._pre_loaders:
                datas = map(pre_load, datas)
            objs = [self._load(d) for d in datas]
            for post_load in self._post_loaders:
                objs = map(post_load, objs)
            return objs
        
        for pre_load in self._pre_loaders:
            data = pre_load(data)
        obj = self._load(data)
        for post_load in self._post_loaders:
            obj = post_load(obj)
        return obj

    cdef inline dict _dump(self, object obj):
        cdef dict data = {}
        cdef SField sfield
        for sfield in self._fields:
            if sfield.getter:
                encoded = sfield.getter(obj)
            else:
                encoded = getattr(obj, sfield.field_name)
            if encoded is None:
                if self._omit_none:
                    continue
            elif sfield.encoder:
                encoded = sfield.encoder.dump(encoded)
            data[sfield.dict_key] = encoded
        return data

    cdef inline object _load(self, dict data):
        cdef dict decoded_data = {}
        cdef SField sfield
        get_data = data.get
        for sfield in self._fields:
            decoded = get_data(sfield.dict_key)
            if decoded is None:
                if self._omit_none:
                    continue
            elif sfield.encoder:
                decoded = sfield.encoder.load(decoded)
            decoded_data[sfield.field_name] = decoded
        return self._dataclass(**decoded_data)

    def _get_encoder(self, field_type):
        if field_type in self._types:
            return self._types[field_type]
        elif field_type in self._global_types:
            return self._global_types[field_type]
        elif _issubclass_safe(field_type, enum.Enum):
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
        elif _is_generic(field_type, typing.Mapping):
            key_encoder = self._get_encoder(field_type.__args__[0])
            value_encoder = self._get_encoder(field_type.__args__[1])
            if key_encoder or value_encoder:
                return DictFieldEncoder(key_encoder, value_encoder)
            return None
        elif _is_generic(field_type, typing.Iterable):
            item_encoder = self._get_encoder(field_type.__args__[0])
            return IterableFieldEncoder(item_encoder, field_type)
        elif dataclasses.is_dataclass(field_type):
            # See if one of our "ancestors" handles this type.
            # This avoids infinite recursion if dataclasses establish a cycle
            for serializer in self._parent_serializers:
                if serializer.dataclass() == field_type:
                    break
            else:
                serializer = Serializer(
                    field_type,
                    omit_none=self._omit_none,
                    type_encoders=self._types,
                    _parent_serializers=self._parent_serializers,
                )
            return DataClassFieldEncoder(serializer)
        raise NoEncoderError(f"No encoder for '{field_type}'")


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
cdef class IterableFieldEncoder(FieldEncoder):
    cdef FieldEncoder _item_encoder
    cdef object _iterable_type

    _iterable_types_mapping = {
        typing.Tuple: tuple,
        typing.List: list,
        typing.Set: set,
    }

    def __init__(self, item_encoder, sequence_type):
        self._item_encoder = item_encoder

        self._iterable_type = self._iterable_types_mapping.get(
            sequence_type.__origin__,
            sequence_type.__origin__
        )

    cpdef inline load(self, value: typing.Any):
        if self._item_encoder:
            return self._iterable_type(map(self._item_encoder.load, value))
        return self._iterable_type(value)

    cpdef inline dump(self, value: typing.Any):
        if self._item_encoder:
            return self._iterable_type(map(self._item_encoder.dump, value))
        return self._iterable_type(value)


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

    def json_schema(self) -> JsonDict:
        return {"type": "string", "format": "date-time"}


@cython.final
cdef class UuidFieldEncoder(FieldEncoder):

    cpdef inline dump(self, value):
        return str(value)

    cpdef inline load(self, value):
        return uuid.UUID(value)

    def json_schema(self):
        return {"type": "string", "format": "uuid"}


@cython.final
cdef class UnionFieldEncoder(FieldEncoder):

    cdef list _type_encoders

    def __init__(
        self,
        type_encoders: typing.List[typing.Tuple[type, FieldEncoder]]
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
