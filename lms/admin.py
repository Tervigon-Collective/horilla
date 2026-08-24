from django.contrib import admin

from lms.models import Course, CourseEnrollment, Lesson, LessonProgress

admin.site.register([Course, Lesson, CourseEnrollment, LessonProgress])
