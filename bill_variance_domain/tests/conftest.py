"""
Ensure the repo root is importable so `shared_packages` resolves during tests.
Run tests from the bill_variance_domain folder with the repo root on sys.path,
or `pip install -e` the shared packages in a real setup.
"""
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

DOMAIN_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if DOMAIN_ROOT not in sys.path:
    sys.path.insert(0, DOMAIN_ROOT)
