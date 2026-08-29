"""Learning Management System models — courses, lessons, enrollments."""

from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from base.horilla_company_manager import HorillaCompanyManager
from base.models import Company
from employee.models import Employee
from horilla.models import HorillaModel


class Course(HorillaModel):
    """A learning course that employees can be enrolled in."""

    title = models.CharField(max_length=200, verbose_name=_("Title"))
    description = models.TextField(blank=True, null=True, verbose_name=_("Description"))
    duration_hours = models.FloatField(default=0, verbose_name=_("Duration (hours)"))
    is_mandatory = models.BooleanField(default=False, verbose_name=_("Mandatory"))
    company_id = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, verbose_name=_("Company")
    )

    objects = HorillaCompanyManager("company_id")

    class Meta:
        verbose_name = _("Course")
        verbose_name_plural = _("Courses")
        ordering = ["-id"]

    def __str__(self):
        return self.title

    def lesson_count(self):
        return self.lessons.filter(is_active=True).count()

    def get_absolute_url(self):
        return reverse("lms-course-detail", kwargs={"pk": self.pk})


class Lesson(HorillaModel):
    """One lesson / module inside a course."""

    course_id = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="lessons", verbose_name=_("Course")
    )
    title = models.CharField(max_length=200, verbose_name=_("Title"))
    content = models.TextField(blank=True, null=True, verbose_name=_("Content"))
    sequence = models.PositiveIntegerField(default=1, verbose_name=_("Sequence"))
    duration_minutes = models.PositiveIntegerField(default=0, verbose_name=_("Minutes"))

    class Meta:
        verbose_name = _("Lesson")
        verbose_name_plural = _("Lessons")
        ordering = ["sequence", "id"]

    def __str__(self):
        return f"{self.course_id}: {self.title}"


class CourseEnrollment(HorillaModel):
    """Employee enrollment in a course."""

    STATUS = [
        ("enrolled", _("Enrolled")),
        ("in_progress", _("In progress")),
        ("completed", _("Completed")),
    ]

    course_id = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="enrollments",
        verbose_name=_("Course"),
    )
    employee_id = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="course_enrollments",
        verbose_name=_("Employee"),
    )
    status = models.CharField(max_length=20, choices=STATUS, default="enrolled")
    enrolled_on = models.DateField(auto_now_add=True)
    due_date = models.DateField(null=True, blank=True, verbose_name=_("Due date"))
    completed_on = models.DateField(null=True, blank=True, verbose_name=_("Completed on"))
    certificate_id = models.CharField(
        max_length=32,
        blank=True,
        default="",
        verbose_name=_("Certificate ID"),
        help_text=_("Issued when the course is completed."),
    )

    objects = HorillaCompanyManager("employee_id__employee_work_info__company_id")

    class Meta:
        verbose_name = _("Course Enrollment")
        verbose_name_plural = _("Course Enrollments")
        unique_together = [("course_id", "employee_id")]
        ordering = ["-id"]

    def __str__(self):
        return f"{self.employee_id} → {self.course_id} ({self.status})"

    def ensure_certificate_id(self) -> str:
        """Assign immutable LMS-{pk:06d} id once the course is completed."""
        if self.certificate_id:
            return self.certificate_id
        if self.status != "completed" or not self.pk:
            return ""
        self.certificate_id = f"LMS-{self.pk:06d}"
        type(self).objects.filter(pk=self.pk).update(
            certificate_id=self.certificate_id
        )
        return self.certificate_id

    def progress_percent(self):
        total = self.course_id.lessons.filter(is_active=True).count()
        if total == 0:
            return 100 if self.status == "completed" else 0
        done = LessonProgress.objects.filter(
            enrollment_id=self, completed=True, lesson_id__is_active=True
        ).count()
        return round(100.0 * done / total)


class LessonProgress(HorillaModel):
    """Track lesson completion for an enrollment."""

    enrollment_id = models.ForeignKey(
        CourseEnrollment,
        on_delete=models.CASCADE,
        related_name="lesson_progress",
        verbose_name=_("Enrollment"),
    )
    lesson_id = models.ForeignKey(
        Lesson, on_delete=models.CASCADE, related_name="progress_rows", verbose_name=_("Lesson")
    )
    completed = models.BooleanField(default=False)
    completed_on = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = _("Lesson Progress")
        verbose_name_plural = _("Lesson Progress")
        unique_together = [("enrollment_id", "lesson_id")]

    def __str__(self):
        return f"{self.enrollment_id.employee_id} · {self.lesson_id}"
