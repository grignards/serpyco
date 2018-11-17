import copy
import dataclasses
import enum
import typing

from serpyco.encoder import FieldEncoder  # type: ignore
from serpyco.exception import SchemaError
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
class _SchemaBuilderField(object):
    field: dataclasses.Field
    hints: FieldHints


class SchemaBuilder(object):
    """
    Creates a JSON schema by inspecting a dataclass
    """

    _global_types: typing.Dict[type, FieldEncoder] = {}

    def __init__(
        self,
        dataclass: type,
        many: bool = False,
        only: typing.Optional[typing.List[str]] = None,
        exclude: typing.Optional[typing.List[str]] = None,
        type_encoders: typing.Dict[type, FieldEncoder] = {},
    ) -> None:
        """
        Creates a SchemaBuilder for the given dataclass.

        :param dataclass: dataclass to create a schema for.
        :param many: if True, the schema will validate against lists
        of dataclass.
        :param only: if given, only the fields in this list will be used
        :param type_encoders: dictionary of {type: FieldEncoder()}
            used to get json schema for given type and dump default values.
        """
        self._dataclass = dataclass
        self._many = many
        self._only = only or []
        self._exclude = exclude or []
        self._types = type_encoders
        self._fields: typing.List[_SchemaBuilderField] = []
        self._nested_builders: typing.Set[typing.Tuple[str, "SchemaBuilder"]] = set()
        self._schema: dict = {}
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
            self._fields.append(_SchemaBuilderField(f, hints))

    def __hash__(self) -> int:
        return hash(
            (self._dataclass, self._many, tuple(self._only), tuple(self._exclude))
        )

    def nested_builders(self) -> typing.List[typing.Tuple[str, "SchemaBuilder"]]:
        """
        Returns a the list of nested builders this builder has created.
        Values are (definition name, builder) tuples.
        """
        if not self._nested_builders:
            self._create_json_schema()
        return list(self._nested_builders)

    def json_schema(self) -> JsonDict:
        """
        Returns the json schema built from this SchemaBuilder's dataclass.
        """
        if not self._schema:
            self._schema = self._create_json_schema()
        return copy.deepcopy(self._schema)

    @classmethod
    def register_global_type(cls, type_: type, encoder: FieldEncoder) -> None:
        """
        Can be used to register a custom encoder for the given type.
        """
        cls._global_types[type_] = encoder

    @classmethod
    def unregister_global_type(cls, type_: type) -> None:
        """
        Removes a previously registered encoder for the given type.
        """
        del cls._global_types[type_]

    def _create_json_schema(
        self,
        embeddable: bool = False,
        parent_builders: typing.Optional[typing.List["SchemaBuilder"]] = None,
    ) -> dict:
        """Returns the JSON schema for the dataclass, along with the schema
        of any nested dataclasses within the "definitions" field.

        Enable the embeddable flag to generate the schema in a format
        for embedding into other schemas or documents supporting
        JSON schema such as Swagger specs,
        """
        parent_builders = parent_builders or []
        parent_builders.append(self)

        definitions: JsonDict = {}  # noqa: E704
        type_hints = typing.get_type_hints(self._dataclass)

        properties = {}
        required = []
        for vfield in self._fields:
            field_type = type_hints[vfield.field.name]
            field_schema, is_required = self._get_field_schema(
                field_type, parent_builders, vfield=vfield
            )

            f = getattr(vfield.field, "default_factory")
            default_value = dataclasses.MISSING
            if vfield.field.default != dataclasses.MISSING:
                default_value = vfield.field.default
            elif f != dataclasses.MISSING:
                default_value = f()

            if default_value != dataclasses.MISSING:
                if field_type in self._types:
                    default_value = self._types[field_type].dump(default_value)
                field_schema["default"] = default_value
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
                    for builder in parent_builders:
                        if hash(builder) == hash(
                            (
                                item_type,
                                False,
                                tuple(vfield.hints.only),
                                tuple(vfield.hints.exclude),
                            )
                        ):
                            break
                    else:
                        sub = SchemaBuilder(
                            item_type,
                            type_encoders=self._types,
                            only=vfield.hints.only,
                            exclude=vfield.hints.exclude,
                        )
                        self._nested_builders.add((definition_name, sub))
                        # Update our nested builders to get nested of nested builders
                        self._nested_builders |= sub._nested_builders

                        item_schema = sub._create_json_schema(
                            embeddable=True, parent_builders=parent_builders
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
        parent_builders: typing.List["SchemaBuilder"],
        vfield: _SchemaBuilderField,
    ) -> typing.Tuple[JsonDict, bool]:
        field_schema: JsonDict = {"type": "object"}
        required = True
        if field_type in self._types:
            field_schema = self._types[field_type].json_schema()
        elif field_type in self._global_types:
            field_schema = self._global_types[field_type].json_schema()
        elif dataclasses.is_dataclass(field_type):
            if field_type == parent_builders[0]._dataclass:
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
                            field_type.__args__[0], parent_builders, vfield
                        )[0],
                        {"type": "null"},
                    ]
                }
                required = False
            elif _is_union(field_type):
                schemas = [
                    self._get_field_schema(item_type, parent_builders, vfield)[0]
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
                        field_schema = self._types[member_types.pop()].json_schema()
                    elif member_type in self._global_types:
                        field_schema = self._global_types[
                            member_types.pop()
                        ].json_schema()
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
                        field_type.__args__[1], parent_builders, vfield
                    )[0]
                    field_schema["additionalProperties"] = add
            elif _is_generic(field_type, typing.Iterable):
                field_schema = {"type": "array"}
                if field_type.__args__[0] is not typing.Any:
                    items = self._get_field_schema(
                        field_type.__args__[0], parent_builders, vfield
                    )[0]
                    field_schema["items"] = items
            elif hasattr(field_type, "__supertype__"):  # NewType fields
                field_schema, _ = self._get_field_schema(
                    field_type.__supertype__, parent_builders, vfield
                )
            else:
                msg = f"Unable to create schema for '{field_type}'"
                raise SchemaError(msg)

        if vfield.hints.description is not None:
            field_schema["description"] = vfield.hints.description
        if vfield.hints.examples:
            field_schema["examples"] = vfield.hints.examples

        return field_schema, required

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
