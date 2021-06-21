# Serpyco changelog

## v1.3.5

- feat: add support for non-annotated collections (`dict`/`list`/`set`) (#44)
- fix: properly support `typing.Union[None, Dataclass1, Dataclass2]` (#42)

## v1.3.4

- fix: get_dict_path() with dataclass dicts
- fix: optional dataclass list (#40)
- refactor: improve loading perf of dataclass iterables
- refactor: small speedup when a __post_init__() method exists
- chore: include mypy stub files to the package (courtesy of R. Pelloux-Prayer)


## v1.3.3

- fix: properly initialize `dict_key` in `SchemaBuilder`

## v1.3.2

- fix: do not create encoders for ignored fields

## v1.3.1

- fix: call `__post_init__` when loading if it is defined (#36)
- fix: use field hints to compute definition name when creating JSON schema (#37)

## v1.3.0

- fix: enum default value (#35)
- feat: mixin class providing dump()/load() on dataclasses

## v1.2.2

- fix: schema reference if parent used in a list and many=True is used to load/dump

## v1.2.1

- fix: recursive dataclass declaration

## v1.2.0

- fix: load with exclude/only/ignore fields
- refactor: get_definition_name now only takes 3 arguments

## v1.1.1

- fix: forgotten definitions with optional mapping/iterable

## v1.1.0

- feat: add `load_as_type` argument to `nested_field()`

## v1.0.1

- fix: bug in schema generation for list of sub-objects
- fix: error message for required properties
- fix: load of frozen dataclass objects

## v1.0.0

- refactor: improve loading speed by a factor of 3 (now only 1.5x slower than dump)
- refactor: improve error messages
- refactor: move `many` parameter to dump/load methods of Serializer
- feat: `load_as_type` parameter for Serializer for easier loading of non-dataclass objects

## v0.18.2

- fix: avoid calling a field encoder with a `None` value

## v0.18.1

- fix: dump sets as list since sets are not JSON serializable + didn't work with a set of hashable objects

## v0.18.0

- feat: strict mode for object validation
- refactor: better validation messages
- **refactor**: remove omit_none option of Serializer, `None` values are now always dumped
- feat: custom type encoders through nested_field()

## v0.17.4

- fix: ensure order of missing fields in error message
- fix: ensure definitions name are unique by using the module name of the dataclass as a prefix
- refactor: do not use `default_factory` to document the default value of a field. Reasoning: it can't be guaranteed that it always returns the same value.

## v0.17.3

- fix: avoid adding a timezone to naive datetime objects.
- feat: add pattern for validating datetime strings

## v0.17.2

- fix: validation error message with optional dataclass

## v0.17.1

- fix: validation error of empty dictionary properly raises a `ValidationError` exception

## v0.17

- refactor: ValidationError exception now includes a dictionary of path/message

## v0.16.13

- fix: error when using a user validation function in a nested object list.
- feat: all validation errors are now included in `ValidationError` exception.

## v0.16.12

- fix: remove dictionary used as default value for encoders
- feat: improve validation error message when using `Union`/`Optional`

## v0.16.11

- fix: `Optional` fields with a `validator` function

## v0.16.10

- refactor: use typing_inspect instead of self-made code (new dependency)
- fix: load of dict with field encoders is now working

## v0.16.9

- fix: cast_on_load now works with Optional[]

## v0.16.8

- feat: `allowed_values` list for fields
- fix: default value handling in schemas

## v0.16.7

- fix: default value with custom types led to wrong schema

## v0.16.6

- fix: avoid non-json serializable default values in JSON schema

## v0.16.5

- fix: support of optional unions

## v0.16.4

- fix: default value not written in schema

## v0.16.3

- fix: non json-serializable default value in schemas with several nested levels
- fix: optional fields with custom encoders were not considered as optional

## v0.16.2

- fix: `Union` loading with non-builtin types
- fix: reference in sub-schemas when many=True is enabled

## v0.16.1

- fix: None default in schema
- fix: fields with a default value are not required

## v0.16

- fix: encode default values in schema
- support Generic[T] in serialization

## v0.15.2

- fix: fields with `init=False`

## v0.15.1

- fix: custom definition name in JSON schema
- fix: `Tuple` is now handled properly
- fix: exceptions caught during cast_on_load are propagated to the calling code

## v0.15

- fields can now be cast to their declared type when loading (`serpyco.field`, `cast_on_load` argument)
- small improvement in dump/load speed

## v0.14

- all fields can now be additionally validated with a custom method (`serpyco.field`, `validator` argument)
- fix validation error message
- fix `get_object_path` and `get_dict_path` when used with `List` or `Dict` fields
- custom nested dataclass definition names when building a schema with `SchemaBuilder`

## v0.13

- string format can now be validated by providing a validation method

## v0.12

- split the schema building/validation code
- allow access to nested-schema builders

## v0.11

- Serializer can exclude fields (via `exclude` parameter)
- default values of field are written in the generated JSON schema
- get dict/object paths of fields
- `only` and `exclude` in nested fields (via `serpyco.nested_field` function)

## v0.10

- support field description and examples (via `serpyco.field` arguments)
- support pre/post load/dump method (via `post_load`, `post_dump`, `pre_load` and `pre_dump` decorators)

## v0.9

- fix `Optional` fields validation (`None` is a valid value)
- custom message for `enum` validation errors

## v0.8

- support `typing.Set[]` fields
- improve validation error messages
- support getter method for fields

## v0.7

- fix json schema caching in `Validator`
- fix `"type": "object"` added in custom schemas
- support per instance custom encoders and schemas
- support ignoring of fields (via `serpyco.field(ignore=True)`)
- support partial serialization (via `only` parameter)

## v0.6

- support additional validation constraints for strings and numbers (`string_field()` and `number_field()`)
- fix support for custom serialization dict keys

## v0.5

- support `typing.Tuple[]` fields
- simpler schemas for integers/numbers
- remove `"type": "object"` from `$ref` schemas

## v0.4

- support Python 3.7

## v0.3

- support `typing.Union[]` fields

## v0.2

- support cycles in fields definition
- split validation and serialization code in two classes: `Validation` and `Serializer`

## v0.1

Initial release
