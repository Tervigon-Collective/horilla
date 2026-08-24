from django.test import SimpleTestCase

from lms.models import Course, CourseEnrollment, Lesson, LessonProgress


class LmsModelSmokeTests(SimpleTestCase):
    def test_models_import(self):
        self.assertEqual(Course._meta.label, "lms.Course")
        self.assertEqual(Lesson._meta.label, "lms.Lesson")
        self.assertEqual(CourseEnrollment._meta.label, "lms.CourseEnrollment")
        self.assertEqual(LessonProgress._meta.label, "lms.LessonProgress")
