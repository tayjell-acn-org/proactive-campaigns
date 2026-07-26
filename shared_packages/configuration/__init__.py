"""Configuration loading from Azure App Configuration + Key Vault."""
from .config_loader import ConfigLoader, get_config_loader

__all__ = ["ConfigLoader", "get_config_loader"]
