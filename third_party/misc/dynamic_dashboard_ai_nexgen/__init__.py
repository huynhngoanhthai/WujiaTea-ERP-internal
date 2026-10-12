# Copyright (C) NexGen Solutions
from . import models
from . import controllers


def post_init_hook(env):
    from .hooks import post_init_hook as _hook
    _hook(env)
