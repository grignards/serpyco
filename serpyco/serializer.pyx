# -*- coding: utf-8 -*-
# cython: language_level=3
# cython: embedsignature=True
# cython: wraparound=False
# cython: nonecheck=False
# cython: boundscheck=False


import dataclasses
import datetime
import enum
import re
import typing
import uuid

import cython
import dateutil.parser
import rapidjson
import typing_inspect

from serpyco.decorator import DecoratorType, _serpyco_tags

from serpyco.encoder cimport FieldEncoder

from serpyco.exception import NoEncoderError, NotADataClassError, ValidationError
from serpyco.field import FieldHints, _metadata_name
from serpyco.schema import SchemaBuilder
from serpyco.util import (
    JSON_ENCODABLE_TYPES,
    UNTYPED_DICT_TYPES,
    UNTYPED_ITERABLE_TYPES,
    JsonDict,
    JsonEncodable,
    _DataClassParams,
    _is_generic,
    _is_union,
    _issubclass_safe,
)
from serpyco.validator import RapidJsonValidator


cdef object dataclasses_MISSING = dataclasses.MISSING
cdef object new_object = object.__new__
_ITERABLE_TYPES_MAPPING = {
    typing.Tuple: tuple,
    typing.List: list,
    typing.Set: set,
}

cdef class SerializerField:
    cdef str field_name
    cdef str dict_key
    cdef FieldEncoder encoder
    cdef object getter
    cdef bint init
    cdef object default
    cdef object default_factory

    def __init__(
        self,
        str field_name,
        str dict_key,
        FieldEncoder encoder,
        object getter,
        bint init,
        object default,
        object default_factory
    ):
        self.field_name = field_name
        self.dict_key = dict_key
        self.encoder = encoder
        self.getter = getter
        self.init = init
        self.default = default
        self.default_factory = default_factory


cdef class Caster(object):
    cdef str dict_key
    cdef object caster

    def __cinit__(self, str dict_key, object caster):
        self.dict_key = dict_key
        self.caster = caster

cdef inline int cast_fields(tuple casters, dict data) except -1:
    cdef Caster caster
    for caster in casters:
        try:
            v = data[caster.dict_key]
        except KeyError:
            continue
        if _is_union(caster.caster):
            types = list(typing_inspect.get_args(caster.caster, evaluate=True))
            types.remove(type(None))
        else:
            types = [caster.caster]
        casted = None
        exc = None
        for type_ in types:
            try:
                casted = type_(v)
                break
            except Exception as ex:
                exc = ex
        if casted is None:
            raise ValidationError(f"Could not cast field {caster.dict_key}: {exc}")
        data[caster.dict_key] = casted


@cython.final
cdef class Serializer(object):
    """
    Serializer class for dataclasses instances.
    """

    cdef tuple _fields
    cdef object _dataclass_params
    cdef object _dataclass
    cdef bint _frozen_dataclass
    cdef bint _has_post_init
    cdef object _validator
    cdef list _parent_serializers
    cdef list _pre_dumpers
    cdef list _post_dumpers
    cdef list _pre_loaders
    cdef list _post_loaders
    cdef tuple _field_casters
    cdef dict _field_encoders
    cdef dict _type_encoders
    cdef object _load_as_type
    cdef list _only
    cdef tuple _excluded_fields
    _global_types = {
        datetime.datetime: DateTimeFieldEncoder(),
        uuid.UUID: UuidFieldEncoder()
    }
    for f, e in _global_types.items():
        SchemaBuilder.register_global_type(f, e)

    def __cinit__(
        self,
        dataclass,
        omit_none: bool = True,
        type_encoders: typing.Dict[type, FieldEncoder] = None,
        only: typing.Optional[typing.List[str]] = None,
        exclude: typing.Optional[typing.List[str]] = None,
        strict: bool = False,
        load_as_type: typing.Optional[type] = None,
        _parent_serializers: typing.List["Serializer"] = None
    ):
        """
        Constructs a serializer for the given data class.

        :param dataclass: data class this serializer will handle
        :param many: if True, serializer will handle lists of the dataclass
        :param omit_none: if False, keep None values in the serialized dicts
        :param type_encoders: encoders to use for given types
        :param only: list of fields to serialize.
            If None, all fields are serialized
        :param exclude: list of fields to exclude from serialization.
            If None, all fields are serialized
        :param strict: if true, unknown properties of an object will make the
            validation fail
        """
        cdef Serializer parent
        cdef SerializerField field
        self._dataclass_params = _DataClassParams(dataclass)
        self._dataclass = self._dataclass_params.type_
        self._type_encoders = type_encoders or {}
        self._parent_serializers = _parent_serializers or []
        self._parent_serializers.append(self)
        self._excluded_fields = tuple()
        fields = []
        excluded_fields = []
        field_casters = []
        type_hints = typing.get_type_hints(self._dataclass)
        self._field_encoders = {}
        for f in dataclasses.fields(self._dataclass):
            hints = f.metadata.get(_metadata_name, FieldHints(dict_key=f.name))
            if hints.dict_key is None:
                hints.dict_key = f.name

            field = SerializerField(
                f.name,
                hints.dict_key,
                None,
                hints.getter,
                f.init,
                f.default,
                f.default_factory
            )
            if (
                hints.ignore
                or (only and f.name not in only)
                or (exclude and f.name in exclude)
            ):
                excluded_fields.append(field)
            else:
                field_type = self._dataclass_params.resolve_type(type_hints[f.name])
                encoder = self._get_encoder(field_type, hints)
                if encoder:
                    self._field_encoders[field_type] = encoder
                    field.encoder = encoder
                if hints.cast_on_load:
                    field_casters.append(Caster(hints.dict_key, field_type))
                fields.append(field)

        self._fields = tuple(fields)
        self._excluded_fields = tuple(excluded_fields)

        field_encoders = {}
        for parent in self._parent_serializers:
            field_encoders.update(parent._field_encoders)
        builder = SchemaBuilder(
            dataclass,
            only=only,
            exclude=exclude,
            type_encoders={**self._global_types, **self._type_encoders},
            strict=strict,
        )
        self._validator = RapidJsonValidator(builder)

        # pre/post load/dump methods
        self._post_dumpers = []
        self._pre_dumpers = []
        self._post_loaders = []
        self._pre_loaders = []
        for attr_name in dir(self._dataclass):
            attr = getattr(self._dataclass, attr_name)
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
        self._field_casters = tuple(field_casters)
        self._load_as_type = load_as_type or self._dataclass
        # Check if the dataclass is frozen or not
        try:
            if self._fields:
                field = self._fields[0]
                obj = new_object(self._load_as_type)
                setattr(obj, field.field_name, None)
            self._frozen_dataclass = False
        except dataclasses.FrozenInstanceError:
            self._frozen_dataclass = True
        self._has_post_init = hasattr(self._dataclass, "__post_init__")

    def __hash__(self):
        cdef SerializerField sfield
        excluded_field_names = []
        for sfield in self._excluded_fields:
            excluded_field_names.append(sfield.field_name)
        return hash((
            self._dataclass,
            self._dataclass_params.arguments,
            tuple(excluded_field_names)
        ))

    def json_schema(self, many: bool = False) -> JsonDict:
        """
        Returns the JSON schema of the underlying validator.
        """
        return self._validator.json_schema(many=many)

    def get_dict_path(self, obj_path: typing.Sequence[str]) -> typing.List[str]:
        """
        Returns the path of a field in dumped dictionaries.
        :param obj_path: list of field names, for example
        ["foo", "bar"] to get the dict path of foo.bar
        """
        cdef SerializerField sfield
        cdef Serializer ser
        part = obj_path[0]
        for sfield in self._fields:
            if sfield.field_name==part:
                break
        else:
            raise KeyError(f"Unknown field {part} in {self._dataclass}")

        if 1 == len(obj_path):
            return [sfield.dict_key]

        ser = self._get_field_serializer(sfield)
        return [sfield.dict_key] + ser.get_dict_path(obj_path[1:])

    def get_object_path(self, dict_path: typing.Sequence[str]) -> typing.List[str]:
        """
        Returns the path of a field in loaded objects.
        :param dict_path: list of dictionary keys, for example
        ["foo", "bar"] to get the object path of {"foo": {"bar": 42}}
        """
        cdef SerializerField sfield
        cdef Serializer ser
        part = dict_path[0]
        for sfield in self._fields:
            if sfield.dict_key==part:
                break
        else:
            raise KeyError(f"Unknown dict key {part} in {self._dataclass}")

        if 1 == len(dict_path):
            return [sfield.field_name]

        ser = self._get_field_serializer(sfield)
        return [sfield.field_name] + ser.get_object_path(dict_path[1:])

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
        SchemaBuilder.register_global_type(field_type, encoder.json_schema())

    @classmethod
    def unregister_global_type(cls, field_type: type) -> None:
        """
        Removes a previously registered encoder for the given type.
        """
        del cls._global_types[field_type]
        SchemaBuilder.unregister_global_type(field_type)

    def dataclass(self) -> type:
        """
        Returns the dataclass used to construct this serializer.
        """
        return self._dataclass

    cpdef inline dump(
        self,
        obj: typing.Union[object, typing.Iterable[object]],
        bint validate: bool=False,
        bint many: bool=False,
    ):
        """
        Dumps the object(s) in the form of a dict/list only
        composed of builtin python types.

        :param validate: if True, the dumped data will be validated.
        """
        cdef list objs
        if many:
            objs = obj
            for pre_dump in self._pre_dumpers:
                objs = map(pre_dump, objs)
            data = [self._dump(o) for o in objs]
        else:
            for pre_dump in self._pre_dumpers:
                obj = pre_dump(obj)
            data = self._dump(obj)

        if validate:
            self._validator.validate(data, many=many)
            self._validator.validate_user(data, many=many)

        if many:
            for post_dump in self._post_dumpers:
                data = map(post_dump, data)
        else:
            for post_dump in self._post_dumpers:
                data = post_dump(data)

        return data

    cpdef inline load(
        self,
        data: typing.Union[dict, typing.Iterable[dict]],
        bint validate: bool=True,
        bint many: bool=False,
    ):
        """
        Loads the given data and returns object(s) of this serializer's
        dataclass.

        :param validate: if True, the data will be validated before
            creating objects
        """
        cdef list datas
        cdef list objs
        cdef object obj

        if many:
            datas = data
            if self._field_casters:
                for data in datas:
                    cast_fields(self._field_casters, data)
            for pre_load in self._pre_loaders:
                datas = map(pre_load, datas)
            data = datas
        else:
            if self._field_casters:
                cast_fields(self._field_casters, data)
            for pre_load in self._pre_loaders:
                data = pre_load(data)

        if validate:
            self._validator.validate(data, many=many)
            self._validator.validate_user(data, many=many)

        if many:
            objs = [self._load(d) for d in datas]
            for post_load in self._post_loaders:
                objs = map(post_load, objs)
            return objs

        obj = self._load(data)
        for post_load in self._post_loaders:
            obj = post_load(obj)
        return obj

    cpdef inline str dump_json(
        self,
        obj: typing.Union[object, typing.Iterable[object]],
        bint validate: bool=False,
        bint many: bool=False
    ):
        """
        Dumps the object(s) in the form of a JSON string.

        :param validate: if True, the dumped data will be validated
        """
        cdef list objs

        if many:
            objs = obj
            for pre_dump in self._pre_dumpers:
                objs = map(pre_dump, objs)
            data = [self._dump(o) for o in objs]
        else:
            for pre_dump in self._pre_dumpers:
                obj = pre_dump(obj)
            data = self._dump(obj)

        # Needed to validate
        js = rapidjson.dumps(data)

        if validate:
            self._validator.validate_json(js, many=many)
            self._validator.validate_user(data, many=many)

        if not self._post_dumpers:
            return js

        if many:
            for post_dump in self._post_dumpers:
                data = map(post_dump, data)
        else:
            for post_dump in self._post_dumpers:
                data = post_dump(data)

        # We need to dump in JSON again as post_dump can modify data.
        return rapidjson.dumps(data)

    cpdef inline load_json(
        self,
        str js,
        bint validate: bool=True,
        bint many: bool=False
    ):
        """
        Loads the given JSON string and returns object(s) of this serializer's
        dataclass.

        :param validate: if True, the JSON will be validated before
            creating objects
        """
        cdef list datas
        cdef list objs
        cdef object obj

        data = rapidjson.loads(js)

        if many:
            datas = data
            if self._field_casters:
                for data in datas:
                    cast_fields(self._field_casters, data)
            for pre_load in self._pre_loaders:
                datas = map(pre_load, datas)
            data = datas
        else:
            if self._field_casters:
                cast_fields(self._field_casters, data)
            for pre_load in self._pre_loaders:
                data = pre_load(data)

        if validate:
            self._validator.validate(data, many=many)
            self._validator.validate_user(data, many=many)

        if many:
            objs = [self._load(d) for d in datas]
            for post_load in self._post_loaders:
                objs = map(post_load, objs)
            return objs
        obj = self._load(data)
        for post_load in self._post_loaders:
            obj = post_load(obj)
        return obj

    cdef inline dict _dump(self, object obj):
        cdef SerializerField sfield
        cdef object encoded
        cdef dict data = {}
        for sfield in self._fields:
            if sfield.getter is not None:
                encoded = sfield.getter(obj)
            else:
                encoded = getattr(obj, sfield.field_name)
            if sfield.encoder is not None and encoded is not None:
                encoded = sfield.encoder.dump(encoded)
            data[sfield.dict_key] = encoded
        return data

    cdef inline object _load(self, dict data):
        cdef SerializerField sfield
        cdef object decoded
        cdef object obj
        obj = new_object(self._load_as_type)
        for sfield in self._fields:
            try:
                decoded = data[sfield.dict_key]
                if sfield.encoder is not None and decoded is not None:
                    decoded = sfield.encoder.load(decoded)
            except KeyError:
                if sfield.default is not dataclasses_MISSING:
                    decoded = sfield.default
                elif sfield.default_factory is not dataclasses_MISSING:
                    decoded = sfield.default_factory()
                else:
                    raise TypeError(
                        "data dictionary is missing "
                        f"required parameter '{sfield.field_name}' "
                        f"for class '{self._dataclass.__qualname__}'"
                    )
            # Cannot use setattr() on frozen dataclasses
            if not self._frozen_dataclass:
                setattr(obj, sfield.field_name, decoded)
            else:
                object.__setattr__(obj, sfield.field_name, decoded)
        for sfield in self._excluded_fields:
            if sfield.default is not dataclasses.MISSING:
                decoded = sfield.default
            elif sfield.default_factory is not dataclasses.MISSING:
                decoded = sfield.default_factory()
            else:
                raise TypeError(
                    f"Cannot create '{self._dataclass.__qualname__}' as "
                    f"'{sfield.field_name}' is excluded but has no "
                    "default value/factory"
                )
            # Cannot use setattr() on frozen dataclasses
            if not self._frozen_dataclass:
                setattr(obj, sfield.field_name, decoded)
            else:
                object.__setattr__(obj, sfield.field_name, decoded)
        if self._has_post_init:
            obj.__post_init__()
        return obj

    def _get_field_serializer(self, sfield: SerializerField) -> "Serializer":
        cdef FieldEncoder encoder = sfield.encoder
        cdef DataClassFieldEncoder dencoder
        cdef IterableFieldEncoder iter_encoder
        cdef DataClassIterableFieldEncoder diter_encoder
        cdef DictFieldEncoder dict_encoder
        encoder = sfield.encoder
        if isinstance(encoder, IterableFieldEncoder):
            iter_encoder = encoder
            dencoder = iter_encoder._item_encoder
            return dencoder._serializer
        elif isinstance(encoder, DataClassIterableFieldEncoder):
            diter_encoder = encoder
            return diter_encoder._serializer
        elif isinstance(encoder, DictFieldEncoder):
            dict_encoder = encoder
            dencoder = dict_encoder._value_encoder
            return dencoder._serializer
        elif isinstance(encoder, DataClassFieldEncoder):
            dencoder = encoder
            return dencoder._serializer
        raise ValueError(f"field {sfield.field_name} is not a dataclass")

    def _get_encoder(self, field_type, hints):
        cdef DataClassFieldEncoder dencoder
        field_type = self._dataclass_params.resolve_type(field_type)
        args = typing_inspect.get_args(field_type, evaluate=True)

        if field_type in self._type_encoders:
            return self._type_encoders[field_type]
        elif field_type in self._global_types:
            return self._global_types[field_type]
        elif typing.Any == field_type:
            return None
        elif _issubclass_safe(field_type, enum.Enum):
            # Must be first as enums can inherit from another type
            return EnumFieldEncoder(field_type)
        elif _issubclass_safe(field_type, tuple(JSON_ENCODABLE_TYPES.keys())):
            return None
        elif _is_union(field_type):
            args = list(typing_inspect.get_args(field_type, evaluate=True))
            try:
                args.remove(type(None))
            except ValueError:
                pass
            type_encoders = [
                (item_type, self._get_encoder(item_type, hints))
                for item_type in args
            ]
            if not args:
                return None
            elif len(args)== 1:
                return type_encoders[0][1]
            else:
                return UnionFieldEncoder(type_encoders)
        elif field_type in UNTYPED_DICT_TYPES:
            return None
        elif _is_generic(field_type, typing.Mapping):
            key_encoder = self._get_encoder(args[0], hints)
            value_encoder = self._get_encoder(args[1], hints)
            if key_encoder or value_encoder:
                return DictFieldEncoder(key_encoder, value_encoder)
            return None
        elif (
            _is_generic(field_type, typing.Tuple)
            and (
                len(args)!=2
                or args[len(args)-1] is not ...
            )
        ):
            # Special case for tuple with fixed-length argument list
            item_encoders = [
                self._get_encoder(arg_type, hints)
                for arg_type in args
            ]
            return FixedTupleFieldEncoder(item_encoders)
        elif field_type in UNTYPED_ITERABLE_TYPES:
            return IterableFieldEncoder(None, field_type)
        # tuples defined with ... are handled by the following elif
        elif _is_generic(field_type, typing.Iterable):
            item_encoder = self._get_encoder(args[0], hints)
            if isinstance(item_encoder, DataClassFieldEncoder):
                dencoder = item_encoder
                return DataClassIterableFieldEncoder(dencoder._serializer, field_type)
            return IterableFieldEncoder(item_encoder, field_type)
        # Is the field a dataclass ?
        try:
            params = _DataClassParams(field_type)
        except NotADataClassError:
            raise NoEncoderError(f"No encoder for '{field_type}'")

        # See if one of our "ancestors" handles this dataclass.
        # This avoids infinite recursion if dataclasses establish a cycle
        for serializer in self._parent_serializers:
            excluded_field_names = tuple(
                f.name for f in dataclasses.fields(params.type_)
                if (
                    hints.ignore
                    or (hints.only and f.name not in hints.only)
                    or (hints.exclude and f.name in hints.exclude)
                )
            )
            sh = hash(serializer)
            h = hash((params.type_, params.arguments, excluded_field_names))
            if h == sh:
                break
        else:
            serializer = Serializer(
                field_type,
                type_encoders=hints.type_encoders or self._type_encoders,
                only=hints.only,
                exclude=hints.exclude,
                load_as_type=hints.load_as_type,
                _parent_serializers=self._parent_serializers,
            )
        return DataClassFieldEncoder(serializer)


# builtin field encoders
@cython.final
cdef class EnumFieldEncoder(FieldEncoder):
    cdef object _enum_type

    def __cinit__(self, enum_type):
        self._enum_type = enum_type

    cpdef inline dump(self, value: typing.Any):
        return value.value

    cpdef inline load(self, value: typing.Any):
        return self._enum_type(value)

    def json_schema(self) -> JsonDict:
        return None


@cython.final
cdef class DataClassFieldEncoder(FieldEncoder):
    cdef Serializer _serializer

    def __cinit__(self, Serializer serializer):
        self._serializer = serializer

    cpdef inline load(self, value):
        return self._serializer._load(value)

    cpdef inline dump(self, value):
        return self._serializer._dump(value)

    def json_schema(self) -> JsonDict:
        return None


@cython.final
cdef class DataClassIterableFieldEncoder(FieldEncoder):
    cdef Serializer _serializer
    cdef object _iterable_type

    def __cinit__(self, serializer, sequence_type):
        origin = typing_inspect.get_origin(sequence_type)
        self._iterable_type = _ITERABLE_TYPES_MAPPING.get(origin, origin)
        self._serializer = serializer

    cpdef inline load(self, value):
        cdef lst = [
            self._serializer._load(v)
            if v is not None
            else None
            for v in value
        ]
        return self._iterable_type(lst)

    cpdef inline dump(self, value):
        return [
            self._serializer._dump(v)
            if v is not None
            else None
            for v in value
        ]

    def json_schema(self) -> JsonDict:
        return None


@cython.final
cdef class FixedTupleFieldEncoder(FieldEncoder):
    cdef tuple _item_encoders
    cdef int _item_encoders_count

    def __cinit__(self, item_encoders):
        self._item_encoders = tuple(item_encoders)
        self._item_encoders_count = len(self._item_encoders)

    cpdef inline load(self, value: typing.Any):
        cdef FieldEncoder encoder
        cdef int i
        decoded = []
        if len(value) != self._item_encoders_count:
            raise ValidationError("Invalid number of items for tuple")
        for i in range(0, self._item_encoders_count):
            encoder = self._item_encoders[i]
            if encoder:
                decoded.append(encoder.load(value[i]))
            else:
                decoded.append(value[i])
        return tuple(decoded)

    cpdef inline dump(self, value: typing.Any):
        cdef FieldEncoder encoder
        cdef int i
        encoded = []
        if len(value) != self._item_encoders_count:
            raise ValidationError("Invalid number of items for tuple")
        for i in range(0, self._item_encoders_count):
            encoder = self._item_encoders[i]
            if encoder:
                encoded.append(encoder.dump(value[i]))
            else:
                encoded.append(value[i])
        return encoded

    def json_schema(self) -> JsonDict:
        return None


@cython.final
cdef class IterableFieldEncoder(FieldEncoder):
    cdef FieldEncoder _item_encoder
    cdef object _iterable_type

    def __cinit__(self, item_encoder, sequence_type):
        self._item_encoder = item_encoder
        origin = typing_inspect.get_origin(sequence_type)
        self._iterable_type = _ITERABLE_TYPES_MAPPING.get(origin, origin)

    cpdef inline load(self, value: typing.Any):
        if self._item_encoder:
            value = [
                self._item_encoder.load(v) if v is not None
                else None
                for v in value
            ]
        return self._iterable_type(value)

    cpdef inline dump(self, value: typing.Any):
        if self._item_encoder:
            return [
                self._item_encoder.dump(v) if v is not None
                else None
                for v in value
            ]
        return list(value)

    def json_schema(self) -> JsonDict:
        return None


@cython.final
cdef class DictFieldEncoder(FieldEncoder):
    cdef FieldEncoder _key_encoder
    cdef FieldEncoder _value_encoder

    def __cinit__(self, key_encoder, value_encoder):
        self._key_encoder = key_encoder
        self._value_encoder = value_encoder

    cpdef inline load(self, value: JsonEncodable):
        if self._key_encoder and self._value_encoder:
            return {
                self._key_encoder.load(k): self._value_encoder.load(v)
                for k, v in value.items()
            }
        elif self._key_encoder and not self._value_encoder:
            return {
                self._key_encoder.load(k): v
                for k, v in value.items()
            }
        elif not self._key_encoder and self._value_encoder:
            return {
                k: self._value_encoder.load(v)
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
                k: self._value_encoder.dump(v)
                for k, v in value.items()
            }
        else:
            return value

    def json_schema(self) -> JsonDict:
        return None


@cython.final
cdef class DateTimeFieldEncoder(FieldEncoder):
    """Encodes datetimes to RFC3339/ISO8601 format"""

    iso8601_pattern = (
        r"^[0-9]{4}-[0-9][0-9]-[0-9][0-9]T"  # YYYY-MM-DD
        r"[0-9][0-9]:[0-9][0-9]:[0-9][0-9](\.[0-9]+)"  # HH:mm:ss.ssss
        r"?(([+-][0-9][0-9]:[0-9][0-9])|Z)?$"  # timezone
    )

    cpdef inline dump(self, value):
        try:
            return value.isoformat()
        except AttributeError:
            raise ValidationError(f"{value} is not a datetime.datetime instance")

    cpdef inline load(self, value):
        try:
            return dateutil.parser.parse(value)
        except (ValueError, OverflowError):
            raise ValidationError(f"{value} is not a valid datetime")

    def json_schema(self) -> JsonDict:
        return {
            "type": "string",
            "format": "date-time",
            "pattern": self.iso8601_pattern
        }


@cython.final
cdef class UuidFieldEncoder(FieldEncoder):

    cpdef inline dump(self, value):
        return str(value)

    cpdef inline load(self, value):
        return uuid.UUID(value)

    def json_schema(self) -> JsonDict:
        return {"type": "string", "format": "uuid"}


@cython.final
cdef class UnionFieldEncoder(FieldEncoder):

    cdef tuple _type_encoders

    def __cinit__(
        self,
        type_encoders: typing.List[typing.Tuple[type, FieldEncoder]]
    ):
        self._type_encoders = tuple(type_encoders)

    cpdef inline dump(self, value):
        cdef list value_types = []
        for value_type, encoder in self._type_encoders:
            value_types.append(str(value_type))
            try:
                return encoder.dump(value) if encoder else value
            except Exception:
                pass
        union = ",".join(value_types)
        msg = f"{value} has a wrong type, expected any of [{union}]"
        raise ValidationError(msg)

    cpdef inline load(self, value):
        cdef list value_types = []
        for value_type, encoder in self._type_encoders:
            try:
                value_types.append(str(value_type))
                return encoder.load(value) if encoder else value
            except Exception:
                pass
        union = ",".join(value_types)
        msg = f"{value} has a wrong type, expected any of [{union}]"
        raise ValidationError(msg)

    def json_schema(self) -> JsonDict:
        return None
