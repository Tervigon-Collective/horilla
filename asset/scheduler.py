"""
scheduler.py

This module is used to register scheduled tasks
"""

import sys
from datetime import date, timedelta

from horilla.db import SafeBackgroundScheduler
from django.urls import reverse

from notifications.signals import notify


def notify_expiring_assets():
    """
    Finds all Expiring Assets and send a notification on the notify_before date.
    """
    from asset.models import Asset
    from horilla_auth.models import HorillaUser

    today = date.today()

    # Cache bot & superuser once
    bot = HorillaUser.objects.filter(username="Horilla Bot").only("id").first()
    superuser = HorillaUser.objects.filter(is_superuser=True).only("id").first()

    # Query only assets that are expiring today
    assets = Asset.objects.filter(
        expiry_date__isnull=False,
        expiry_date__gte=today,
    )

    for asset in assets:
        if asset.expiry_date:
            expiry_date = asset.expiry_date
            notify_days = asset.notify_before if asset.notify_before is not None else 1
            notify_date = expiry_date - timedelta(days=notify_days)
            recipient = getattr(asset.owner, "employee_user_id", None) or superuser
            if notify_date == today and recipient:
                notify.send(
                    bot,
                    recipient=recipient,
                    verb=f"The Asset '{asset.asset_name}' expires in {notify_days} days",
                    verb_ar=f"تنتهي صلاحية الأصل '{asset.asset_name}' خلال {notify_days} من الأيام",
                    verb_de=f"Das Asset {asset.asset_name} läuft in {notify_days} Tagen ab.",
                    verb_es=f"El activo {asset.asset_name} caduca en {notify_days} días.",
                    verb_fr=f"L'actif {asset.asset_name} expire dans {notify_days} jours.",
                    redirect=reverse("asset-category-view"),
                    label="System",
                    icon="information",
                )


def mark_expired_assets():
    """
    Finds all assets past their expiry date and sets their status to Not-Available.
    """
    from asset.models import Asset

    today = date.today()
    expired = Asset.objects.filter(
        expiry_date__isnull=False,
        expiry_date__lt=today,
    ).exclude(asset_status="Not-Available")
    for asset in expired:
        asset.asset_status = "Not-Available"
        asset.save()


def notify_expiring_documents():
    """
    Notify employees (and reporting managers) on the notify-before date,
    and deactivate documents past expiry.
    """
    from horilla_auth.models import HorillaUser
    from horilla_documents.models import Document

    today = date.today()
    bot = HorillaUser.objects.filter(username="Horilla Bot").first()
    documents = Document.objects.filter(
        expiry_date__isnull=False
    ).select_related(
        "employee_id",
        "employee_id__employee_user_id",
        "employee_id__employee_work_info",
        "employee_id__employee_work_info__reporting_manager_id",
        "employee_id__employee_work_info__reporting_manager_id__employee_user_id",
    )

    for document in documents:
        expiry_date = document.expiry_date
        notify_days = document.notify_before if document.notify_before is not None else 1
        notify_date = expiry_date - timedelta(days=max(0, int(notify_days)))

        if notify_date == today and document.is_active:
            employee = document.employee_id
            recipients = []
            user = getattr(employee, "employee_user_id", None)
            if user:
                recipients.append(user)
            work_info = getattr(employee, "employee_work_info", None)
            manager = getattr(work_info, "reporting_manager_id", None) if work_info else None
            manager_user = getattr(manager, "employee_user_id", None) if manager else None
            if manager_user and manager_user not in recipients:
                recipients.append(manager_user)

            redirect = reverse("expiring-documents-list") + "?tab=soon"
            for recipient in recipients:
                try:
                    notify.send(
                        bot,
                        recipient=recipient,
                        verb=(
                            f"The document '{document.title}' for "
                            f"{employee.get_full_name()} expires in {notify_days} days"
                        ),
                        verb_ar=(
                            f"تنتهي صلاحية المستند '{document.title}' خلال {notify_days} يوم"
                        ),
                        verb_de=(
                            f"Das Dokument '{document.title}' läuft in {notify_days} Tagen ab."
                        ),
                        verb_es=(
                            f"El documento '{document.title}' caduca en {notify_days} días"
                        ),
                        verb_fr=(
                            f"Le document '{document.title}' expire dans {notify_days} jours"
                        ),
                        redirect=redirect,
                        label="System",
                        icon="information",
                    )
                except Exception:
                    pass

        if today >= expiry_date and document.is_active:
            Document.objects.filter(pk=document.pk).update(is_active=False)


if not any(
    cmd in sys.argv
    for cmd in ["makemigrations", "migrate", "compilemessages", "flush", "shell"]
):
    scheduler = SafeBackgroundScheduler()
    scheduler.add_job(notify_expiring_assets, "interval", days=1)
    scheduler.add_job(notify_expiring_documents, "interval", hours=4)
    scheduler.add_job(mark_expired_assets, "interval", days=1)
    scheduler.start()
