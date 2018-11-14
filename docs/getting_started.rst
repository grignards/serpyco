==============
Getting started
===============

Serialize dataclasses instances
-------------------------------

The classic use for Serpyco is to dump your dataclass objects to builtin Python types. This is done by creating a *Serializer* for your dataclass type:

.. literalinclude:: examples/simple_dump.py
    :language: python
    
More complex dataclass can be serialized just as easily:

.. literalinclude:: examples/complex_dump.py
    :language: python

Loading data works the same:

.. code-block:: python

print(serializer.load({'color': 1, 'points': [{'x': 1, 'y': 2}, {'x': 2, 'y': 3}, {'x': 4, 'y': 5}]}))
Polygon(points=[Point(x=1, y=2), Point(x=2, y=3), Point(x=4, y=5)], color=<PolygonColor.RED: 1>, name=None)

Validate data
-------------

Serpyco can also validate your data when dumping/loading objects.  This is done by the `validate=True` parameter of `dump` and `load`:

.. code-block:: python

    serializer.load(
        {
            'color': 4,
            'points': [{'x': "wrong", 'y': 2}, {'x': 2, 'y': 3}, {'x': 4, 'y': 5}]
        }, validate=True)
    ValidationError: ('data["points"][0]["x"]: has type str, expected number.')


Customize data validation
-------------------------

Typing the fields of a dataclass is not always enough for precisely validating
input, that's why Serpyco offers additional field properties to enable
fine-tuning of the validation.

String fields
=============

.. literalinclude:: examples/string_field.py
    :language: python

* Number fields:

* Optional fields:

Recognized types
----------------

The following python types are recognized out-of-the-box by Serpyco:

- builtins: `str`, `float`, `int`, `bool`
- containers: `typing.List`, `typing.Set`, `typing.Tuple`
- unions: `typing.Optional`, `typing.Union`
- enumerates: `enum.Enum`
- dates: `datetime.datetime`
- misc: `uuid.UUID`

Advanced topics
---------------

Field serialization options
===========================

Options can be defined on fields that changes the behaviour of the serialization. This is done by defining the field as:

.. code-block:: python

    from serpyco import field
    @dataclass
    class Example(object):
        name: str = field(dict_key="custom")

See `field()` documentation for its parameters and effects.

Dump and load to/from JSON
==========================

The special methods `dump_json` and `load_json` are provided. They are equivalent as calling:

.. code-block:: python

    data = serializer.dump(obj)
    js = json.dumps(data)

    data = json.loads(data)
    obj = serializer.load(data)

But are faster, especially when using validation (internally, the validation is done using rapidjson and its JSON schema validator).

Custom field encoder
--------------------

You can register your own field encoders for any type:

Pre-processing and post-processing methods
==========================================

Decorators...

Serialize objects which are not dataclass instances
===================================================

Serpyco is made to serialize dataclass objects, but you can also use it to only defines "schemas" to dump your existing classes:

...
