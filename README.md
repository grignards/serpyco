# Dataclasses Serializer


Fast serializer for Python 3.7 dataclasses. Python 3.6 is supported through the dataclasses backport.
Also provides data validation through JSON Schema generation and rapidjson validator.

JSON schema generation code have been taken from [dataclasses-jsonschema](https://github.com/s-knibbs/dataclasses-jsonschema).

Serialization is optimized using Cython (but I'm a beginner regarding this, so MR are welcomed).

## Examples

```python

    from dataclasses import dataclass

    from serpyco import Serializer


    @dataclass
    class Point(object):
        x: float
        y: float


    serializer = Serializer(Point)
```

### Generate the schema

```python

    >>> pprint(serializer.json_schema())
    {'$schema': 'http://json-schema.org/draft-04/schema#',
    'definitions': {},
    'description': 'Point(x:float, y:float)',
    'properties': {'x': {'format': 'float', 'type': 'number'},
                    'y': {'format': 'float', 'type': 'number'}},
    'required': ['x', 'y'],
    'type': 'object'}
```

### Deserialise data

```python

    >>> serializer.load({'x': 3.14, 'y': 1.5})
    Point(x=3.14, y=1.5)
    >>> serializer.load({'x': 3.14, 'y': 'wrong'})
    ValidationError('type', '#/properties/y', '#/y')
```

## TODO

* Improve optimization ?
* Support type Union using 'oneOf'
* Add the package to the benchmarked solutions of https://github.com/voidfiles/python-serialization-benchmark