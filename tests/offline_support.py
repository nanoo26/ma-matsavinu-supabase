"""Offline imports: fake configuration, no dotenv files and no real HTTP."""

import importlib.util
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import requests

ROOT = Path(__file__).resolve().parents[1]


def load_offline_module(filename, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    with (
        patch.dict(os.environ, {
            "SUPABASE_URL": "https://offline.invalid",
            "SUPABASE_KEY": "offline-dummy-key",
            "SECRET_KEY": "offline-dummy-session-secret",
        }, clear=True),
        patch("dotenv.load_dotenv", return_value=False),
        patch.dict(sys.modules, {name: module}),
    ):
        spec.loader.exec_module(module)
    return module


class OfflineCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        blocker = patch.object(
            requests.sessions.Session, "request",
            side_effect=AssertionError("Real HTTP is forbidden in offline tests"),
        )
        blocker.start()
        cls.addClassCleanup(blocker.stop)
