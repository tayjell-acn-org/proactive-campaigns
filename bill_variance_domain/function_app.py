"""
Bill Variance Domain Function App entry point.

Registers the domain's triggers on a single FunctionApp instance: four
per-campaign gather (timer) triggers + one shared Service Bus processor
trigger (TDD Section 3.2/3.4 - keep gather and processor together per domain).
"""
import azure.functions as func

from shared_packages.observability import configure_logging

configure_logging()

from gatherer_trigger import bp as gatherer_bp
from processor_trigger import bp as processor_bp

app = func.FunctionApp()
app.register_functions(gatherer_bp)
app.register_functions(processor_bp)
