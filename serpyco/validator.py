import enum
import re
import typing

import dataclasses
import rapidjson  # type: ignore
from serpyco.encoder import FieldEncoder  # type: ignore
from serpyco.exception import JsonSchemaError, ValidationError
from serpyco.field import FieldHints, _metadata_name
from serpyco.util import (
    JSON_ENCODABLE_TYPES,
    JsonDict,
    _is_generic,
    _is_optional,
    _is_union,
    _issubclass_safe,
)


@dataclasses.dataclass
class _ValidatorField(object):
    field: dataclasses.Field
    hints: FieldHints


class Validator(object):
    """
    Validates a dict/json string against a dataclass definition.
    """

    _global_types: typing.Dict[type, typing.Any] = {}

    def __init__(
        self,
        dataclass: type,
        many: bool = False,
        only: typing.Optional[typing.List[str]] = None,
        exclude: typing.Optional[typing.List[str]] = None,
        type_encoders: typing.Dict[type, FieldEncoder] = {},
    ) -> None:
        """
        Creates a Validator for the given dataclass.

        :param dataclass: dataclass to validate.
        :param many: if True, the validator will validate against lists
        of dataclass.
        :param only: if given, only the fields in this list will be used
        :param type_encoders: dictionary of {type: FieldEncoder()}
            used to get json schema for given type and dump default values.
        """
        self._dataclass = dataclass
        self._many = many
        self._validator: typing.Optional[rapidjson.Validator] = None
        self._only = only or []
        self._exclude = exclude or []
        self._types = type_encoders
        self._fields: typing.List[_ValidatorField] = []
        for f in dataclasses.fields(dataclass):
            if not f.metadata:
                hints = FieldHints(dict_key=f.name)
            else:
                hints = f.metadata.get(_metadata_name, FieldHints(dict_key=f.name))
            if (
                hints.ignore
                or (only and f.name not in only)
                or (exclude and f.name in exclude)
            ):
                continue
            if hints.dict_key is None:
                hints.dict_key = f.name
            self._fields.append(_ValidatorField(f, hints))

    def __hash__(self) -> int:
        return hash(
            (self._dataclass, self._many, tuple(self._only), tuple(self._exclude))
        )

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
        self,
        embeddable: bool = False,
        parent_validators: typing.Optional[typing.List["Validator"]] = None,
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
        for vfield in self._fields:
            field_type = type_hints[vfield.field.name]
            field_schema, is_required = self._get_field_schema(
                field_type, parent_validators, vfield=vfield
            )

            f = getattr(vfield.field, "default_factory")
            if vfield.field.default != dataclasses.MISSING:
                val = vfield.field.default
                if field_type in self._types:
                    val = self._types[field_type].dump(val)
                field_schema["default"] = val
            elif f != dataclasses.MISSING:
                val = f()
                if field_type in self._types:
                    val = self._types[field_type].dump(val)
                field_schema["default"] = val
            properties[vfield.hints.dict_key] = field_schema

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
                definition_name = self._get_definition_name(
                    item_type, vfield.hints.only, vfield.hints.exclude
                )
                if (
                    dataclasses.is_dataclass(item_type)
                    and definition_name not in definitions
                ):
                    for validator in parent_validators:
                        if hash(validator) == hash(
                            (
                                item_type,
                                False,
                                tuple(vfield.hints.only),
                                tuple(vfield.hints.exclude),
                            )
                        ):
                            break
                    else:
                        sub = Validator(
                            item_type,
                            type_encoders=self._types,
                            only=vfield.hints.only,
                            exclude=vfield.hints.exclude,
                        )
                        item_schema = sub._create_json_schema(
                            embeddable=True, parent_validators=parent_validators
                        )
                        definitions[definition_name] = None
                        definitions.update(item_schema)
            if is_required:
                required.append(vfield.hints.dict_key)
        schema = {"type": "object", "properties": properties}
        if required:
            schema["required"] = required
        if self._dataclass.__doc__:
            schema["description"] = self._dataclass.__doc__.strip()

        if embeddable:
            schema = {
                **definitions,
                self._get_definition_name(
                    self._dataclass, self._only, self._exclude
                ): schema,
            }
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
        vfield: _ValidatorField,
    ) -> typing.Tuple[JsonDict, bool]:
        field_schema: JsonDict = {"type": "object"}
        required = True
        if field_type in self._types:
            field_schema = self._types[field_type].json_schema()
        elif field_type in self._global_types:
            field_schema = self._global_types[field_type]
        elif dataclasses.is_dataclass(field_type):
            if field_type == parent_validators[0]._dataclass:
                ref = "#"
            else:
                ref = "#/definitions/{}".format(
                    self._get_definition_name(
                        field_type, vfield.hints.only, vfield.hints.exclude
                    )
                )
            field_schema = {"$ref": ref}
        else:
            if _is_optional(field_type):
                field_schema = {
                    "anyOf": [
                        self._get_field_schema(
                            field_type.__args__[0], parent_validators, vfield
                        )[0],
                        {"type": "null"},
                    ]
                }
                required = False
            elif _is_union(field_type):
                schemas = [
                    self._get_field_schema(item_type, parent_validators, vfield)[0]
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
                for hint_attr, schema_attr in validation_hints:
                    attr = getattr(vfield.hints, hint_attr)
                    if attr is not None:
                        field_schema[schema_attr] = attr
            elif _is_generic(field_type, typing.Mapping):
                field_schema = {"type": "object"}
                if field_type.__args__[1] is not typing.Any:
                    add = self._get_field_schema(
                        field_type.__args__[1], parent_validators, vfield
                    )[0]
                    field_schema["additionalProperties"] = add
            elif _is_generic(field_type, typing.Iterable):
                field_schema = {"type": "array"}
                if field_type.__args__[0] is not typing.Any:
                    items = self._get_field_schema(
                        field_type.__args__[0], parent_validators, vfield
                    )[0]
                    field_schema["items"] = items
            elif hasattr(field_type, "__supertype__"):  # NewType fields
                field_schema, _ = self._get_field_schema(
                    field_type.__supertype__, parent_validators, vfield
                )
            else:
                msg = f"Unable to create schema for '{field_type}'"
                raise JsonSchemaError(msg)

        if vfield.hints.description is not None:
            field_schema["description"] = vfield.hints.description
        if vfield.hints.examples:
            field_schema["examples"] = vfield.hints.examples

        return field_schema, required

    @staticmethod
    def _get_field_type_name(field_type: typing.Any) -> typing.Optional[str]:
        try:
            return str(field_type.__name__)
        except AttributeError:
            try:
                return str(field_type._name)
            except AttributeError:
                return None

    @staticmethod
    def _get_value(json_path: str, data: typing.Any) -> typing.Any:
        components = json_path.split("/")[1:]
        for component in components:
            if isinstance(data, typing.Mapping):
                data = data[component]
            elif isinstance(data, typing.Sequence):
                data = data[int(component)]
            else:
                raise ValueError("Got a data which is not a list or dict")
        return data

    @staticmethod
    def _get_definition_name(
        type_: type, only: typing.List[str], exclude: typing.List[str]
    ) -> str:
        """
        Ensures that a definition name is unique even for the same type
        with different only/exclude parameters
        """
        name = type_.__name__
        if only:
            name += "_only_" + "_".join(only)
        if exclude:
            name += "_exclude_" + "_".join(exclude)
        return name

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
            msg = (
                f'string does not match pattern, got "{d}",'
                + f'expected "{schema_part}"'
            )
        elif "format" == schema_part_name:
            msg = (
                f'string doesn\'t match defined format, got "{d}",'
                + f' expected "{schema_part}"'
            )
        elif "maximum" == schema_part_name:
            msg = f"number must be <= {schema_part}, got {d}"
        elif "minimum" == schema_part_name:
            msg = f"number must be >= {schema_part}, got {d}"
        elif "maxLength" == schema_part_name:
            le = len(d)
            msg = (
                f'string length must be <= {schema_part}, got "{d}"'
                + f" whose length is {le}"
            )
        elif "minLength" == schema_part_name:
            le = len(d)
            msg = (
                f'string length must be >= {schema_part}, got "{d}"'
                + f" whose length is {le}"
            )
        elif "required" == schema_part_name:
            props = list(
                set(typing.cast(typing.List[str], schema_part)) - set(d.keys())
            )
            props = list(map(lambda s: f'"{s}"', props))
            missing = ", ".join(props)
            msg = f"is missing required properties {missing}"
        elif "enum" == schema_part_name:
            msg = f'value must be one of {schema_part}, got "{d}"'
        else:
            msg = f"validation error {exc}"
        return f"{data_path}: {msg}."
