"""
is_reportingmanger must be a scoped bool.

Approval guards across base/ and attendance/ call it directly, so both its
scoping (this employee, not "anyone") and its return type matter.
"""

from types import SimpleNamespace

from django.http import HttpResponse
from django.test import TestCase

from base.views import is_reportingmanger
from employee.models import Employee, EmployeeWorkInformation
from horilla.testkit import make_company, make_employee, make_user


def _reload(employee):
    """make_employee() caches employee_work_info; re-read after an .update()."""
    return Employee.objects.select_related("employee_work_info").get(pk=employee.pk)


class IsReportingMangerScopeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company("Scope Corp")

        cls.manager_user = make_user("scope_manager")
        cls.manager = make_employee(
            company=cls.company,
            email="scope_manager@test.horilla",
            user=cls.manager_user,
        )

        # Manages somebody, but not `report` - the case the blanket
        # is_reportingmanager() check used to wave through.
        cls.other_manager_user = make_user("scope_other_manager")
        cls.other_manager = make_employee(
            company=cls.company,
            email="scope_other_manager@test.horilla",
            user=cls.other_manager_user,
        )

        cls.report = make_employee(
            company=cls.company, email="scope_report@test.horilla"
        )
        EmployeeWorkInformation.objects.filter(employee_id=cls.report).update(
            reporting_manager_id=cls.manager
        )
        cls.report = _reload(cls.report)

        cls.other_report = make_employee(
            company=cls.company, email="scope_other_report@test.horilla"
        )
        EmployeeWorkInformation.objects.filter(employee_id=cls.other_report).update(
            reporting_manager_id=cls.other_manager
        )
        cls.other_report = _reload(cls.other_report)

    @staticmethod
    def _request(user):
        return SimpleNamespace(user=user)

    def test_direct_manager_is_allowed(self):
        instance = SimpleNamespace(employee_id=self.report)
        self.assertTrue(is_reportingmanger(self._request(self.manager_user), instance))

    def test_manager_of_someone_else_is_denied(self):
        """Managing *anyone* must not grant rights over an unrelated employee."""
        instance = SimpleNamespace(employee_id=self.report)
        self.assertFalse(
            is_reportingmanger(self._request(self.other_manager_user), instance)
        )

    def test_missing_work_info_returns_false_not_truthy_response(self):
        """
        Regression: this used to return an HttpResponse, which is truthy, so
        every caller guarding an approval with it granted the action to anyone
        whenever the subject had no work information.
        """
        orphan = make_employee(
            company=self.company, email="scope_orphan@test.horilla"
        )
        EmployeeWorkInformation.objects.filter(employee_id=orphan).delete()

        result = is_reportingmanger(
            self._request(self.other_manager_user),
            SimpleNamespace(employee_id=orphan),
        )

        self.assertNotIsInstance(result, HttpResponse)
        self.assertFalse(result)
