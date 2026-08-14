"""Backward-compat shim for section DB imports.

Sections import ``xdb`` from `..db_ext`. The merged database lives in
`botguardian.db` and exposes every method the sections need. This module
simply re-exports ``db`` under the section name so we don't duplicate
SQL helpers in two places.
"""
from __future__ import annotations

from ..db import db as xdb  # noqa: F401

__all__ = ["xdb"]
