# -*- coding: utf-8 -*-
import abc
import copy
import re
import typing

import rapidjson  # type: ignore
from serpyco.exception import ValidationError
from serpyco.util import FieldValidator, JsonDict, _get_values


class AbstractValidator(abc.ABC):
    """
    Abstract class for schema validators.
    Implementation shall raise serpyco.ValidationError().
    """

    def __init__(
        self,
        schema: JsonDict,
        field_validators: typing.Optional[
            typing.List[typing.Tuple[str, FieldValidator]]
        ] = None,
    ) -> None:
        self._schema = schema
        self._field_validators = field_validators or []

    def json_schema(self) -> JsonDict:
        """
        Returns the schema that this validator uses to validate.
        """
        return self._schema

    @abc.abstractmethod
    def validate_json(self, json_string: str) -> None:
        """
        Validates a JSON string against this object's schema.
        """
        pass

    @abc.abstractmethod
    def validate(self, data: typing.Union[JsonDict, typing.List[JsonDict]]) -> None:
        """
        Validates the given data against this object's schema.
        """
        pass

    def validate_user(
        self, data: typing.Union[JsonDict, typing.List[JsonDict]], many: bool
    ) -> None:
        """
        Validates the given data with the user-defined validators.
        See :func:`serpyco.field()`.
        :param data: data to validate, either a dict or a list of dicts (with many=True)
        :param many: if true, data will be considered as a list
        """
        if not many:
            data = [typing.cast(JsonDict, data)]

        for d in data:
            for path, validator in self._field_validators:
                try:
                    for value in _get_values(path.split("/")[1:], d):
                        validator(value)
                except KeyError:
                    # The value is not present, so do not validate
                    pass


class RapidJsonValidator(AbstractValidator):
    """
    Schema validator using rapidjson.
    """

    def __init__(
        self,
        schema: JsonDict,
        field_validators: typing.Optional[
            typing.List[typing.Tuple[str, FieldValidator]]
        ] = None,
    ) -> None:
        super().__init__(schema, field_validators)
        self._validator = rapidjson.Validator(rapidjson.dumps(schema))

    def validate_json(self, json_string: str) -> None:
        validates = False
        validator = self._validator
        messages: typing.List[str] = []
        data_paths: typing.List[str] = []
        data: typing.Optional[JsonDict] = None
        schema_copy: typing.Optional[JsonDict] = None
        while not validates:
            try:
                validator(json_string)
                validates = True
            except rapidjson.ValidationError as exc:
                if data is None:
                    data = rapidjson.loads(json_string)
                if schema_copy is None:
                    schema_copy = copy.deepcopy(self._schema)

                messages.append(self._get_error_message(exc, data, schema_copy))
                data_paths.append(exc.args[1])

                schema_components = exc.args[1].split("/")[1:]
                schema_parent = schema_copy
                if not schema_components:
                    schema_copy = {}
                else:
                    while len(schema_components) > 1:
                        schema_parent = schema_parent[schema_components[0]]
                        schema_components = schema_components[1:]
                    schema_parent[schema_components[0]] = {}
                validator = rapidjson.Validator(rapidjson.dumps(schema_copy))

        if messages:
            raise ValidationError("\n".join(messages), dict(zip(data_paths, messages)))

    def validate(self, data: typing.Union[JsonDict, typing.List[JsonDict]]) -> None:
        self.validate_json(rapidjson.dumps(data))

    def _get_error_message(
        self, exc: rapidjson.ValidationError, data: JsonDict, schema: JsonDict
    ) -> str:
        schema_part_name, schema_path, data_path = exc.args
        d = list(_get_values(data_path.split("/")[1:], data))[0]

        schema_values = list(_get_values(schema_path.split("/")[1:], schema))
        schema_part = schema_values[0][schema_part_name]

        # transform the json path to something more python-like
        data_path = data_path.replace("#", "data")
        data_path = re.sub(r"/(\d+)", r"[\g<1>]", data_path)
        data_path = re.sub(r"/(\w+)", r'["\g<1>"]', data_path)

        if "type" == schema_part_name:
            data_type = d.__class__.__name__
            msg = f"has type {data_type}, expected {schema_part}"
        elif "pattern" == schema_part_name:
            msg = (
                f'string does not match pattern, got "{d}", '
                + f'expected "{schema_part}"'
            )
        elif "format" == schema_part_name:
            msg = (
                f'string doesn\'t match defined format, got "{d}", '
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
        elif "anyOf" == schema_part_name:
            messages: typing.List[str] = []
            for sub_schema in schema_part:
                # This was an union, let's validate with the sub-schemas to get a
                # precise error message
                val = rapidjson.Validator(rapidjson.dumps(sub_schema))
                try:
                    val(rapidjson.dumps(d))
                except rapidjson.ValidationError as e:
                    messages.append(
                        " - "
                        + self._get_error_message(e, d, sub_schema).split(":")[-1][1:-1]
                    )
            msg_string = "\n".join(messages)
            msg = f"does not validate for any Union parameters. Details:\n{msg_string}"
        else:
            msg = f"validation error {exc}"
        return f"{data_path}: {msg}."
