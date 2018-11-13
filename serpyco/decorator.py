# -*- coding: utf-8 -*-

import typing

_serpyco_tags = "__serpyco_tags__"

PRE_DUMP = "pre_dump"
POST_DUMP = "post_dump"
PRE_LOAD = "pre_load"
POST_LOAD = "post_load"


def pre_dump(method: typing.Callable):
    setattr(method, _serpyco_tags, PRE_DUMP)
    return method


def post_load(method: typing.Callable):
    setattr(method, _serpyco_tags, POST_LOAD)
    return method


def pre_load(method: typing.Callable):
    setattr(method, _serpyco_tags, POST_DUMP)
    return method


def post_dump(method: typing.Callable):
    setattr(method, _serpyco_tags, POST_DUMP)
    return method
