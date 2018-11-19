# Serpyco changelog

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