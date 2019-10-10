# -*- coding: utf-8 -*-
import abc
import copy
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
            datas = [typing.cast(JsonDict, data)]
        else:
            datas = typing.cast(typing.List[JsonDict], data)

        for d in datas:
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
        messages: typing.List[str] = []
        failing_data_paths: typing.List[str] = []
        data: typing.Optional[JsonDict] = None
        schema_copy: typing.Optional[JsonDict] = None

        validates = False
        # start with the whole-schema
        validator = self._validator
        while not validates:
            try:
                validator(json_string)
                validates = True
            except rapidjson.ValidationError as exc:
                if data is None:
                    data = rapidjson.loads(json_string)
                if schema_copy is None:
                    schema_copy = copy.deepcopy(self._schema)

                failing_data, failing_data_path, message = self._get_error_message(
                    exc, data, schema_copy
                )
                messages.append(
                    f'value "{failing_data}" at path "{failing_data_path}" {message}'
                )
                failing_data_paths.append(failing_data_path)

                failing_schema_path = exc.args[1].split("/")[1:]

                if not failing_schema_path:
                    # The root schema fails, no need to go deeper
                    break
                failing_schema_parent = RapidJsonValidator._get_value(
                    failing_schema_path[:-1], schema_copy
                )
                failing_schema_parent[failing_schema_path[-1]] = {}
                validator = rapidjson.Validator(rapidjson.dumps(schema_copy))

        if messages:
            schema_comment = self._schema.get("comment", "N/A")
            raise ValidationError(
                f'Validation failed for class "{schema_comment}":\n'
                + "\n".join(f"- {m}" for m in messages),
                dict(zip(failing_data_paths, messages)),
            )

    def validate(self, data: typing.Union[JsonDict, typing.List[JsonDict]]) -> None:
        self.validate_json(rapidjson.dumps(data))

    @staticmethod
    def _get_value(path: typing.List[str], d: JsonDict) -> JsonDict:
        for component in path:
            d = d[component]
        return d

    def _get_error_message(
        self,
        exc: rapidjson.ValidationError,
        data: JsonDict,
        schema: JsonDict,
        indent: int = 2,
    ) -> typing.Tuple[JsonDict, str, str]:
        schema_part_name, schema_path, data_path = exc.args
        d = list(_get_values(data_path.split("/")[1:], data))[0]

        schema_values = list(_get_values(schema_path.split("/")[1:], schema))
        schema_part = schema_values[0][schema_part_name]

        if "type" == schema_part_name:
            if "null" == schema_part:
                msg = f"must be None"
            else:
                data_type = d.__class__.__name__
                msg = f'has type "{data_type}", expected "{schema_part}"'
        elif "pattern" == schema_part_name:
            msg = f'does not match pattern, expected "{schema_part}"'
        elif "format" == schema_part_name:
            msg = f'doesn\'t match defined format, expected "{schema_part}"'
        elif "maximum" == schema_part_name:
            msg = f"must be <= {schema_part}"
        elif "minimum" == schema_part_name:
            msg = f"must be >= {schema_part}"
        elif "maxLength" == schema_part_name:
            le = len(d)
            msg = f"must have its length <= {schema_part} but length is {le}"
        elif "minLength" == schema_part_name:
            le = len(d)
            msg = f"must have its length >= {schema_part} but length is {le}"
        elif "required" == schema_part_name:
            props = list(
                set(typing.cast(typing.List[str], schema_part)) - set(d.keys())
            )
            props = [f'"{s}"' for s in sorted(props)]
            missing = ", ".join(props)
            msg = f"properties {missing} must be defined"
        elif "enum" == schema_part_name:
            msg = f"must have a value in {schema_part}"
        elif "anyOf" == schema_part_name:
            messages: typing.List[str] = []
            for sub_schema in schema_part:
                # This was an union, let's validate with the sub-schemas to get a
                # precise error message
                try:
                    ref = sub_schema["$ref"].split("/")[1:]
                    sub_schema = next(_get_values(ref, schema))
                except KeyError:
                    pass
                val = rapidjson.Validator(rapidjson.dumps(sub_schema))
                try:
                    val(rapidjson.dumps(d))
                except rapidjson.ValidationError as e:
                    messages.append(
                        self._get_error_message(e, d, sub_schema, indent=indent + 2)[2]
                    )
            start_line = " " * indent + "- "
            msg_string = start_line + f"\n{start_line}".join(messages)
            msg = f"must match at least one of the following criteria:\n{msg_string}"
        elif "additionalProperties" == schema_part_name:
            schema_properties = set(schema.get("properties", {}).keys())
            data_properties = set(data.keys())
            props = list(data_properties - schema_properties)
            props = [f'"{s}"' for s in sorted(props)]
            additional = ", ".join(props)
            msg = f"properties {additional} cannot be defined"
        else:
            msg = f"validation error {exc}"
        return (d, data_path, msg)
