from django.db import migrations


PERMISSIONS = [
    ("dashboard.view", "View dashboard", "Dashboard"),
    ("subscriber.view", "View subscribers", "Subscribers"),
    ("subscriber.create", "Create subscribers", "Subscribers"),
    ("subscriber.edit", "Edit subscribers", "Subscribers"),
    ("subscriber.disable", "Disable subscribers", "Subscribers"),
    ("package.view", "View packages", "Packages"),
    ("package.manage", "Manage packages", "Packages"),
    ("voucher.view", "View vouchers", "Vouchers"),
    ("voucher.generate", "Generate vouchers", "Vouchers"),
    ("voucher.export", "Export vouchers", "Vouchers"),
    ("voucher.disable", "Disable vouchers", "Vouchers"),
    ("session.view", "View sessions", "Sessions"),
    ("session.disconnect", "Disconnect sessions", "Sessions"),
    ("router.view", "View routers", "Networking"),
    ("router.manage", "Manage routers", "Networking"),
    ("analytics.view", "View analytics", "Analytics"),
    ("role.manage", "Manage roles", "Access Control"),
    ("user.manage", "Manage tenant users", "Access Control"),
    ("audit.view", "View audit logs", "Audit"),
    ("settings.manage", "Manage tenant settings", "Settings"),
]


def seed_permissions(apps, schema_editor):
    permission_model = apps.get_model("core", "PamirPermission")
    for code, name, category in PERMISSIONS:
        permission_model.objects.update_or_create(
            code=code,
            defaults={"name": name, "category": category},
        )


def remove_permissions(apps, schema_editor):
    permission_model = apps.get_model("core", "PamirPermission")
    permission_model.objects.filter(code__in=[item[0] for item in PERMISSIONS]).delete()


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]

    operations = [migrations.RunPython(seed_permissions, remove_permissions)]
