# AT&T Proactive Outreach — Campaign Execution Platform

Reusable, config-driven platform for proactive outreach campaigns. Organized
by **campaign domain** (per the Technical Design Document), with reusable
capabilities in `shared_packages/` and one Azure Function App per domain.

The **Bill Variance** domain is implemented first, with **Pending Credits** as
the MVP campaign. Additional domains (e.g. Payment Reminders) are added as
sibling folders without changing the core platform.

## Structure

```text
proactive-campaigns/
├── shared_packages/                 # reused by every domain
│   ├── base_db/                     # Snowflake/ECDW source client
│   ├── communication_service/       # NotifyNow REST adapter (+ retries)
│   ├── observability/               # structured logging + OperationalTracker
│   ├── campaign_models/             # CampaignWorkMessage, CampaignConfig, ...
│   ├── configuration/               # App Config + Key Vault loader
│   └── validation/                  # required-field / email validators
│
├── bill_variance_domain/            # Function App #1 (implemented)
│   ├── function_app.py              # registers gather + processor blueprints
│   ├── gatherer_trigger.py          # TIMER trigger -> publishes Service Bus msgs
│   ├── processor_trigger.py         # SERVICE BUS trigger -> dispatch to campaign
│   ├── campaigns/
│   │   ├── __init__.py              # campaign factory (id -> handler)
│   │   ├── pending_credits/         # MVP — fully scaffolded (Steps 1-10)
│   │   ├── promotion_expiry/
│   │   ├── autopay_expiry/
│   │   └── international_roaming_charges/
│   ├── tests/{unit,integration}/
│   ├── host.json / local.settings.json / requirements.txt / .funcignore
│
├── payment_reminders_domain/        # Function App #2 (scaffold for later)
│
└── pipelines/                       # CI/CD workflows per domain
    ├── bill_variance_domain.yml
    └── payment_reminders_domain.yml
```

## Architecture (per domain)

```text
Timer (gather) ──► Azure Service Bus queue ──► Service Bus (processor) ──► NotifyNow
     │                                               │
 identify eligible accounts,                    per-account business logic,
 publish 1 message per account            contact lookup, payload, handoff + retries
```

Keeping the gather and processor triggers in the **same** domain Function App
(connected by Service Bus) gives scale-out, retries, throttling, and DLQ
handling while reducing operational overhead.

## Run locally

Prereqs: Python 3.11, Azure Functions Core Tools v4, Azurite (or a real
storage account), and a Service Bus connection string.

```bash
cd bill_variance_domain
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# shared_packages must be importable — copy it in for local runs
# (CI bundles it automatically; see pipelines/):
cp -r ../shared_packages ./shared_packages

# fill in local.settings.json values, then:
func start
```

## Run tests

```bash
cd bill_variance_domain
pip install pytest
pytest tests/unit -q
```

## Add a new campaign (same domain)

1. Create `campaigns/<new_campaign>/rules.py` with a `process(work)` function.
2. Register it in `campaigns/__init__.py` (`campaign_id -> handler`).
3. Add a config entry (`active_flag=false` until validated).
4. Add unit/integration tests.

## Add a new domain

Copy `payment_reminders_domain/` as a template, add a `pipelines/<domain>.yml`,
and reuse everything in `shared_packages/`. Introduce a new domain only when it
has distinct rules, sources, ownership, security, or scaling needs.

## Notes / TODO

- Source queries (Snowflake/ECDW/Telegence), Customer Graph, and IDM lookups
  are stubbed and marked `# TODO` — wire them as access is onboarded.
- Secrets (NotifyNow, Snowflake) belong in Key Vault; non-secret settings in
  App Configuration. Use managed identity where approved.
- Finalize run window/frequency, retry thresholds, and reconciliation rules
  in configuration before production activation.
