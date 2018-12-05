# Serpyco changelog

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