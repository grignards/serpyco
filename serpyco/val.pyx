import cython
import re
import sys

from serpyco.exception import ValidationError

@cython.final
cdef class Validator(object):
    cdef object _schema
    cdef dict _sub_validators

    def __init__(self, dict schema, dict sub_validators):
        cdef Validator sub
        self._sub_validators = sub_validators
        if "definitions" in schema:
            for name, def_schema in schema["definitions"].items():
                self._sub_validators[name] = Validator(def_schema, self._sub_validators)
        if "type" in schema:
            type_ = schema["type"]
            if "string"==type_:
                self._schema = StringSchema(self, schema)
            elif "integer"==type_:
                self._schema = IntegerSchema(self, schema)
            elif "number"==type_:
                self._schema = NumberSchema(self, schema)
            elif "boolean"==type_:
                self._schema = BooleanSchema(self, schema)
            elif "null"==type_:
                self._schema = NullSchema(self, schema)
            elif "object"==type_:
                self._schema = ObjectSchema(self, schema)
            elif "array"==type_:
                self._schema = ArraySchema(self, schema)
        if "$ref" in schema:
            name = schema["$ref"].split("/")[-1]
            sub = self._sub_validators[name]
            self._schema = sub._schema
        if "anyOf" in schema:
            self._schema = AnyOfSchema(self, schema)
        if not self._schema:
            raise ValueError(schema)


    cpdef int validate(self, object value) except -1:
        cdef list errors = []
        cdef Schema schema = self._schema
        schema.validate(value, errors)
        if errors:
            raise ValidationError(errors)
        #print(errors)

cdef class Schema:
    cdef Validator _validator

    def __init__(self, Validator validator):
        self._validator = validator

    cdef void validate(self, object value, list errors):
        pass

@cython.final
cdef class AnyOfSchema(Schema):
    cdef tuple _sub_validators

    def __init__(self, Validator validator, dict schema):
        super().__init__(validator)
        self._sub_validators = tuple(
            Validator(sub, validator._sub_validators)
            for sub in schema["anyOf"]
        )

    cdef void validate(self, object value, list errors):
        cdef Validator validator
        cdef list sub_errors = []
        cdef list temp_errors = []
        for validator in self._sub_validators:
            temp_errors.clear()
            validator._schema.validate(value, temp_errors)
            if not sub_errors:
                return
            sub_errors.extend(temp_errors)
        errors.extend(sub_errors)


@cython.final
cdef class NullSchema(Schema):
    cdef object _none_type

    def __init__(self, Validator validator, dict schema):
        super().__init__(validator)
        self._none_type = type(None)
    
    cdef void validate(self, object value, list errors):
        if not isinstance(value, self._none_type):
            errors.append("type")        


@cython.final
cdef class BooleanSchema(Schema):
    def __init__(self, Validator validator, dict schema):
        super().__init__(validator)
    
    cdef void validate(self, object value, list errors):
        if not isinstance(value, bool):
            errors.append("type")


@cython.final
cdef class StringSchema(Schema):
    cdef str format_
    cdef int minimum_length
    cdef int maximum_length
    cdef object pattern

    def __init__(self, Validator validator, dict schema):
        super().__init__(validator)
        self.format_= schema.get("format", None)
        self.minimum_length = int(schema.get("minimumLength", -1))
        self.maximum_length = int(schema.get("maximumLength", -1))
        if "pattern" in schema:
            self.pattern = re.compile(schema["pattern"])
        else:
            self.pattern = None

    cdef void validate(self, object value, list errors):
        if not isinstance(value, str):
            errors.append("type")
            return

        l = len(value)
        if (
            (self.minimum_length>0 and l<self.minimum_length) 
            or (self.maximum_length>0 and l>self.maximum_length)
        ):
            errors.append("length")
        if self.pattern is not None and not self.pattern.match(value):
            errors.append("pattern")


@cython.final
cdef class IntegerSchema(Schema):
    cdef long minimum
    cdef long maximum
    cdef long exclusive_minimum
    cdef long exclusive_maximum
    cdef long multiple_of

    def __init__(self, Validator validator, dict schema):
        super().__init__(validator)
        self.minimum = int(schema.get("minimum", -sys.maxsize))
        self.maximum = int(schema.get("maximum", sys.maxsize))
        self.exclusive_minimum = int(schema.get("exclusiveMinimum", -sys.maxsize))
        self.exclusive_maximum = int(schema.get("exclusiveMaximum", sys.maxsize))
        self.multiple_of = int(schema.get("multipleOf", 1))

    cdef void validate(self, object value, list errors):
        if not isinstance(value, int):
            errors.append("type")
            return

        cdef int ivalue = value
        if ivalue<self.minimum:
            errors.append("minimum")
        if ivalue>self.maximum:
            errors.append("minimum")
        if ivalue<=self.exclusive_minimum:
            errors.append("exclusiveMinimum")
        if ivalue>=self.exclusive_maximum:
            errors.append("exclusiveMaximum")
        if ivalue%self.multiple_of:
            errors.append("multipleOf")


@cython.final
cdef class NumberSchema(Schema):
    cdef float minimum
    cdef float maximum
    cdef float exclusive_minimum
    cdef float exclusive_maximum
    cdef bint has_multiple_of
    cdef float multiple_of

    def __init__(self, Validator validator, dict schema):
        super().__init__(validator)
        self.minimum = float(schema.get("minimum", -sys.maxsize))
        self.maximum = float(schema.get("maximum", sys.maxsize))
        self.exclusive_minimum = float(schema.get("exclusiveMinimum", -sys.float_info.max))
        self.exclusive_maximum = float(schema.get("exclusiveMaximum", sys.float_info.max))
        try:
            self.multiple_of = float(schema["multipleOf"])
            self.has_multiple_of = True
        except KeyError:
            self.multiple_of = 0.0
            self.has_multiple_of = False

    cdef void validate(self, object value, list errors):
        if not isinstance(value, float):
            errors.append("type")
            return

        cdef float fvalue = value
        if fvalue<self.minimum:
            errors.append("minimum")
        if fvalue>self.maximum:
            errors.append("minimum")
        if fvalue<=self.exclusive_minimum:
            errors.append("exclusiveMinimum")
        if fvalue>=self.exclusive_maximum:
            errors.append("exclusiveMaximum")
        if self.has_multiple_of and fvalue%self.multiple_of:
            errors.append("multipleOf")


cdef class ObjectProperty(object):
    cdef str name
    cdef Schema schema

    def __init__(self, str name, Schema schema):
        self.name = name
        self.schema = schema


@cython.final
cdef class ArraySchema(Schema):
    cdef Schema item_schema
    cdef tuple item_schemas

    def __init__(self, Validator validator, dict schema):
        super().__init__(validator)
        if "items" in schema:
            items = schema["items"]
            if isinstance(items, list):
                self.item_schemas = tuple(
                    Validator(s, self._validator._sub_validators)._schema
                    for s in items
                )
                self.item_schema = None
            else:
                val = Validator(items, self._validator._sub_validators)
                self.item_schema = val._schema
                self.item_schemas = ()

    cdef void validate(self, object value, list errors):
        if not isinstance(value, list):
            errors.append("type")
            return
        
        cdef list lvalue = value
        if self.item_schema:
            for v in lvalue:
                self.item_schema.validate(v, errors)
        else:
            l = min(len(lvalue), len(self.item_schemas))
            get_schema = self.item_schemas.__getitem__
            for index in range(0, l):
                self.item_schema[index].validate(lvalue[index], errors)


@cython.final
cdef class ObjectSchema(Schema):
    cdef tuple properties
    cdef tuple additionalProperties
    cdef set required

    def __init__(self, Validator validator, dict schema):
        super().__init__(validator)
        if "properties" in schema:
            self.properties = tuple(
                ObjectProperty(name, Validator(value, self._validator._sub_validators)._schema)
                for name, value in schema["properties"].items()
            )
        else:
            self.properties = ()
        if "additionalProperties" in schema:
            self.additionalProperties = tuple(
                ObjectProperty(name, Validator(value, self._validator._sub_validators)._schema)
                for name, value in schema["additionalProperties"].items()
            )
        else:
            self.additionalProperties = ()
        self.required = set(schema.get("required", []))

    cdef void validate(self, object value, list errors):
        if not isinstance(value, dict):
            errors.append("type")
            return

        cdef dict d = value
        get_data = d.get
        if not self.required.issubset(set(d.keys())):
            errors.append("required")

        cdef ObjectProperty prop
        for prop in self.properties:
            v = get_data(prop.name, None)
            # TODO: None can be in the dict...
            if v is not None:
                prop.schema.validate(v, errors)


class Error(Exception):
    pass
