import copy
import dataclasses
import enum
import typing

import typing_inspect  # type: ignore

from serpyco.encoder import FieldEncoder  # type: ignore
from serpyco.exception import NotADataClassError, SchemaError
from serpyco.field import FieldHints, _metadata_name
from serpyco.util import (
    JSON_ENCODABLE_TYPES,
    FieldValidator,
    JsonDict,
    _DataClassParams,
    _get_qualified_type_name,
    _is_generic,
    _is_optional,
    _is_union,
    _issubclass_safe,
)

GetDefinitionCallable = typing.Callable[
    [type, typing.Iterable[type], typing.Iterable[str], typing.Iterable[str]], str
]


def default_get_definition_name(
    type_: type,
    arguments: typing.Iterable[type],
    only: typing.Iterable[str],
    exclude: typing.Iterable[str],
) -> str:
    """
    Ensures that a definition name is unique even for the same type
    with different arguments or only/exclude parameters
    """
    name = _get_qualified_type_name(type_)
    if arguments:
        name += "[" + ",".join([arg.__name__ for arg in arguments]) + "]"
    if only:
        name += "_only_" + "_".join(only)
    if exclude:
        name += "_exclude_" + "_".join(exclude)
    return name


@dataclasses.dataclass
class _SchemaBuilderField(object):
    field: dataclasses.Field  # type:ignore
    hints: FieldHints


class SchemaBuilder(object):
    """
    Creates a JSON schema by inspecting a dataclass
    """

    _global_types: typing.Dict[type, FieldEncoder] = {}

    def __init__(
        self,
        dataclass: type,
        only: typing.Optional[typing.List[str]] = None,
        exclude: typing.Optional[typing.List[str]] = None,
        type_encoders: typing.Optional[typing.Dict[type, FieldEncoder]] = None,
        get_definition_name: GetDefinitionCallable = default_get_definition_name,
        strict: bool = False,
    ) -> None:
        """
        Creates a SchemaBuilder for the given dataclass.

        :param dataclass: dataclass to create a schema for.
        :param many: if True, the schema will validate against lists
        of dataclass.
        :param only: if given, only the fields in this list will be used
        :param type_encoders: dictionary of {type: FieldEncoder()}
            used to get json schema for given type and dump default values.
        :param get_definition_name: a callable that will be used to get the
            schema definition name of a nested dataclass.
            It will be called with:
              - the type of the nested dataclass
              - the `only` list defined for the nested dataclass
              - the `exclude` list defined for the nested dataclass
            It must return a string.
        :param strict: if true, unknown properties of an object will make the
            validation fail
        """
        self._dataclass = _DataClassParams(dataclass)
        self._only = only or []
        self._exclude = exclude or []
        self._types = type_encoders or {}
        self._fields: typing.List[_SchemaBuilderField] = []
        self._nested_builders: typing.Set[typing.Tuple[str, "SchemaBuilder"]] = set()
        self._field_validators: typing.List[typing.Tuple[str, FieldValidator]] = []
        self._schema: JsonDict = {}
        self._many_schema: JsonDict = {}
        self._get_definition_name = get_definition_name
        self._strict = strict

        for f in dataclasses.fields(self._dataclass.type_):
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
            self._fields.append(_SchemaBuilderField(f, hints))

    def __hash__(self) -> int:
        return hash(
            (
                self._dataclass.type_,
                self._dataclass.arguments,
                tuple(self._only),
                tuple(self._exclude),
            )
        )

    def nested_builders(self) -> typing.List[typing.Tuple[str, "SchemaBuilder"]]:
        """
        Returns a the list of nested builders this builder has created.
        Values are (definition name, builder) tuples.
        """
        if not self._nested_builders:
            self._schema = self._create_json_schema()
        return list(self._nested_builders)

    def json_schema(self, many: bool = False) -> JsonDict:
        """
        Returns the json schema built from this SchemaBuilder's dataclass.
        """
        if many:
            if not self._schema:
                self._schema = self._create_json_schema(many=many)
            return copy.deepcopy(self._schema)
        else:
            if not self._many_schema:
                self._many_schema = self._create_json_schema(many=many)
            return copy.deepcopy(self._many_schema)

    def field_validators(self) -> typing.List[typing.Tuple[str, FieldValidator]]:
        return [(f"#/{name}", validator) for name, validator in self._field_validators]

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
        many: bool = False,
        embeddable: bool = False,
        parent_builders: typing.Optional[typing.List["SchemaBuilder"]] = None,
    ) -> JsonDict:
        """Returns the JSON schema for the dataclass, along with the schema
        of any nested dataclasses within the "definitions" field.

        Enable the embeddable flag to generate the schema in a format
        for embedding into other schemas or documents supporting
        JSON schema such as Swagger specs,
        """
        parent_builders = parent_builders or []
        parent_builders.append(self)
        no_field_validators = not self._field_validators

        definitions: JsonDict = {}  # noqa: E704

        type_hints = typing.get_type_hints(self._dataclass.type_)
        properties = {}
        required = []
        for vfield in self._fields:
            field_type = type_hints[vfield.field.name]
            field_type = self._dataclass.resolve_type(field_type)

            field_schema, is_required = self._get_field_schema(
                field_type, parent_builders, vfield=vfield
            )

            default_value = vfield.field.default
            # A field is not required if either a:
            # - default value
            # - default factory
            # is provided.
            is_required = (
                default_value is dataclasses.MISSING
                and vfield.field.default_factory is dataclasses.MISSING  # type: ignore
            )

            # If a default value is provided, put it in the schema.
            # useful for documentation generation for example
            if default_value != dataclasses.MISSING:
                if field_type in self._types and default_value is not None:
                    default_value = self._types[field_type].dump(default_value)
                field_schema["default"] = default_value

            properties[vfield.hints.dict_key] = field_schema

            is_iterable = _is_generic(field_type, typing.Iterable)

            # Update definitions to dataclasses
            for item_type in self._get_types(field_type):
                item_type = self._dataclass.resolve_type(item_type)
                try:
                    params = _DataClassParams(item_type)
                except NotADataClassError:
                    continue

                # Prevent recursion from forward refs &
                # circular type dependencies
                definition_name = self._get_definition_name(
                    params.type_,
                    params.arguments,
                    vfield.hints.only,
                    vfield.hints.exclude,
                )
                if definition_name not in definitions:
                    for builder in parent_builders:
                        if hash(builder) == hash(
                            (
                                params.type_,
                                params.arguments,
                                tuple(vfield.hints.only),
                                tuple(vfield.hints.exclude),
                            )
                        ):
                            break
                    else:
                        sub = SchemaBuilder(
                            item_type,
                            type_encoders=vfield.hints.type_encoders or self._types,
                            only=vfield.hints.only,
                            exclude=vfield.hints.exclude,
                            get_definition_name=self._get_definition_name,
                        )
                        self._nested_builders.add((definition_name, sub))
                        # Update our nested builders to get nested of nested builders
                        self._nested_builders |= sub._nested_builders

                        item_schema = sub._create_json_schema(
                            embeddable=True,
                            parent_builders=parent_builders,
                            many=is_iterable,
                        )

                        # Get the format validators defined in the sub-schema
                        if no_field_validators:
                            for sub_field_name, validator in sub._field_validators:
                                if is_iterable:
                                    path = vfield.field.name + "/*/" + sub_field_name
                                else:
                                    path = vfield.field.name + "/" + sub_field_name
                                self._field_validators.append((path, validator))

                        definitions[definition_name] = None
                        definitions.update(item_schema)
            if is_required:
                required.append(vfield.hints.dict_key)

            if vfield.hints.validator and no_field_validators:
                self._field_validators.append(
                    (vfield.field.name, vfield.hints.validator)
                )

        schema = {
            "type": "object",
            "properties": properties,
            "comment": _get_qualified_type_name(self._dataclass.type_),
            "additionalProperties": not self._strict,
            "required": required,
        }
        if self._dataclass.type_.__doc__:
            schema["description"] = self._dataclass.type_.__doc__.strip()

        if embeddable:
            schema = {
                **definitions,
                self._get_definition_name(
                    self._dataclass.type_,
                    self._dataclass.arguments,
                    self._only,
                    self._exclude,
                ): schema,
            }
        elif not many:
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
        field_type = self._dataclass.resolve_type(field_type)
        args = typing_inspect.get_args(field_type, evaluate=True)
        required = True
        try:
            schema = self._types[field_type].json_schema()
            if schema is not None:
                return schema, not _is_optional(field_type)
        except KeyError:
            pass

        field_schema: JsonDict = {}
        if field_type in self._global_types:
            field_schema = self._global_types[field_type].json_schema()
        elif typing.Any == field_type:
            field_schema = {}
        elif type(None) == field_type:
            field_schema = {"type": "null"}
        elif _is_union(field_type):
            schemas = [
                self._get_field_schema(item_type, parent_builders, vfield)[0]
                for item_type in args
            ]
            field_schema = {"anyOf": schemas}
            required = type(None) not in args
        elif _issubclass_safe(field_type, enum.Enum):
            member_types = set()
            values = []
            field_schema = {}
            for member in field_type:
                member_types.add(type(member.value))
                values.append(member.value)
            if len(member_types) == 1:
                member_type = member_types.pop()
                member_schema, _ = self._get_field_schema(
                    member_type, parent_builders, vfield
                )
                field_schema.update(member_schema)
            field_schema["enum"] = values
            if field_type.__doc__:
                field_schema["description"] = field_type.__doc__.strip()
        elif field_type in JSON_ENCODABLE_TYPES:
            field_schema = dict(JSON_ENCODABLE_TYPES[field_type])
            validation_hints = [
                ("pattern", "pattern"),
                ("max_length", "maxLength"),
                ("min_length", "minLength"),
                ("minimum", "minimum"),
                ("maximum", "maximum"),
                ("format_", "format"),
            ]
            for hint_attr, schema_attr in validation_hints:
                attr = getattr(vfield.hints, hint_attr)
                if attr is not None:
                    field_schema[schema_attr] = attr
        elif _is_generic(field_type, typing.Mapping):
            field_schema = {"type": "object"}
            add = self._get_field_schema(args[1], parent_builders, vfield)[0]
            field_schema["additionalProperties"] = add
        elif _is_generic(field_type, tuple) and (
            len(args) != 2 or args[len(args) - 1] is not ...
        ):
            arg_len = len(args)
            items = [
                self._get_field_schema(arg_type, parent_builders, vfield)[0]
                for arg_type in args
            ]
            field_schema = {
                "type": "array",
                "minItems": arg_len,
                "maxItems": arg_len,
                "items": items,
            }

        elif _is_generic(field_type, typing.Iterable):
            field_schema = {"type": "array"}
            field_schema["items"] = self._get_field_schema(
                args[0], parent_builders, vfield
            )[0]
        elif hasattr(field_type, "__supertype__"):  # NewType fields
            field_schema, _ = self._get_field_schema(
                field_type.__supertype__, parent_builders, vfield
            )
        else:
            try:
                params = _DataClassParams(field_type)
                if params == parent_builders[0]._dataclass:
                    ref = "#"
                else:
                    ref = "#/definitions/{}".format(
                        self._get_definition_name(
                            params.type_,
                            params.arguments,
                            vfield.hints.only,
                            vfield.hints.exclude,
                        )
                    )
                field_schema = {"$ref": ref}
            except NotADataClassError:
                msg = f"Unable to create schema for '{field_type}'"
                raise SchemaError(msg)

        if vfield.hints.description is not None:
            field_schema["description"] = vfield.hints.description
        if vfield.hints.examples:
            field_schema["examples"] = vfield.hints.examples
        if vfield.hints.allowed_values:
            values = [
                v.value if isinstance(v, enum.Enum) else v
                for v in vfield.hints.allowed_values
            ]
            try:
                values = list(set(field_schema["enum"]) & set(values))
            except KeyError:
                pass
            field_schema["enum"] = values

        return field_schema, required

    @classmethod
    def _get_types(cls, field_type: type) -> typing.Set[type]:
        """Return the 'root' types of the given type.
        This expands the arguments of the given type if it is:
          - a Union
          - a Mapping
          - an Iterable
        """
        types: typing.Set[type] = set()
        if (
            _is_union(field_type)
            or _is_generic(field_type, typing.Mapping)
            or _is_generic(field_type, typing.Iterable)
        ):
            for arg in typing_inspect.get_args(field_type, evaluate=True):
                types |= cls._get_types(arg)
        else:
            types.add(field_type)
        return types
