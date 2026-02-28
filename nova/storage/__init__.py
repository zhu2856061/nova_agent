# -*- coding: utf-8 -*-
# @Time   : 2026/02/07 21:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

from nova import CONF

from .local_dict import InDictStore
from .local_file import LocalFileStore

LOCAL_FILE_STORE = None
LOCAL_DICT_STORE = None
if CONF:
    LOCAL_FILE_STORE = LocalFileStore(CONF.SYSTEM.store_dir)
    LOCAL_DICT_STORE = InDictStore()
