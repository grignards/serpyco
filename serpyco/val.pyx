import cython
import re

cpdef Schema compile(dict schema):
    if "type" in schema:
        type_ = schema["type"]
        if "string"==type_:
            return StringSchema(schema)
        elif "object"==type_:
            return ObjectSchema(schema)
        elif "array"==type_:
            return ArraySchema(schema)

cdef class Schema:
    cdef void validate(self, object value, list errors):
        pass


@cython.final
cdef class StringSchema(Schema):
    cdef str format_
    cdef int minimum_length
    cdef int maximum_length
    cdef object pattern

    def __cinit__(self, dict schema):
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
        return


cdef class ObjectProperty(object):
    cdef str name
    cdef Schema schema

    def __cinit__(self, str name, Schema schema):
        self.name = name
        self.schema = schema


cdef class ArraySchema(Schema):
    cdef Schema item_schema
    cdef tuple item_schemas

    def __cinit__(self, dict schema):
        if "items" in schema:
            items = schema["items"]
            if isinstance(items, list):
                self.item_schemas = tuple(
                    compile(s)
                    for s in items
                )
                self.item_schema = None
            else:
                self.item_schema = compile(items)
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


cdef class ObjectSchema(Schema):
    cdef tuple properties
    cdef tuple additionalProperties
    cdef set required

    def __cinit__(self, dict schema):
        if "properties" in schema:
            self.properties = tuple(
                ObjectProperty(name, compile(value))
                for name, value in schema["properties"].items()
            )
        else:
            self.properties = ()
        if "additionalProperties" in schema:
            self.additionalProperties = tuple(
                ObjectProperty(name, compile(value))
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

cpdef validate(Schema schema, object value):
    cdef list errors = []
    schema.validate(value, errors)
    print(errors)