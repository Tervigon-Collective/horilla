"""LMS views — course catalog, enrollments, lesson completion."""

from datetime import date

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from employee.models import Employee
from horilla.decorators import login_required, permission_required
from lms.models import Course, CourseEnrollment, Lesson, LessonProgress


def _company_filter(request, qs, field="company_id"):
    selected = request.session.get("selected_company")
    if selected and selected != "all":
        return qs.filter(**{field: selected})
    return qs


@login_required
def course_list(request):
    qs = Course.objects.filter(is_active=True)
    qs = _company_filter(request, qs)
    return render(request, "lms/course_list.html", {"courses": qs[:200]})


@login_required
def my_learning(request):
    employee = getattr(request.user, "employee_get", None)
    enrollments = []
    if employee:
        enrollments = (
            CourseEnrollment.objects.filter(employee_id=employee, is_active=True)
            .select_related("course_id")
            .order_by("-id")[:100]
        )
    return render(request, "lms/my_learning.html", {"enrollments": enrollments})


@login_required
@permission_required("lms.add_course")
def course_create(request):
    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        if not title:
            messages.error(request, _("Title is required."))
        else:
            company = None
            selected = request.session.get("selected_company")
            if selected and selected != "all":
                from base.models import Company

                company = Company.objects.filter(pk=selected).first()
            course = Course.objects.create(
                title=title,
                description=(request.POST.get("description") or "").strip(),
                duration_hours=float(request.POST.get("duration_hours") or 0),
                is_mandatory=request.POST.get("is_mandatory") == "1",
                company_id=company,
            )
            messages.success(request, _("Course created."))
            return redirect("lms-course-detail", pk=course.pk)
    return render(request, "lms/course_form.html", {"course": None})


@login_required
@permission_required("lms.change_course")
def course_edit(request, pk):
    course = get_object_or_404(Course, pk=pk)
    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        if not title:
            messages.error(request, _("Title is required."))
        else:
            course.title = title
            course.description = (request.POST.get("description") or "").strip()
            try:
                course.duration_hours = float(request.POST.get("duration_hours") or 0)
            except (TypeError, ValueError):
                pass
            course.is_mandatory = request.POST.get("is_mandatory") == "1"
            course.save()
            messages.success(request, _("Course updated."))
            return redirect("lms-course-detail", pk=course.pk)
    return render(request, "lms/course_form.html", {"course": course})


@login_required
def course_detail(request, pk):
    course = get_object_or_404(
        Course.objects.prefetch_related("lessons", "enrollments__employee_id"), pk=pk
    )
    employee = getattr(request.user, "employee_get", None)
    my_enrollment = None
    completed_lesson_ids = set()
    if employee:
        my_enrollment = CourseEnrollment.objects.filter(
            course_id=course, employee_id=employee
        ).first()
        if my_enrollment:
            completed_lesson_ids = set(
                my_enrollment.lesson_progress.filter(completed=True).values_list(
                    "lesson_id", flat=True
                )
            )
    employees = Employee.objects.filter(is_active=True).order_by(
        "employee_first_name", "employee_last_name"
    )[:500]
    return render(
        request,
        "lms/course_detail.html",
        {
            "course": course,
            "lessons": course.lessons.filter(is_active=True),
            "enrollments": course.enrollments.select_related("employee_id")[:100],
            "my_enrollment": my_enrollment,
            "completed_lesson_ids": completed_lesson_ids,
            "employees": employees,
        },
    )


@login_required
@permission_required("lms.add_lesson")
@require_http_methods(["POST"])
def lesson_add(request, pk):
    course = get_object_or_404(Course, pk=pk)
    title = (request.POST.get("title") or "").strip()
    if not title:
        messages.error(request, _("Lesson title is required."))
    else:
        seq = course.lessons.count() + 1
        try:
            minutes = int(request.POST.get("duration_minutes") or 0)
        except (TypeError, ValueError):
            minutes = 0
        Lesson.objects.create(
            course_id=course,
            title=title,
            content=(request.POST.get("content") or "").strip(),
            sequence=seq,
            duration_minutes=max(0, minutes),
        )
        messages.success(request, _("Lesson added."))
    return redirect("lms-course-detail", pk=course.pk)


@login_required
@permission_required("lms.add_courseenrollment")
@require_http_methods(["POST"])
def enroll_employees(request, pk):
    course = get_object_or_404(Course, pk=pk)
    ids = request.POST.getlist("employee_ids")
    due = None
    raw_due = request.POST.get("due_date")
    if raw_due:
        try:
            due = date.fromisoformat(raw_due)
        except ValueError:
            due = None
    created = 0
    for emp_id in ids:
        employee = Employee.objects.filter(pk=emp_id).first()
        if not employee:
            continue
        _, was_created = CourseEnrollment.objects.get_or_create(
            course_id=course,
            employee_id=employee,
            defaults={"due_date": due, "status": "enrolled"},
        )
        if was_created:
            created += 1
    messages.success(request, _("%(n)s employees enrolled.") % {"n": created})
    return redirect("lms-course-detail", pk=course.pk)


@login_required
@require_http_methods(["POST"])
def enroll_self(request, pk):
    course = get_object_or_404(Course, pk=pk, is_active=True)
    employee = getattr(request.user, "employee_get", None)
    if not employee:
        messages.error(request, _("No employee profile is linked to this user."))
        return redirect("lms-course-detail", pk=course.pk)
    _, created = CourseEnrollment.objects.get_or_create(
        course_id=course,
        employee_id=employee,
        defaults={"status": "enrolled"},
    )
    if created:
        messages.success(request, _("You are enrolled."))
    else:
        messages.info(request, _("You are already enrolled."))
    return redirect("lms-course-detail", pk=course.pk)


@login_required
@require_http_methods(["POST"])
def complete_lesson(request, enrollment_id, lesson_id):
    enrollment = get_object_or_404(CourseEnrollment, pk=enrollment_id)
    employee = getattr(request.user, "employee_get", None)
    if not (
        request.user.has_perm("lms.change_courseenrollment")
        or (employee and enrollment.employee_id_id == employee.pk)
    ):
        messages.error(request, _("Not allowed."))
        return redirect("lms-my-learning")

    lesson = get_object_or_404(Lesson, pk=lesson_id, course_id=enrollment.course_id)
    progress, _ = LessonProgress.objects.get_or_create(
        enrollment_id=enrollment, lesson_id=lesson
    )
    progress.completed = True
    progress.completed_on = date.today()
    progress.save()

    if enrollment.status == "enrolled":
        enrollment.status = "in_progress"
        enrollment.save(update_fields=["status"])

    total = enrollment.course_id.lessons.filter(is_active=True).count()
    done = LessonProgress.objects.filter(
        enrollment_id=enrollment, completed=True, lesson_id__is_active=True
    ).count()
    if total and done >= total:
        enrollment.status = "completed"
        enrollment.completed_on = date.today()
        enrollment.save(update_fields=["status", "completed_on"])
        messages.success(request, _("Course completed."))
    else:
        messages.success(request, _("Lesson marked complete."))
    return redirect("lms-course-detail", pk=enrollment.course_id_id)
