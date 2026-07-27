"""
Ensure the repo root and domain root are importable so `shared_packages` and
`campaigns` resolve during tests without the copy/deploy step.
"""
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOMAIN_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for path in (REPO_ROOT, DOMAIN_ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)
