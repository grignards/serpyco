# Serpyco changelog

## v0.6

- support additional validation constraints for strings and numbers (`string_field()` and `number_field()`)
- fix support for custom serialization dict keys

## v0.5

- support typing.Tuple[] fields
- simpler schemas for integers/numbers
- remove `"type": "object"` from `$ref` schemas

## v0.4

- support Python 3.7

## v0.3

- support typing.Union[] fields

## v0.2

- support cycles in fields definition
- split validation and serialzation code in two classes: Validation and Serializer

## v0.1

Initial release