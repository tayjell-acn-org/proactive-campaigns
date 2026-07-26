"""
Bill Variance Domain Function App entry point.

Registers the domain's triggers on a single FunctionApp instance so the
gather (timer) and processor (Service Bus) triggers deploy together
(TDD Section 3.2 - keep both triggers in the same domain app unless
security/networking/long-running needs require a split).
"""
import azure.functions as func

from shared_packages.observability import configure_logging

configure_logging()

# Blueprints keep each trigger in its own module for readability.
from gatherer_trigger import bp as gatherer_bp
from processor_trigger import bp as processor_bp

app = func.FunctionApp()
app.register_functions(gatherer_bp)
app.register_functions(processor_bp)
