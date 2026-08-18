"""
This page is handling the cbv methods of mail log tab in employee individual page.
"""

from typing import Any

from django.contrib import messages
from django.db.models import Q
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _

from base.filters import MailLogFilter
from base.models import EmailLog
from employee.cbv.accessibility import is_hr_user
from employee.models import Employee
from horilla.http.response import HorillaRedirect
from horilla_views.cbv_methods import login_required
from horilla_views.generic.cbv.views import HorillaDetailedView, HorillaListView


@method_decorator(login_required, name="dispatch")
class MailLogTabList(HorillaListView):
    """
    list view for mail log  tab
    """

    model = EmailLog
    filter_class = MailLogFilter

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.view_id = "maillog"

        pk = self.request.resolver_match.kwargs.get("pk")
        self.search_url = reverse("individual-email-log-list", kwargs={"pk": pk})

    # def get_context_data(self, **kwargs: Any):
    #     context = super().get_context_data(**kwargs)
    #     pk = self.kwargs.get('pk')
    #     context["search_url"] = f"{reverse('individual-email-log-list',kwargs={'pk': pk})}"
    #     return context

    def dispatch(self, request, *args, **kwargs):
        if not is_hr_user(request):
            messages.info(request, _("You dont have access to the feature"))
            return HorillaRedirect(request)
        pk = kwargs.get("pk")
        if not Employee.objects.filter(id=pk).exists():
            messages.error(request, _("Employee not found."))
            return HorillaRedirect(request)
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        pk = self.kwargs.get("pk")
        employee = Employee.objects.get(id=pk)
        query_filter = Q(to__icontains=employee.email)
        queryset = queryset.filter(to__icontains=employee.email)
        if employee.employee_work_info and employee.employee_work_info.email:
            query_filter |= Q(to__icontains=employee.employee_work_info.email)
            queryset = queryset.filter(query_filter)
            queryset = queryset.order_by("-created_at")

        return queryset

    columns = [
        (_("Subject"), "subject"),
        (_("Date"), "created_at"),
        (_("Status"), "status_display"),
    ]

    sortby_mapping = [
        (_("Subject"), "subject"),
        (_("Date"), "created_at"),
    ]

    row_attrs = """
                hx-get='{mail_log_detail_view}?instance_ids={ordered_ids}'
                hx-target="#genericModalBody"
                data-target="#genericModal"
                data-toggle="oh-modal-toggle"
                """


@method_decorator(login_required, name="dispatch")
class MailLogDetailView(HorillaDetailedView):
    """
    detail view for mail log tab
    """

    template_name = "cbv/mail_log_tab/iframe.html"
    model = EmailLog

    def get_context_data(self, **kwargs: Any):
        context = super().get_context_data(**kwargs)
        pk = self.kwargs.get("pk")
        log = EmailLog.objects.filter(id=pk).first()
        context["log"] = log
        return context

    header = {"title": "", "subtitle": "", "avatar": ""}

    def dispatch(self, request, *args, **kwargs):
        if not is_hr_user(request):
            messages.info(request, _("You dont have access to the feature"))
            return HorillaRedirect(request)
        return super().dispatch(request, *args, **kwargs)
