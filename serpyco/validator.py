# -*- coding: utf-8 -*-
import abc
import re
import typing

import rapidjson  # type: ignore
from serpyco.exception import ValidationError
from serpyco.util import _get_value


class AbstractValidator(abc.ABC):
    """
    Abstract class for schema validators.
    Implementation shall raise serpyco.ValidationError().
    """

    @abc.abstractmethod
    def json_schema(self) -> dict:
        """
        Returns the schema that this validator uses to validate.
        """
        pass

    @abc.abstractmethod
    def validate_json(self, json_string: str) -> None:
        """
        Validates a JSON string against this object's schema.
        """
        pass

    @abc.abstractmethod
    def validate(self, data: typing.Union[dict, list]) -> None:
        """
        Validates the given data against this object's schema.
        """
        pass


class RapidJsonValidator(AbstractValidator):
    """
    Schema validator using rapidjson.
    """

    def __init__(self, schema: dict) -> None:
        self._schema = schema
        self._validator = rapidjson.Validator(rapidjson.dumps(schema))

    def json_schema(self) -> dict:
        return self._schema

    def validate_json(self, json_string: str) -> None:
        try:
            self._validator(json_string)
        except rapidjson.ValidationError as exc:
            data = rapidjson.loads(json_string)
            msg = self._get_error_message(exc, data)
            raise ValidationError(msg, exc.args)

    def validate(self, data: typing.Union[dict, list]) -> None:
        self.validate_json(rapidjson.dumps(data))

    def _get_error_message(self, exc: rapidjson.ValidationError, data: dict) -> str:
        schema_part_name, schema_path, data_path = exc.args
        d = _get_value(data_path, data)
        schema_part = _get_value(schema_path, self._schema)[schema_part_name]

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
