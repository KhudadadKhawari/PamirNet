from celery import shared_task

from .services import expire_due_vouchers


@shared_task(name="vouchers.expire_due_vouchers")
def expire_due_vouchers_task():
    return expire_due_vouchers()
