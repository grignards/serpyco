============================================
Serpyco: a serializer for python dataclasses
============================================

What is Serpyco ?
-----------------

Serpyco is a serialization library for `Python 3.6+ dataclasses <https://docs.python.org/3/library/dataclasses.html>`_ that works just by defining your dataclasses:

.. code-block:: python

    import dataclasses
    import typing

    import serpyco

    @dataclasses.dataclass
    class Example(object):
        name: str
        num: int
        tags: typing.List[str]


    serializer = serpyco.Serializer(Example)

    result = serializer.dump(Example(name="foo", num=2, tags=["hello", "world"]))
    print(result)

    {'name': 'foo', 'num': 2, 'tags': ['hello', 'world']}

Serpyco works by analysing the dataclass fields and can recognize many types : `List`, `Set`, `Tuple`, `Optional`, `Union`... You can also embed other dataclasses in a definition.

The main use-case for Serpyco is to serialize objects for an API, but it can be helpful whenever you need to transform objects to/from builtin Python types.


Features
--------

- Serialization and unserialization of dataclasses
- Validation of input/output data
- Very fast
- Extensible through custom encoders

Installing
----------

Serpyco is best installed via pip:

.. code-block:: shell

    pip install serpyco

It has only 3 (4 with python 3.6 dataclasses backport) dependencies:

- rapid-json: used for data validation and fast JSON dump/load
- python-dateutil: used for serializing datetime objects
- typing_inspect: used to inspect types as needed to create serializers

Documentation
-------------

- `Documentation <https://sgrignard.gitlab.io/serpyco/docs>`_
- `API Reference <https://sgrignard.gitlab.io/serpyco/docs/api.html>`_

Contributing
------------

Serpyco is written using `Python <https://www.python.org>`_ and `Cython <https://www.cython.org>`_ for parts needing speed.

- `Issue tracker <https://gitlab.com/sgrignard/serpyco/issues>`_
- `Source code <https://gitlab.com/sgrignard/serpyco>`_
