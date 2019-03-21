===============
Getting started
===============

Serialize dataclasses instances
-------------------------------

The classic use for Serpyco is to dump your dataclass objects to builtin Python types. This is done by creating a :class:`serpyco.Serializer` for your dataclass type:

.. literalinclude:: examples/simple_dump.py
    :language: python
    
More complex dataclass can be serialized just as easily:

.. literalinclude:: examples/complex_dump.py
    :language: python

Loading data works the same:

.. code-block:: python

    >>> serializer.load(
    >>>     {"color": 1, "points": [{"x": 1, "y": 2}, {"x": 2, "y": 3}, {"x": 4, "y": 5}]}
    >>> )
    Polygon(
        points=[Point(x=1, y=2), Point(x=2, y=3), Point(x=4, y=5)],
        color=<PolygonColor.RED:1>,
        name=None,
    )

Validate data
-------------

Serpyco can also validate your data when dumping/loading objects.
This is done by the `validate=True` parameter of
:func:`serpyco.Serializer.dump` and :func:`serpyco.Serializer.load`:

.. code-block:: python

    >>> serializer.load(
    >>> {
    >>>     'color': 4,
    >>>     'points': [
    >>>         {'x': "wrong", 'y': 2},
    >>>         {'x': 2, 'y': 3},
    >>>         {'x': 4, 'y': 5}
    >>>     ]
    >>> }, validate=True)
    ValidationError: ('data["points"][0]["x"]: has type str, expected number.')


Customize data validation
-------------------------

Typing the fields of a dataclass is not always enough for precisely validating
input, that's why Serpyco offers additional field properties to enable
fine-tuning of the validation.

String fields
=============

Tuning the validation of string fields is done using :func:`serpyco.string_field`:

.. code-block:: python

    from dataclasses import dataclass
    from serpyco import Serializer, string_field, ValidationError


    @dataclass
    class StringFields(object):
        simple: str
        name: str = string_field(pattern="^[A-Z]")


    serializer = Serializer(StringFields)

    >>> serializer.load({"name": "Foo", "simple": "whatever"}, validate=True)
    StringFields(simple='whatever', name='Foo')

    >>> serializer.load({"name": "foo", "simple": "foo"}, validate=True)
    ValidationError: ('data["name"]: string does not match pattern, got "foo",expected "^[A-Z]".')


Number fields
=============

For numbers (`int` and `float`), the tuning is done with :func:`serpyco.number_field`:

.. code-block:: python

    from dataclasses import dataclass
    from serpyco import Serializer, number_field, ValidationError


    @dataclass
    class NumberFields(object):
        simple: int
        range: float = number_field(minimum=0, maximum=10)


    serializer = Serializer(NumberFields)
    >>> serializer.load({"simple": 98, "range": 5}, validate=True)
    >>> NumberFields(simple=98, range=5)

    >>> serializer.load({"simple": 100, "range": 12}, validate=True)
    ValidationError: ('data["range"]: number must be <= 10, got 12.')

Optional fields
===============

A field can be specified as optional by typing it with `Optional`:

.. code-block:: python

    from dataclasses import dataclass
    from serpyco import Serializer


    @dataclass
    class OptionalField(object):
        name: str
        option: typing.Optional[int] = None

    serializer = Serializer(OptionalField)
    >>> serializer.load({"name": "foo"}, validate=True)
    OptionalField(name="foo", option=None)

Recognized types
----------------

The following python types are recognized out-of-the-box by Serpyco:

- builtins: `str`, `float`, `int`, `bool`
- containers: `typing.List`, `typing.Set`, `typing.Tuple`
- unions: `typing.Optional`, `typing.Union`
- generics: `typing.Generic`
- enumerates: `enum.Enum`
- dates: `datetime.datetime`
- misc: `uuid.UUID`

Advanced topics
---------------

Keep only some fields/exclude some fields from serialization
============================================================

The fields dumped/loaded by a serializer object can be tuned when creating it:

.. code-block:: python

    from dataclasses import dataclass
    from serpyco import field, Serializer

    @dataclasses.dataclass
    class Data(object):
        """Data test class"""

        foo: str
        bar: str

    >>> serializer = serpyco.Serializer(Data, only=["foo"])
    >>> serializer.dump(Data(foo="bar", bar="foo"))
    {"foo": "bar"}
    >>> serializer = serpyco.Serializer(Data, exclude=["foo"])
    >>> serializer.dump(Data(foo="bar", bar="foo"))
    {"bar": "foo"}


General field serialization options
===================================

Options can be defined on fields that changes the behaviour of the
serialization. This is done by using :func:`serpyco.field`:

.. code-block:: python

    from dataclasses import dataclass
    from serpyco import field, Serializer

    @dataclass
    class Example(object):
        name: str = field(dict_key="custom")

    serializer = Serializer(Example)
    >>> serializer.dump(Example(name="foo"))
    {"custom": "foo"}
    >>> serializer.load(Example({"custom": "foo"})
    Example(name="foo")

The :func:`serpyco.field` and specific versions for string/number/nested types
are compatible with :func:`dataclasses.field` signature.

Nested fields serialization options
===================================

Nested dataclasses serialization can be tuned to only keep
or exclude some fields by using :func:`serpyco.nested_field`:

.. code-block:: python

    from dataclasses import dataclass
    from serpyco import Serializer, nested_field

    @dataclass
    class Nested(object):
        """Nested test class"""

        foo: str
        bar: str

    @dataclass
    class Parent(object):
        """Parent test class"""

        first: Nested = serpyco.nested_field(only=["foo"])
        second: Nested = serpyco.nested_field(exclude=["foo"])

    serializer = Serializer(Parent)
    >>> serializer.dump(
    >>>    Parent(first=Nested(foo="foo", bar="bar"), second=Nested(foo="foo", bar="bar"))
    >>> )
    {"first": {"foo": "foo"}, "second": {"bar": "bar"}}

Dump and load to/from JSON
==========================

The special methods :func:`serpyco.Serializer.dump_json` and
:func:`serpyco.Serializer.load_json` are provided.
They are equivalent as calling:

.. code-block:: python

    data = serializer.dump(obj)
    js = json.dumps(data)

    data = json.loads(data)
    obj = serializer.load(data)

But are faster, especially when using validation.

Custom field encoder
====================

You can register your own field encoders for any type:

.. code-block:: python

    from dataclasses import dataclass
    import typing

    from serpyco import Serializer, FieldEncoder


    class Rational(object):
        def __init__(self, numerator: int, denominator: int):
            self.numerator = numerator
            self.denominator = denominator
        
        def __repr__(self) -> str:
            return f"Rational({self.numerator}/{self.denominator})"


    class RationalEncoder(FieldEncoder):
        def load(self, value: typing.Tuple[int, int]) -> Rational:
            return Rational(value[0], value[1])

        def dump(self, rational: Rational) -> typing.Tuple[int, int]:
            return (rational.numerator, rational.denominator)

        def json_schema(self) -> dict:
            # optional, but helpful to specify a custom validation
            # if you don't want any validation, return {} in your 
            # implementation.
            return {
                "type": "array",
                "maxItems": 2,
                "minItems": 2,
                "items": {"type": "integer"},
            }


    @dataclass
    class Custom(object):
        rational: Rational


    serializer = Serializer(Custom, type_encoders={Rational: RationalEncoder()})
    >>> serializer.dump(Custom(rational=Rational(1, 2)))
    {'rational': (1, 2)}

    >>> serializer.load({"rational": (1, 2)})
    Custom(rational=Rational(1/2))

    serializer.load({"rational": (1, 2.1)})
    ValidationError: ('data["rational"][1]: has type float, expected integer.')

Pre-processing and post-processing methods
==========================================

It is possible to specify additional processing to take place
before and after either loading or dumping:

.. code-block:: python

    from dataclasses import dataclass

    from serpyco import Serializer, post_dump


    @dataclass
    class Custom(object):
        firstname: str
        lastname: str

        @post_dump
        def make_name(data: dict) -> dict:
            first = data["firstname"]
            last = data["lastname"]
            return {"name": f"{first} {last}"}


    serializer = Serializer(Custom)
    >>> serializer.dump(Custom(firstname="foo", lastname="bar"))
    {'name': 'foo bar'}


Type casting when loading
=========================

In some cases it is useful to be able to accept field values that can be cast
to the field's type. This is possible by setting the `cast_on_load=True`
argument of the :func:`serpyco.field` function:

.. code-block:: python

    @dataclasses.dataclass
    class CastedOnLoad(object):
        value: int = serpyco.field(cast_on_load=True)

    serializer = serpyco.Serializer(CastedOnLoad)
    >>> serializer.load({"value": "42"})
    CastedOnLoad(value=42)

:class:`serpyco.ValidationError` will be raised if any exception is caught
during the cast of the value.


Serialize objects which are not dataclass instances
===================================================

Serpyco is primarly made to serialize dataclass objects, but you can also use it to dump/load your existing classes:

.. code-block:: python

    class Existing(object):
        def __init__(self, name: str, value: int) -> None:
            self.name = name
            self.value = value

        def __repr__(self) -> str:
            return f"Existing(name={self.name}, value={self.value})"


    @dataclasses.dataclass
    class Schema(object):
        name: str
        value: int

        @staticmethod
        @serpyco.post_load
        def create_existing(obj: "Schema") -> Existing:
            return Existing(obj.name, obj.value)


    serializer = serpyco.Serializer(Schema)
    
    >>> serializer.dump(Existing(name="hello", value=42))
    {'name': 'hello', 'value': 42}

    >>> serializer.load({"name": "hello", "value": 42})
    Existing(name=hello, value=42)


Serialize generic dataclasses
=============================

Dataclasses which are generic are supported, for example:

.. code-block:: python

    T = typing.TypeVar("T")
    class Gen(typing.Generic[T]):
        name: str
        value: T
    
    serializer = serpyco.Serializer(Gen[int])
    >>> serializer.dump(Gen(name="hello", value=42))
    {'name': 'hello', 'value': 42}

    serializer = serpyco.Serializer(Gen[str])
    >>> serializer.dump(Gen(name="hello", value="hello"))
    {'name': 'hello', 'value': "hello"}