# -*- coding: utf-8 -*-
import abc
import itertools
import copy
import dataclasses
import typing

import rapidjson  # type: ignore
from serpyco.schema import SchemaBuilder
from serpyco.exception import ValidationError
from serpyco.util import JsonDict, _get_values


class AbstractValidator(abc.ABC):
    """
    Abstract class for schema validators.
    Implementation shall raise serpyco.ValidationError().
    """

    def __init__(self, schema_builder: SchemaBuilder) -> None:
        self._schema = schema_builder.json_schema(many=False)
        self._many_schema = schema_builder.json_schema(many=True)
        self._field_validators = schema_builder.field_validators()

    def json_schema(self, many: bool = False) -> JsonDict:
        """
        Returns the schema that this validator uses to validate.
        """
        if many:
            return self._many_schema
        return self._schema

    @abc.abstractmethod
    def validate_json(self, json_string: str, many: bool = False) -> None:
        """
        Validates a JSON string against this object's schema.
        """
        pass

    @abc.abstractmethod
    def validate(
        self, data: typing.Union[JsonDict, typing.List[JsonDict]], many: bool = False
    ) -> None:
        """
        Validates the given data against this object's schema.
        """
        pass

    def validate_user(
        self, data: typing.Union[JsonDict, typing.List[JsonDict]], many: bool = False
    ) -> None:
        """
        Validates the given data with the user-defined validators.
        See :func:`serpyco.field()`.
        :param data: data to validate, either a dict or a list of dicts (with many=True)
        :param many: if true, data will be considered as a list
        """
        if many:
            datas = typing.cast(typing.List[JsonDict], data)
        else:
            datas = [typing.cast(JsonDict, data)]

        for d in datas:
            for path, validator in self._field_validators:
                try:
                    for value in _get_values(path.split("/")[1:], d):
                        validator(value)
                except KeyError:
                    # The value is not present, so do not validate
                    pass


@dataclasses.dataclass
class ValidationFailure:
    schema: JsonDict
    exception: rapidjson.ValidationError


@dataclasses.dataclass
class ValidatorSchema:
    schema: JsonDict
    validator: rapidjson.Validator


class RapidJsonValidator(AbstractValidator):
    """
    Schema validator using rapidjson.
    """

    def __init__(self, schema_builder: SchemaBuilder) -> None:
        super().__init__(schema_builder)
        self._validator = ValidatorSchema(
            schema=self._schema,
            validator=rapidjson.Validator(rapidjson.dumps(self._schema)),
        )
        self._many_validator = ValidatorSchema(
            schema=self._many_schema,
            validator=rapidjson.Validator(rapidjson.dumps(self._many_schema)),
        )

    def validate_json(self, json_string: str, many: bool = False) -> None:
        schema_copy: typing.Optional[JsonDict] = None
        validators: typing.List[ValidatorSchema]
        if many:
            validators = [self._many_validator]
        else:
            validators = [self._validator]
        validation_failures: typing.List[ValidationFailure] = []

        while validators:
            validator_schema = validators[0]
            validators = validators[1:]
            try:
                validator_schema.validator(json_string)
            except rapidjson.ValidationError as exc:

                failing_schema_part_name, failing_schema_path, failing_data_path = (
                    exc.args
                )

                if failing_schema_path == "#":
                    # the root schema fails, no need to go deeper
                    validation_failures.append(
                        ValidationFailure(validator_schema.schema, exc)
                    )
                    continue

                failing_schema_components = failing_schema_path.split("/")[1:]
                failing_schema_part = self._get_schema_part(
                    failing_schema_components,
                    failing_schema_part_name,
                    validator_schema.schema,
                )
                sub_schemas: typing.List[JsonDict]
                if failing_schema_part_name == "anyOf":
                    # re-validate against each sub schema
                    assert isinstance(failing_schema_part, list)
                    sub_schemas = failing_schema_part
                    # Do not consider Optional errors
                    if self._is_optional(sub_schemas):
                        sub_schemas.pop()
                else:
                    sub_schemas = [{}]
                    validation_failures.append(
                        ValidationFailure(validator_schema.schema, exc)
                    )

                for sub_schema in sub_schemas:
                    schema_copy = copy.deepcopy(validator_schema.schema)
                    if len(failing_schema_components) > 1:
                        failing_schema_parent = self._get_value(
                            failing_schema_components[:-1], schema_copy
                        )
                    else:
                        failing_schema_parent = schema_copy
                    failing_schema_parent[failing_schema_components[-1]] = sub_schema

                    validators.append(
                        ValidatorSchema(
                            validator=rapidjson.Validator(rapidjson.dumps(schema_copy)),
                            schema=schema_copy,
                        )
                    )

        if validation_failures:
            data = rapidjson.loads(json_string)
            self._raise_validation_error(
                data, validator_schema.schema.get("comment", "N/A"), validation_failures
            )

    def validate(
        self, data: typing.Union[JsonDict, typing.List[JsonDict]], many: bool = False
    ) -> None:
        self.validate_json(rapidjson.dumps(data), many=many)

    @staticmethod
    def _get_value(components: typing.List[str], d: JsonDict) -> JsonDict:
        for component in components:
            d = d[component]
        return d

    @staticmethod
    def _get_schema_part(
        components: typing.List[str], part_name: str, schema: JsonDict
    ) -> JsonDict:
        schema_value = next(_get_values(components, schema))
        return typing.cast(JsonDict, schema_value[part_name])

    @staticmethod
    def _raise_validation_error(
        data: typing.Union[JsonDict, typing.List[JsonDict]],
        class_name: str,
        validation_failures: typing.List[ValidationFailure],
    ) -> None:
        validation_failures = sorted(
            validation_failures, key=lambda f: tuple(reversed(f.exception.args))
        )
        messages: typing.List[str] = []
        failing_data_paths: typing.List[str] = []
        for args, failures in itertools.groupby(
            validation_failures, key=lambda f: tuple(reversed(f.exception.args))
        ):
            failing_data_path, failing_schema_path, failing_schema_part_name, = args

            if failing_schema_path == "#":
                failing_schema_parts = [next(failures).schema]
                failing_data = data
            else:
                failing_data = next(_get_values(failing_data_path.split("/")[1:], data))
                failing_schema_components = failing_schema_path.split("/")[1:]
                failing_schema_parts = [
                    RapidJsonValidator._get_schema_part(
                        failing_schema_components,
                        failing_schema_part_name,
                        failure.schema,
                    )
                    for failure in failures
                ]

            msg = RapidJsonValidator._get_error_message(
                failing_data, failing_schema_part_name, failing_schema_parts
            )

            if failing_data_path != "#":
                msg = f'value "{failing_data}" at path "{failing_data_path}" {msg}'
            failing_data_paths.append(failing_data_path)
            messages.append(msg)
        raise ValidationError(
            f'Validation failed for class "{class_name}":\n'
            + "\n".join(f"- {m}" for m in messages),
            dict(zip(failing_data_paths, messages)),
        )

    @staticmethod
    def _get_error_message(
        data: typing.Any, schema_part_name: str, schema_parts: typing.List[JsonDict]
    ) -> str:
        if "type" == schema_part_name:
            data_type = data.__class__.__name__
            msg = f'has type "{data_type}", expected '
            possible_types = []
            for schema_part in schema_parts:
                if "null" == schema_part:
                    possible_types.append('"NoneType"')
                else:
                    possible_types.append(f'"{schema_part}"')
            if len(possible_types) > 1:
                msg += " or ".join(possible_types)
            else:
                msg += possible_types[0]
        elif "pattern" == schema_part_name:
            msg = f'does not match pattern, expected "{schema_parts[0]}"'
        elif "format" == schema_part_name:
            msg = f'doesn\'t match defined format, expected "{schema_parts[0]}"'
        elif "maximum" == schema_part_name:
            msg = f"must be <= {schema_parts[0]}"
        elif "minimum" == schema_part_name:
            msg = f"must be >= {schema_parts[0]}"
        elif "maxLength" == schema_part_name:
            le = len(data)
            msg = f"must have its length <= {schema_parts[0]} but length is {le}"
        elif "minLength" == schema_part_name:
            le = len(data)
            msg = f"must have its length >= {schema_parts[0]} but length is {le}"
        elif "required" == schema_part_name:
            props = list(
                set(typing.cast(typing.List[str], schema_parts[0])) - set(data.keys())
            )
            props = [f'"{s}"' for s in sorted(props)]
            missing = ", ".join(props)
            if len(props) > 1:
                msg = f"must define properties {missing}"
            else:
                msg = f"must define property {missing}"
        elif "enum" == schema_part_name:
            msg = f"must have a value in {schema_parts[0]}"
        elif "additionalProperties" == schema_part_name:
            print(data)
            schema_properties = set(schema_parts[0].get("properties", {}).keys())
            data_properties = set(data.keys())
            props = list(data_properties - schema_properties)
            props = [f'"{s}"' for s in sorted(props)]
            additional = ", ".join(props)
            msg = f"properties {additional} cannot be defined"
        else:
            msg = f"unknown validation error"
        return msg

    @staticmethod
    def _is_optional(sub_schemas: typing.List[JsonDict]) -> bool:
        return 2 == len(sub_schemas) and ("null" == sub_schemas[1].get("type"))
