import typing


class BaseSerpycoError(Exception):
    pass


class SchemaError(BaseSerpycoError):
    pass


class NoEncoderError(BaseSerpycoError):
    pass


class ValidationError(BaseSerpycoError):
    def __init__(self, msg: str, args: typing.Optional[typing.List[str]] = None):
        super().__init__(msg, args)


class NotDataClassError(BaseSerpycoError):
    pass
