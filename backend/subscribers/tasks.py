from celery import shared_task

from .services import expire_due_subscriptions


@shared_task(name="subscribers.expire_due_subscriptions")
def expire_due_subscriptions_task():
    return expire_due_subscriptions()
