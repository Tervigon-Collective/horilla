"""
Document bulk approve/reject must only touch employees the caller manages.

Both views mass-updated whatever ids arrived in the POST, so anyone past the
manager gate could approve or reject any employee's documents.
"""

from django.test import TestCase
from django.urls import reverse

from employee.models import Employee, EmployeeWorkInformation
from horilla.testkit import make_company, make_employee, make_user
from horilla_documents.models import Document


def _reload(employee):
    """make_employee() caches employee_work_info; re-read after an .update()."""
    return Employee.objects.select_related("employee_work_info").get(pk=employee.pk)


class DocumentBulkScopeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company("Docs Corp")

        cls.manager_user = make_user("docs_manager", password="secret123")
        cls.manager = make_employee(
            company=cls.company,
            email="docs_manager@test.horilla",
            user=cls.manager_user,
        )

        cls.report = make_employee(
            company=cls.company, email="docs_report@test.horilla"
        )
        EmployeeWorkInformation.objects.filter(employee_id=cls.report).update(
            reporting_manager_id=cls.manager
        )
        cls.report = _reload(cls.report)

        # Nobody's reportee - the manager must not be able to touch this one.
        cls.stranger = make_employee(
            company=cls.company, email="docs_stranger@test.horilla"
        )

    def _make_doc(self, employee):
        return Document.objects.create(
            title=f"Doc for {employee.pk}",
            employee_id=employee,
            document="uploads/some-file.pdf",
            status="requested",
        )

    def test_bulk_approve_skips_employees_the_manager_does_not_manage(self):
        mine = self._make_doc(self.report)
        theirs = self._make_doc(self.stranger)

        self.client.force_login(self.manager_user)
        self.client.post(
            reverse("document-bulk-approve"),
            {"ids": [str(mine.pk), str(theirs.pk)]},
        )

        mine.refresh_from_db()
        theirs.refresh_from_db()
        self.assertEqual(mine.status, "approved")
        self.assertNotEqual(theirs.status, "approved")

    def test_bulk_reject_skips_employees_the_manager_does_not_manage(self):
        mine = self._make_doc(self.report)
        theirs = self._make_doc(self.stranger)

        self.client.force_login(self.manager_user)
        self.client.post(
            reverse("document-bulk-reject"),
            {
                "ids": [str(mine.pk), str(theirs.pk)],
                "reject_reason": "Not legible enough",
            },
        )

        mine.refresh_from_db()
        theirs.refresh_from_db()
        self.assertNotEqual(theirs.status, "rejected")
