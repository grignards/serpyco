import enum
import re
import typing

import dataclasses
import rapidjson
from serpyco.exception import JsonSchemaError, ValidationError
from serpyco.field import FieldHints, _metadata_name
from serpyco.util import (JSON_ENCODABLE_TYPES, JsonDict, _is_generic,
                          _is_optional, _is_union, _issubclass_safe)


class Validator(object):
    """
    Validates a dict/json string against a dataclass definition.
    """

    _global_types: JsonDict = {}

    def __init__(
        self,
        dataclass: type,
        many: bool = False,
        type_schemas: typing.Dict[type, dict] = {},
        only: typing.Optional[typing.List[str]] = None,
    ) -> None:
        """
        Creates a Validator for the given dataclass.

        :param dataclass: dataclass to validate.
        :param many: if True, the validator will validate against lists
        of dataclass.
        :param type_schemas: setup custom schemas for given types
        :param only: if given, only the fields in this list will be used
        """
        self._dataclass = dataclass
        self._many = many
        self._validator: typing.Optional[rapidjson.Validator] = None
        self._types = type_schemas
        self._fields: typing.List[typing.Tuple[str, FieldHints]] = []
        for f in dataclasses.fields(dataclass):
            hints = f.metadata.get(_metadata_name, FieldHints(dict_key=f.name))
            if hints.ignore or (only and f.name not in only):
                continue
            if hints.dict_key is None:
                hints.dict_key = f.name
            self._fields.append((f.name, hints))

    def validate(self, data: typing.Union[dict, list]) -> None:
        """
        Validates the given data against the schema generated from this
        validator's dataclass.
        """
        self.validate_json(rapidjson.dumps(data))

    def validate_json(self, json_string: str) -> None:
        """
        Validates a JSON string against the schema of this validator's
        dataclass.
        """
        if not self._validator:
            js = rapidjson.dumps(self.json_schema())
            self._validator = rapidjson.Validator(js)
        try:
            self._validator(json_string)
        except rapidjson.ValidationError as exc:
            data = rapidjson.loads(json_string)
            msg = self._get_error_message(exc, data)
            raise ValidationError(msg, exc.args)

    def json_schema(self) -> JsonDict:
        """
        Returns the json schema built from this validator's dataclass.
        """
        return self._create_json_schema()

    @classmethod
    def register_global_type(cls, type_: type, schema: JsonDict) -> None:
        """
        Can be used to register a custom JSON schema for the given type.
        """
        cls._global_types[type_] = schema

    @classmethod
    def unregister_global_type(cls, type_: type) -> None:
        """
        Removes a previously registered schema for the given type.
        """
        del cls._global_types[type_]

    def _create_json_schema(
        self, embeddable=False, parent_validators: typing.List["Validator"] = None
    ) -> dict:
        """Returns the JSON schema for the dataclass, along with the schema
        of any nested dataclasses within the "definitions" field.

        Enable the embeddable flag to generate the schema in a format
        for embedding into other schemas or documents supporting
        JSON schema such as Swagger specs,
        """
        parent_validators = parent_validators or []
        parent_validators.append(self)

        definitions: JsonDict = {}  # noqa: E704
        type_hints = typing.get_type_hints(self._dataclass)

        properties = {}
        required = []
        for field_name, hints in self._fields:
            field_type = type_hints[field_name]
            properties[hints.dict_key], is_required = self._get_field_schema(
                field_type, parent_validators, hints=hints
            )

            # Update definitions to objects
            item_types = [field_type]
            if _is_optional(field_type):
                item_types = [field_type.__args__[0]]
            elif _is_union(field_type):
                item_types = field_type.__args__
            elif _is_generic(field_type, typing.Mapping):
                item_types = [field_type.__args__[1]]
            elif _is_generic(field_type, typing.Iterable):
                item_types = [field_type.__args__[0]]

            for item_type in item_types:
                # Prevent recursion from forward refs &
                # circular type dependencies
                if (
                    dataclasses.is_dataclass(item_type)
                    and item_type.__name__ not in definitions
                ):
                    for validator in parent_validators:
                        if validator._dataclass == item_type:
                            break
                    else:
                        sub = Validator(item_type, type_schemas=self._types)
                        item_schema = sub._create_json_schema(
                            embeddable=True, parent_validators=parent_validators
                        )
                        definitions[item_type.__name__] = None
                        definitions.update(item_schema)
            if is_required:
                required.append(hints.dict_key)
        schema = {"type": "object", "properties": properties}
        if required:
            schema["required"] = required
        if self._dataclass.__doc__:
            schema["description"] = self._dataclass.__doc__.strip()

        if embeddable:
            schema = {**definitions, self._dataclass.__name__: schema}
        elif not self._many:
            schema = {
                **schema,
                **{
                    "definitions": definitions,
                    "$schema": "http://json-schema.org/draft-04/schema#",
                },
            }
        else:
            schema = {
                "definitions": definitions,
                "$schema": "http://json-schema.org/draft-04/schema#",
                "type": "array",
                "items": schema,
            }

        return schema

    def _get_field_schema(
        self,
        field_type: typing.Any,
        parent_validators: typing.List["Validator"],
        hints: typing.Optional[FieldHints] = None,
    ) -> typing.Tuple[JsonDict, bool]:
        field_schema: JsonDict = {"type": "object"}
        required = True
        field_type_name = self._get_field_type_name(field_type)
        if field_type in self._types:
            field_schema = self._types[field_type]
        elif field_type in self._global_types:
            field_schema = self._global_types[field_type]
        elif dataclasses.is_dataclass(field_type):
            if field_type == parent_validators[0]._dataclass:
                ref = "#"
            else:
                ref = "#/definitions/{}".format(field_type_name)
            field_schema = {"$ref": ref}
        else:
            if _is_optional(field_type):
                field_schema = {
                    "anyOf": [
                        self._get_field_schema(
                            field_type.__args__[0], parent_validators, hints
                        )[0],
                        {"type": "null"},
                    ]
                }
                required = False
            elif _is_union(field_type):
                schemas = [
                    self._get_field_schema(item_type, parent_validators, hints)[0]
                    for item_type in field_type.__args__
                ]
                field_schema["oneOf"] = schemas
                del field_schema["type"]
            elif _issubclass_safe(field_type, enum.Enum):
                member_types = set()
                values = []
                for member in field_type:
                    member_types.add(type(member.value))
                    values.append(member.value)
                if len(member_types) == 1:
                    member_type = member_types.pop()
                    if member_type in JSON_ENCODABLE_TYPES:
                        field_schema.update(JSON_ENCODABLE_TYPES[member_type])
                    elif member_type in self._types:
                        field_schema = self._types[member_types.pop()]
                    elif member_type in self._global_types:
                        field_schema = self._global_types[member_types.pop()]
                field_schema["enum"] = values
                if field_type.__doc__:
                    field_schema["description"] = field_type.__doc__.strip()
            elif field_type in JSON_ENCODABLE_TYPES:
                field_schema = dict(JSON_ENCODABLE_TYPES[field_type])
                validation_hints = [
                    ("format_", "format"),
                    ("pattern", "pattern"),
                    ("max_length", "maxLength"),
                    ("min_length", "minLength"),
                    ("minimum", "minimum"),
                    ("maximum", "maximum"),
                ]
                if hints:
                    for hint_attr, schema_attr in validation_hints:
                        attr = getattr(hints, hint_attr)
                        if attr is not None:
                            field_schema[schema_attr] = attr

            elif _is_generic(field_type, typing.Mapping):
                field_schema = {"type": "object"}
                if field_type.__args__[1] is not typing.Any:
                    add = self._get_field_schema(
                        field_type.__args__[1], parent_validators, hints
                    )[0]
                    field_schema["additionalProperties"] = add
            elif _is_generic(field_type, typing.Iterable):
                field_schema = {"type": "array"}
                if field_type.__args__[0] is not typing.Any:
                    items = self._get_field_schema(
                        field_type.__args__[0], parent_validators, hints
                    )[0]
                    field_schema["items"] = items
            elif hasattr(field_type, "__supertype__"):  # NewType fields
                field_schema, _ = self._get_field_schema(
                    field_type.__supertype__, parent_validators, hints
                )
            else:
                msg = f"Unable to create schema for '{field_type}'"
                raise JsonSchemaError(msg)
        if hints.description is not None:
            field_schema["description"] = hints.description
        if hints.examples is not None:
            field_schema["examples"] = hints.examples

        return field_schema, required

    @staticmethod
    def _get_field_type_name(field_type: typing.Any) -> typing.Optional[str]:
        try:
            return field_type.__name__
        except AttributeError:
            try:
                return field_type._name
            except AttributeError:
                return None

    @staticmethod
    def _get_value(json_path: str, data):
        components = json_path.split("/")[1:]
        for component in components:
            if isinstance(data, typing.Mapping):
                data = data[component]
            elif isinstance(data, typing.Sequence):
                data = data[int(component)]
            else:
                raise ValueError("Got a data which is not a list or dict")
        return data

    def _get_error_message(self, exc: rapidjson.ValidationError, data: dict) -> str:
        schema = self._create_json_schema()
        schema_part_name, schema_path, data_path = exc.args
        d = self._get_value(data_path, data)
        schema_part = self._get_value(schema_path, schema)[schema_part_name]

        # transform the json path to something more python-like
        data_path = data_path.replace("#", "data")
        data_path = re.sub(r"/(\d+)", r"[\g<1>]", data_path)
        data_path = re.sub(r"/(\w+)", r'["\g<1>"]', data_path)

        if "type" == schema_part_name:
            data_type = d.__class__.__name__
            msg = f"has type {data_type}, expected {schema_part}"
        elif "pattern" == schema_part_name:
            msg = f'''string doesn\'t match pattern, got "{d}",'
                expected "{schema_part}"'''
        elif "format" == schema_part_name:
            msg = (
                f'string doesn\'t match defined format, got "{d}",'
                f' expected "{schema_part}"'
            )
        elif "maximum" == schema_part_name:
            msg = f"number must be <= {schema_part}, got {d}"
        elif "minimum" == schema_part_name:
            msg = f"number must be >= {schema_part}, got {d}"
        elif "maxLength" == schema_part_name:
            le = len(d)
            msg = (
                f'string length must be <= {schema_part}, got "{d}"'
                f" whose length is {le}"
            )
        elif "minLength" == schema_part_name:
            le = len(d)
            msg = (
                f'string length must be >= {schema_part}, got "{d}"'
                f" whose length is {le}"
            )
        elif "required" == schema_part_name:
            props = set(schema_part) - set(d.keys())
            props = map(lambda s: f'"{s}"', props)
            missing = ", ".join(props)
            msg = f"is missing required properties {missing}"
        elif "enum" == schema_part_name:
            msg = f'value must be one of {schema_part}, got "{d}"'
        else:
            msg = f"validation error {exc}"
        return f"{data_path}: {msg}."
