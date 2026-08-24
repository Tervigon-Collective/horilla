"""
horilla_api/urls/attendance/urls.py
"""

from django.urls import path

from horilla_api.api_views.attendance.permission_views import AttendancePermissionCheck
from horilla_api.api_views.attendance.views import *

urlpatterns = [
    # Slash and no-slash variants: Flutter mixes both; POST + 301 loses the body.
    path("clock-in/", ClockInAPIView.as_view(), name="api-check-in"),
    path("clock-in", ClockInAPIView.as_view(), name="api-check-in-noslash"),
    path("clock-out/", ClockOutAPIView.as_view(), name="api-check-out"),
    path("clock-out", ClockOutAPIView.as_view(), name="api-check-out-noslash"),
    path("attendance/", AttendanceView.as_view(), name="api-attendance-list"),
    path("attendance", AttendanceView.as_view(), name="api-attendance-list-noslash"),
    path("attendance/<int:pk>", AttendanceView.as_view(), name="api-attendance-detail"),
    path(
        "attendance/list/<str:type>",
        AttendanceView.as_view(),
        name="api-attendance-list-type",
    ),
    path("attendance-validate/<int:pk>", ValidateAttendanceView.as_view()),
    path(
        "attendance-request/",
        AttendanceRequestView.as_view(),
        name="api-attendance-request-view",
    ),
    path(
        "attendance-request",
        AttendanceRequestView.as_view(),
        name="api-attendance-request-view-noslash",
    ),
    path(
        "attendance-request/<int:pk>",
        AttendanceRequestView.as_view(),
        name="api-attendance-request-detail",
    ),
    path(
        "attendance-request-approve/<int:pk>",
        AttendanceRequestApproveView.as_view(),
        name="api-attendance-request-approve",
    ),
    path(
        "attendance-request-cancel/<int:pk>",
        AttendanceRequestCancelView.as_view(),
        name="api-attendance-request-cancel",
    ),
    path("overtime-approve/<int:pk>", OvertimeApproveView.as_view(), name="api-ot-approve"),
    path(
        "attendance-hour-account/<int:pk>/",
        AttendanceOverTimeView.as_view(),
        name="api-hour-account-detail",
    ),
    path(
        "attendance-hour-account/<int:pk>",
        AttendanceOverTimeView.as_view(),
        name="api-hour-account-detail-noslash",
    ),
    path("attendance-hour-account/", AttendanceOverTimeView.as_view(), name="api-hour-account"),
    path(
        "attendance-hour-account",
        AttendanceOverTimeView.as_view(),
        name="api-hour-account-noslash",
    ),
    path("late-come-early-out-view/", LateComeEarlyOutView.as_view(), name="api-late-come"),
    path(
        "late-come-early-out-view",
        LateComeEarlyOutView.as_view(),
        name="api-late-come-noslash",
    ),
    path("attendance-activity/", AttendanceActivityView.as_view(), name="api-activity"),
    path(
        "attendance-activity",
        AttendanceActivityView.as_view(),
        name="api-activity-noslash",
    ),
    path("today-attendance/", TodayAttendance.as_view(), name="api-today-attendance"),
    path(
        "today-attendance",
        TodayAttendance.as_view(),
        name="api-today-attendance-noslash",
    ),
    path("offline-employees/count/", OfflineEmployeesCountView.as_view(), name="api-offline-count"),
    path(
        "offline-employees/count",
        OfflineEmployeesCountView.as_view(),
        name="api-offline-count-noslash",
    ),
    path("offline-employees/list/", OfflineEmployeesListView.as_view(), name="api-offline-list"),
    path(
        "offline-employees/list",
        OfflineEmployeesListView.as_view(),
        name="api-offline-list-noslash",
    ),
    path("permission-check/attendance", AttendancePermissionCheck.as_view()),
    path("permission-check/attendance/", AttendancePermissionCheck.as_view()),
    path("checking-in", CheckingStatus.as_view()),
    path("checking-in/", CheckingStatus.as_view()),
    path("offline-employee-mail-send", OfflineEmployeeMailsend.as_view()),
    path("converted-mail-template", ConvertedMailTemplateConvert.as_view()),
    path("mail-templates", MailTemplateView.as_view()),
    path("my-attendance/", UserAttendanceView.as_view()),
    path("my-attendance", UserAttendanceView.as_view()),
    path("attendance-type-check/", AttendanceTypeAccessCheck.as_view()),
    path("attendance-type-check", AttendanceTypeAccessCheck.as_view()),
    path("my-attendance-detailed/<int:id>/", UserAttendanceDetailedView.as_view()),
    path("my-attendance-detailed/<int:id>", UserAttendanceDetailedView.as_view()),
    path(
        "monthly-summary/",
        AttendanceMonthlySummaryAPIView.as_view(),
        name="api-attendance-monthly-summary",
    ),
    path(
        "monthly-summary",
        AttendanceMonthlySummaryAPIView.as_view(),
        name="api-attendance-monthly-summary-noslash",
    ),
]
