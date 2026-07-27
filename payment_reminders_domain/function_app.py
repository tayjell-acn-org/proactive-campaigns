"""
Payment Reminders Domain Function App entry point (SCAFFOLD).

Placeholder second domain showing how a new campaign domain is added later
without changing shared_packages. Mirror the bill_variance_domain layout
(per-campaign gather timers + shared processor). A new Function App should
only be introduced for a distinct domain (TDD Sections 3.2, 14).
"""
import azure.functions as func

from shared_packages.observability import configure_logging

configure_logging()

from gatherer_trigger import bp as gatherer_bp
from processor_trigger import bp as processor_bp

app = func.FunctionApp()
app.register_functions(gatherer_bp)
app.register_functions(processor_bp)
