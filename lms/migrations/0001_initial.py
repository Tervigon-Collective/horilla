# Initial LMS models

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("base", "0001_initial"),
        ("employee", "0007_job_grade"),
    ]

    operations = [
        migrations.CreateModel(
            name="Course",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, blank=True, null=True, verbose_name="Created At")),
                ("is_active", models.BooleanField(default=True, verbose_name="Is Active")),
                ("title", models.CharField(max_length=200, verbose_name="Title")),
                ("description", models.TextField(blank=True, null=True, verbose_name="Description")),
                ("duration_hours", models.FloatField(default=0, verbose_name="Duration (hours)")),
                ("is_mandatory", models.BooleanField(default=False, verbose_name="Mandatory")),
                ("company_id", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to="base.company", verbose_name="Company")),
                ("created_by", models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name="Created By")),
                ("modified_by", models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="course_modified_by", to=settings.AUTH_USER_MODEL, verbose_name="Modified By")),
            ],
            options={"verbose_name": "Course", "verbose_name_plural": "Courses", "ordering": ["-id"]},
        ),
        migrations.CreateModel(
            name="Lesson",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, blank=True, null=True, verbose_name="Created At")),
                ("is_active", models.BooleanField(default=True, verbose_name="Is Active")),
                ("title", models.CharField(max_length=200, verbose_name="Title")),
                ("content", models.TextField(blank=True, null=True, verbose_name="Content")),
                ("sequence", models.PositiveIntegerField(default=1, verbose_name="Sequence")),
                ("duration_minutes", models.PositiveIntegerField(default=0, verbose_name="Minutes")),
                ("course_id", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lessons", to="lms.course", verbose_name="Course")),
                ("created_by", models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name="Created By")),
                ("modified_by", models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="lesson_modified_by", to=settings.AUTH_USER_MODEL, verbose_name="Modified By")),
            ],
            options={"verbose_name": "Lesson", "verbose_name_plural": "Lessons", "ordering": ["sequence", "id"]},
        ),
        migrations.CreateModel(
            name="CourseEnrollment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, blank=True, null=True, verbose_name="Created At")),
                ("is_active", models.BooleanField(default=True, verbose_name="Is Active")),
                ("status", models.CharField(choices=[("enrolled", "Enrolled"), ("in_progress", "In progress"), ("completed", "Completed")], default="enrolled", max_length=20)),
                ("enrolled_on", models.DateField(auto_now_add=True)),
                ("due_date", models.DateField(blank=True, null=True, verbose_name="Due date")),
                ("completed_on", models.DateField(blank=True, null=True, verbose_name="Completed on")),
                ("course_id", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="enrollments", to="lms.course", verbose_name="Course")),
                ("created_by", models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name="Created By")),
                ("employee_id", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="course_enrollments", to="employee.employee", verbose_name="Employee")),
                ("modified_by", models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="courseenrollment_modified_by", to=settings.AUTH_USER_MODEL, verbose_name="Modified By")),
            ],
            options={"verbose_name": "Course Enrollment", "verbose_name_plural": "Course Enrollments", "ordering": ["-id"], "unique_together": {("course_id", "employee_id")}},
        ),
        migrations.CreateModel(
            name="LessonProgress",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, blank=True, null=True, verbose_name="Created At")),
                ("is_active", models.BooleanField(default=True, verbose_name="Is Active")),
                ("completed", models.BooleanField(default=False)),
                ("completed_on", models.DateField(blank=True, null=True)),
                ("created_by", models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name="Created By")),
                ("enrollment_id", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lesson_progress", to="lms.courseenrollment", verbose_name="Enrollment")),
                ("lesson_id", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="progress_rows", to="lms.lesson", verbose_name="Lesson")),
                ("modified_by", models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="lessonprogress_modified_by", to=settings.AUTH_USER_MODEL, verbose_name="Modified By")),
            ],
            options={"verbose_name": "Lesson Progress", "verbose_name_plural": "Lesson Progress", "unique_together": {("enrollment_id", "lesson_id")}},
        ),
    ]
