import typing

from serpyco.util import JsonDict


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
        Return the JSON schema of the handled value type.
        """
        raise NotImplementedError()
