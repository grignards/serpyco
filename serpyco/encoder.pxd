import typing

cdef class FieldEncoder(object):
    cpdef dump(self, value)
    cpdef load(self, value)
