# AT&T Proactive Outreach — Campaign Execution Platform

Reusable, config-driven platform for proactive outreach campaigns, organized by
**campaign domain** (TDD Section 4.2). Reusable capabilities live in
`shared_packages/`; each domain is one Azure Function App.

The **Bill Variance** domain implements all four MVP campaigns —
**Pending Credits, Promotion Expiry, Autopay Discount Expiry, and
International Roaming Charges** — aligned to the implementation steps in TDD
Section 5.1.

## What changed in this version

- **Four separate timer triggers** — one per campaign, each on its own schedule
  app setting (`%PENDING_CREDITS_SCHEDULE%`, etc.). All publish to one Service
  Bus queue; the shared processor routes by `campaign_id`.
- **Updated step logic (TDD 5.1):**
  - Pending Credits / Promotion Expiry / Autopay Discount Expiry follow the
    shared **8-step** pattern: (1) Snowflake segment query → (2) Business Rules →
    (3) **Suppression** → (4) Online Account (IDM/Customer Graph) →
    (5) Billing Contact (mBiz/ROME) → (6) Customer Contacts (Customer Graph) →
    (7) NotifyNow handoff → (8) persist to **Azure SQL DB**.
  - International Roaming Charges follows the **9-step event-driven** pattern
    (detect event → coverage → eligibility → account/segment → contact role →
    resolve contact → registration → persist → NotifyNow).
- **New shared packages:** `suppression/` (Step 3) and `base_db/sql_repository.py`
  (Azure SQL DB operational store — `CampaignRun` + `AccountEligibilitySuppression`).

## Structure

```text
proactive-campaigns/
├── shared_packages/
│   ├── base_db/                 # SnowflakeClient + SqlRepository (Azure SQL DB)
│   ├── communication_service/   # NotifyNow adapter (retries + idempotency)
│   ├── observability/           # JSON logging + OperationalTracker (SQL-backed)
│   ├── campaign_models/         # WorkMessage, Config, Run, AudienceRecord, statuses
│   ├── configuration/           # App Config + Key Vault loader
│   ├── suppression/             # SuppressionService (Step 3)
│   └── validation/              # required-field / email validators
│
├── bill_variance_domain/        # Function App #1 (implemented)
│   ├── function_app.py          # 4 gather timers + 1 processor
│   ├── gatherer_trigger.py      # per-campaign TIMER triggers -> Service Bus
│   ├── processor_trigger.py     # SERVICE BUS trigger -> campaign factory
│   ├── campaigns/
│   │   ├── __init__.py          # factory: id -> (get_candidates, process)
│   │   ├── pending_credits/     # 8-step MVP
│   │   ├── promotion_expiry/    # 8-step
│   │   ├── autopay_expiry/      # 8-step
│   │   └── international_roaming_charges/  # 9-step event-driven
│   ├── tests/{unit,integration}/
│   └── host.json · local.settings.json · requirements.txt · .funcignore
│
├── payment_reminders_domain/    # Function App #2 (scaffold)
├── pipelines/                   # per-domain CI/CD
└── README.md · .gitignore · .vscode/
```

## Per-campaign schedules

Set one NCRONTAB app setting per campaign — `{sec} {min} {hour} {day} {month} {dow}`:

```json
"PENDING_CREDITS_SCHEDULE": "0 0 8 * * *",
"PROMOTION_EXPIRY_SCHEDULE": "0 30 8 * * *",
"AUTOPAY_DISCOUNT_EXPIRY_SCHEDULE": "0 0 9 * * *",
"INTERNATIONAL_ROAMING_CHARGES_SCHEDULE": "0 0 * * * *"
```

Staggering start times also spreads load on Snowflake and NotifyNow. Each
timer's schedule setting must exist in every environment or that function
fails to start.

## Local prerequisites

1. **Azurite** running (Blob/Queue on 10000/10001) — the timers use
   `use_monitor` blob state, and the Functions host needs storage.
2. **Service Bus** connection set in `SERVICE_BUS_CONNECTION` and the queue
   `bill-variance-work` created.
3. `shared_packages` importable — for local `func start`, copy it in:
   `cp -r ../shared_packages ./shared_packages` (CI bundles it automatically).

```bash
cd bill_variance_domain
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
xcopy /E /I /Y ..\shared_packages shared_packages
func start
```

## Testing & manually triggering a timer

```bash
cd bill_variance_domain
pip install pytest
pytest tests/unit -q
```

To fire a gather without waiting for its schedule, either set
`run_on_startup=True` temporarily, or call the admin endpoint while the host
runs:

```bash
curl -X POST http://localhost:7071/admin/functions/gather_pending_credits \
  -H "Content-Type: application/json" -d '{}'
```

## Add a new campaign (same domain)

1. Create `campaigns/<new_campaign>/rules.py` with `get_candidates(config)`
   (Step 1) and `process(work)` (remaining steps).
2. Register it in `campaigns/__init__.py`.
3. Add a per-campaign schedule app setting and a timer function in
   `gatherer_trigger.py`.
4. Add a config entry (`active_flag=false` until validated) and tests.

## Notes / TODO

- Source queries (Snowflake), IDM/Customer Graph, mBiz/ROME, and the Azure SQL
  DB writes are stubbed and marked `# TODO` — wire them as access is onboarded.
- Secrets (NotifyNow, Snowflake, SQL) belong in Key Vault; non-secret settings
  in App Configuration. Use managed identity where approved.
- The `SqlRepository` runs in-memory until `SQL_CONNECTION_STRING` is set, so
  suppression and reconciliation work end-to-end locally.
