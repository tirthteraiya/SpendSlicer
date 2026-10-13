"""Keep botocore's parsing rules while reading UTF-8 AWS files on Windows."""

from __future__ import annotations

import configparser
import locale
import os
import types

import botocore.configloader


class _ConfigParser(configparser.RawConfigParser):
    def read(self, filenames, encoding=None):
        if encoding is not None:
            return super().read(filenames, encoding=encoding)
        if isinstance(filenames, (str, bytes, os.PathLike)):
            filenames = [filenames]
        loaded = []
        for filename in filenames:
            try:
                loaded.extend(super().read(filename, encoding="utf-8-sig"))
            except UnicodeDecodeError:
                # Existing ANSI files written by older Windows AWS tools still work.
                loaded.extend(super().read(filename, encoding=locale.getpreferredencoding(False)))
        return loaded


def configure() -> None:
    # Replace only botocore's parser reference, never Python's global parser.
    # The SDK keeps profile merging, SSO and nested service configuration rules.
    parser_module = types.ModuleType("botocore_configparser")
    parser_module.__dict__.update(vars(configparser))
    parser_module.RawConfigParser = _ConfigParser
    botocore.configloader.configparser = parser_module
