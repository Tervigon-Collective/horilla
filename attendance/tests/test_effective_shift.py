from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from attendance.methods.effective_shift import resolve_effective_shift
from attendance.methods.missing_punch import regularize_form_url


class EffectiveShiftTests(SimpleTestCase):
    def test_falls_back_to_work_info_shift(self):
        shift = SimpleNamespace(id=3)
        employee = SimpleNamespace(
            employee_work_info=SimpleNamespace(shift_id=shift)
        )
        roster_qs = MagicMock()
        roster_qs.filter.return_value.select_related.return_value.first.return_value = None
        with patch("base.models.Roster", SimpleNamespace(objects=roster_qs)):
            self.assertEqual(resolve_effective_shift(employee), shift)

    def test_uses_published_roster_shift(self):
        fallback = SimpleNamespace(id=1)
        roster_shift = SimpleNamespace(id=9)
        employee = SimpleNamespace(
            employee_work_info=SimpleNamespace(shift_id=fallback)
        )
        entry = SimpleNamespace(shift_id=9, shift=roster_shift)
        roster_qs = MagicMock()
        roster_qs.filter.return_value.select_related.return_value.first.return_value = entry
        with patch("base.models.Roster", SimpleNamespace(objects=roster_qs)):
            self.assertEqual(resolve_effective_shift(employee), roster_shift)


class MissingPunchUrlTests(SimpleTestCase):
    def test_existing_attendance_uses_update_form(self):
        record = SimpleNamespace(
            attendance_id_id=12,
            employee_id_id=4,
            date=None,
            shift_id_id=None,
            message="Missing punch out",
        )
        self.assertIn("update-attendance-request/12/", regularize_form_url(record))

    def test_no_attendance_uses_new_request(self):
        from datetime import date

        record = SimpleNamespace(
            attendance_id_id=None,
            employee_id_id=4,
            date=date(2026, 8, 24),
            shift_id_id=7,
            message="Missing punch in",
        )
        url = regularize_form_url(record)
        self.assertIn("request-new-attendance/", url)
        self.assertIn("missing_punch=1", url)
        self.assertIn("employee_id=4", url)
