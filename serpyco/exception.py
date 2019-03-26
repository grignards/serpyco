import typing


class BaseSerpycoError(Exception):
    pass


class SchemaError(BaseSerpycoError):
    pass


class NoEncoderError(BaseSerpycoError):
    pass


class ValidationError(BaseSerpycoError):
    """Raised when an error is found during validation of data.

    :param msg: formatted exception message(s).
    :param errors: dictionary of error message(s) where the key
    is the JSON path to the invalid data.
    """

    def __init__(self, msg: str, errors: typing.Optional[typing.Dict[str, str]] = None):
        super().__init__(msg, errors or {"#": msg})


class NotADataClassError(BaseSerpycoError):
    pass
