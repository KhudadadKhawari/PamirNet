from celery import shared_task
from django.conf import settings

from .services import cleanup_old_accounting_data


@shared_task(name="accounting.cleanup_old_data")
def cleanup_old_data():
    return cleanup_old_accounting_data(
        raw_days=getattr(settings, "ACCOUNTING_RAW_RETENTION_DAYS", 365),
        health_days=getattr(settings, "ROUTER_HEALTH_RETENTION_DAYS", 30),
    )
