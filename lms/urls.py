"""LMS URL routes."""

from django.urls import path

from lms import views

urlpatterns = [
    path("", views.course_list, name="lms-course-list"),
    path("my/", views.my_learning, name="lms-my-learning"),
    path("courses/create/", views.course_create, name="lms-course-create"),
    path("courses/<int:pk>/", views.course_detail, name="lms-course-detail"),
    path("courses/<int:pk>/edit/", views.course_edit, name="lms-course-edit"),
    path("courses/<int:pk>/lesson/", views.lesson_add, name="lms-lesson-add"),
    path("courses/<int:pk>/enroll/", views.enroll_employees, name="lms-enroll"),
    path("courses/<int:pk>/enroll-self/", views.enroll_self, name="lms-enroll-self"),
    path(
        "enrollments/<int:enrollment_id>/lesson/<int:lesson_id>/complete/",
        views.complete_lesson,
        name="lms-complete-lesson",
    ),
    path(
        "enrollments/<int:enrollment_id>/certificate/",
        views.certificate_pdf,
        name="lms-certificate-pdf",
    ),
]
