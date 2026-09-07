from celery import shared_task

from .models import Router
from .services import check_router_health


@shared_task(name="networking.check_all_routers")
def check_all_routers():
    checked = 0
    for router in Router.objects.filter(enabled=True).iterator():
        check_router_health(router)
        checked += 1
    return checked
