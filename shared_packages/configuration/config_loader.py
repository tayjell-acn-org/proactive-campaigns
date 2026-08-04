"""
Configuration loader.

Non-secret runtime settings come from Azure App Configuration; secrets
(NotifyNow credentials, source/SQL connection strings, API keys) come from
Azure Key Vault, accessed via managed identity where approved
(TDD Sections 4.1 / 10). Degrades gracefully to environment variables so it
can run locally before the Azure resources are provisioned.
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Optional

from shared_packages.campaign_models import CampaignConfig

logger = logging.getLogger(__name__)


class ConfigLoader:
    def __init__(
        self,
        app_config_endpoint: Optional[str] = None,
        key_vault_uri: Optional[str] = None,
    ) -> None:
        self.app_config_endpoint = app_config_endpoint or os.getenv("APP_CONFIG_ENDPOINT")
        self.key_vault_uri = key_vault_uri or os.getenv("KEY_VAULT_URI")
        self._app_config_client = None
        self._secret_client = None

    def _get_app_config_client(self):
        if self._app_config_client is None and self.app_config_endpoint:
            try:
                from azure.appconfiguration import AzureAppConfigurationClient
                from azure.identity import DefaultAzureCredential

                self._app_config_client = AzureAppConfigurationClient(
                    base_url=self.app_config_endpoint,
                    credential=DefaultAzureCredential(),
                )
            except Exception as exc:  # pragma: no cover - infra dependent
                logger.warning("App Configuration client unavailable: %s", exc)
        return self._app_config_client

    def _get_secret_client(self):
        if self._secret_client is None and self.key_vault_uri:
            try:
                from azure.identity import DefaultAzureCredential
                from azure.keyvault.secrets import SecretClient

                self._secret_client = SecretClient(
                    vault_url=self.key_vault_uri,
                    credential=DefaultAzureCredential(),
                )
            except Exception as exc:  # pragma: no cover - infra dependent
                logger.warning("Key Vault client unavailable: %s", exc)
        return self._secret_client

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Read a non-secret runtime setting (App Config -> env var fallback)."""
        client = self._get_app_config_client()
        if client:
            try:
                setting = client.get_configuration_setting(key=key)
                if setting is not None:
                    return setting.value
            except Exception as exc:  # pragma: no cover - infra dependent
                logger.warning("App Config read failed for %s: %s", key, exc)
        return os.getenv(key, default)

    def get_secret(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """Read a secret value (Key Vault -> env var fallback)."""
        client = self._get_secret_client()
        if client:
            try:
                return client.get_secret(name).value
            except Exception as exc:  # pragma: no cover - infra dependent
                logger.warning("Key Vault read failed for %s: %s", name, exc)
        return os.getenv(name, default)

    def get_active_campaigns(self, domain: str) -> list[CampaignConfig]:
        """
        Return the active campaign configurations for a domain.

        TODO: Replace the local fallback with a real lookup against the
        approved campaign config store (App Configuration). Only campaigns with
        active_flag == True should be returned (TDD Sections 4.1 / 4.3).
        """
        fallback = {
            "bill_variance_domain": [
                CampaignConfig(
                    campaign_id="PENDING_CREDITS",
                    campaign_name="Pending Credits",
                    active_flag=True,
                    source_profile="TELEGENCE_MOBILITY",
                    eligibility_rule_set="PendingCreditsRules",
                ),
                CampaignConfig(
                    campaign_id="PROMOTION_EXPIRY",
                    campaign_name="Promotion Expiry",
                    active_flag=True,
                    source_profile="TELEGENCE_MOBILITY",
                    eligibility_rule_set="PromotionExpiryRules",
                ),
            ],
            "payment_reminders_domain": [],
        }
        campaigns = fallback.get(domain, [])
        return [c for c in campaigns if c.active_flag]

    def get_campaign(self, domain: str, campaign_id: str) -> Optional[CampaignConfig]:
        """Return a single active campaign config by id, or None."""
        for campaign in self.get_active_campaigns(domain):
            if campaign.campaign_id == campaign_id:
                return campaign
        return None


@lru_cache(maxsize=1)
def get_config_loader() -> ConfigLoader:
    """Cached singleton for the process lifetime."""
    return ConfigLoader()
