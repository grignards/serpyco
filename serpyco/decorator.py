# -*- coding: utf-8 -*-
import enum
import typing

_serpyco_tags = "__serpyco_tags__"


class DecoratorType(str, enum.Enum):
    PRE_DUMP = "pre_dump"
    POST_DUMP = "post_dump"
    PRE_LOAD = "pre_load"
    POST_LOAD = "post_load"


ObjCallable = typing.Callable[[object], object]
DictCallable = typing.Callable[[dict], dict]


def pre_dump(method: ObjCallable) -> ObjCallable:
    """
    This decorator can be applied to a callable taking one object
    and should return an object of the dataclass it is declared in.
    The method will then be called with each object given to Serializer.dump
    or Serializer.dump_json before dumping them.
    :param: method method to call before dumping
    """
    setattr(method, _serpyco_tags, DecoratorType.PRE_DUMP)
    return method


def post_load(method: ObjCallable) -> ObjCallable:
    """
    This decorator can be applied to a callable taking one data class object
    and should return an object.
    The method will then be called with each object output by Serializer.load
    or Serializer.load_json before returning them.
    :param: method method to call after loading.
    """
    setattr(method, _serpyco_tags, DecoratorType.POST_LOAD)
    return method


def pre_load(method: DictCallable) -> DictCallable:
    """
    This decorator can be applied to a callable taking one dictionary
    and should return another dictionary.
    The method will then be called with each dictionary given to
    Serializer.load or Serializer.load before loading them in
    dataclass objects.
    :param: method method to call before loading
    """
    setattr(method, _serpyco_tags, DecoratorType.PRE_LOAD)
    return method


def post_dump(method: DictCallable) -> DictCallable:
    """
    This decorator can be applied to a callable taking one dictionary
    and should return another dictionary.
    The method will then be called with each dictionary output by
    Serializer.dump or Serializer.dump_json after dumping them.
    :param: method method to call after dumping
    """
    setattr(method, _serpyco_tags, DecoratorType.POST_DUMP)
    return method
