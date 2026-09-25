"""
Related attendance-web findings, all from the same audit pass:

GHSA-r59f-4xh4-58cf: the office-IP restriction trusted the first
X-Forwarded-For value unconditionally, so an attacker who supplies an
allowed address in that (client-controlled) header bypasses the restriction
entirely. get_client_ip() now only trusts the entries appended by the
ATTENDANCE_TRUSTED_PROXY_COUNT reverse proxies in front of the app.

GHSA-j3hc-6v4r-j658 (web clock-in/out skipped the geo-fence) is covered in
this fork by geofencing.utils.validate_request_location, which the web
views already call and which fails closed without coordinates.

The third copy of the reporting-manager truthy-HttpResponse bug (the same
root cause behind PR #3412's fixes to base.views.is_reportingmanger and
horilla_api...base.views._is_reportingmanger) lived in
attendance.methods.utils.is_reportingmanger, reached via
attendance.views.views.revalidate_this_attendance: an employee with no
work-info record yet made every caller's `or` chain pass for anyone.
"""

from datetime import date
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from attendance.methods.utils import get_client_ip, is_reportingmanger
from attendance.models import Attendance
from employee.models import EmployeeWorkInformation
from horilla.horilla_middlewares import set_selected_company
from horilla.testkit import make_company, make_employee, make_user


class GetClientIpTests(TestCase):
    def _request(self, remote_addr="10.0.0.5", xff=None):
        request = type("R", (), {"META": {"REMOTE_ADDR": remote_addr}})()
        if xff is not None:
            request.META["HTTP_X_FORWARDED_FOR"] = xff
        return request

    @override_settings(ATTENDANCE_TRUSTED_PROXY_COUNT=0)
    def test_x_forwarded_for_is_ignored_with_no_proxy_count_configured(self):
        request = self._request(remote_addr="203.0.113.9", xff="10.20.30.7")
        self.assertEqual(get_client_ip(request), "203.0.113.9")

    @override_settings(ATTENDANCE_TRUSTED_PROXY_COUNT=1)
    def test_address_appended_by_the_trusted_proxy_is_used(self):
        request = self._request(remote_addr="172.17.0.1", xff="198.51.100.4")
        self.assertEqual(get_client_ip(request), "198.51.100.4")

    @override_settings(ATTENDANCE_TRUSTED_PROXY_COUNT=1)
    def test_client_prepended_office_address_is_not_trusted(self):
        # nginx appends the real peer after whatever the client sent.
        request = self._request(
            remote_addr="172.17.0.1", xff="10.20.30.7, 198.51.100.4"
        )
        self.assertEqual(get_client_ip(request), "198.51.100.4")

    @override_settings(ATTENDANCE_TRUSTED_PROXY_COUNT=2)
    def test_short_chain_falls_back_to_remote_addr(self):
        request = self._request(remote_addr="172.17.0.1", xff="198.51.100.4")
        self.assertEqual(get_client_ip(request), "172.17.0.1")


class ThirdReportingManagerCopyTests(TestCase):
    """attendance.methods.utils.is_reportingmanger -- same bug, third copy."""

    def setUp(self):
        set_selected_company(None)
        self.company = make_company("Acme")
        boss_user = make_user("boss3", password="pw")
        self.boss = make_employee(
            company=self.company,
            email="boss3@acme.test",
            first_name="Boss",
            user=boss_user,
        )
        target_user = make_user("target3", password="pw")
        self.target = make_employee(
            company=self.company,
            email="target3@acme.test",
            first_name="Target",
            user=target_user,
        )

    def tearDown(self):
        set_selected_company(None)

    def _request_as(self, employee):
        request = type("R", (), {"user": employee.employee_user_id})()
        return request

    def test_returns_false_not_a_truthy_response_when_work_info_is_missing(self):
        EmployeeWorkInformation.objects.filter(employee_id=self.target).delete()
        attendance = Attendance.objects.create(
            employee_id=self.target,
            attendance_date=date(2026, 1, 5),
            attendance_clock_in="09:00",
            attendance_clock_in_date=date(2026, 1, 5),
        )
        result = is_reportingmanger(self._request_as(self.boss), attendance)
        self.assertIs(result, False)
        # The bug was specifically that this used to be truthy in an `or`
        # chain -- assert the falsy-ness directly, not just "not the manager".
        self.assertFalse(bool(result))


class RevalidateAttendanceRegressionTests(TestCase):
    """The one real call site of the fixed helper."""

    def setUp(self):
        set_selected_company(None)
        self.company = make_company("Acme2")
        stranger_user = make_user("stranger", password="pw")
        self.stranger = make_employee(
            company=self.company,
            email="stranger@acme.test",
            first_name="Stranger",
            user=stranger_user,
        )
        target_user = make_user("orphan", password="pw")
        self.target = make_employee(
            company=self.company,
            email="orphan@acme.test",
            first_name="Orphan",
            user=target_user,
        )
        EmployeeWorkInformation.objects.filter(employee_id=self.target).delete()
        self.attendance = Attendance.objects.create(
            employee_id=self.target,
            attendance_date=date(2026, 1, 5),
            attendance_clock_in="09:00",
            attendance_clock_in_date=date(2026, 1, 5),
            attendance_validated=True,
        )

    def tearDown(self):
        set_selected_company(None)

    def test_a_stranger_cannot_revalidate_an_orphaned_employees_attendance(self):
        client = Client()
        client.force_login(self.stranger.employee_user_id)
        client.get(reverse("revalidate-this-attendance", args=[self.attendance.pk]))
        self.attendance.refresh_from_db()
        self.assertTrue(self.attendance.attendance_validated)
