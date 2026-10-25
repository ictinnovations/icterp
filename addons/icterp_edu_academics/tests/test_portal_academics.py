from datetime import date

from odoo.tests.common import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestAcademicsPortal(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        portal = env.ref("base.group_portal")
        year = env["op.academic.year"].create({"name": "PY 2026", "start_date": date(2026, 1, 1), "end_date": date(2026, 12, 31)})
        cls.term = env["op.academic.term"].create({"name": "Fall P", "term_start_date": date(2026, 9, 1),
                                                   "term_end_date": date(2026, 12, 31), "academic_year_id": year.id})
        course = env["op.course"].create({"name": "BBA P", "code": "BBAP"})
        batch = env["op.batch"].create({"name": "BBA 26", "code": "BBA26P", "course_id": course.id,
                                        "start_date": date(2026, 9, 1), "end_date": date(2030, 6, 30)})
        subject = env["op.subject"].create({"name": "Principles of Accounting", "code": "AC101P", "credit_hours": 3})

        def student(first, login):
            s = env["op.student"].create({"first_name": first, "last_name": "P", "name": first + " P", "gender": "f",
                                          "birth_date": date(2006, 1, 1), "email": login})
            env["op.student.course"].create({"student_id": s.id, "course_id": course.id, "batch_id": batch.id})
            s.user_id = env["res.users"].create({"name": s.name, "login": login, "password": login,
                                                 "partner_id": s.partner_id.id, "group_ids": [(6, 0, portal.ids)]})
            return s

        cls.ayesha = student("Ayesha", "ayesha.p@example.com")
        cls.other = student("Sana", "sana.p@example.com")
        o = env["icterp.course.offering"].create({"term_id": cls.term.id, "course_id": course.id, "batch_id": batch.id,
                                                  "subject_id": subject.id})
        o.action_open()
        comp = env["icterp.assessment.component"].create({"offering_id": o.id, "name": "Final", "max_marks": 100, "weight": 100})
        for s, m in ((cls.ayesha, 88), (cls.other, 60)):
            e = env["icterp.enrollment"].create({"student_id": s.id, "offering_id": o.id})
            env["icterp.assessment.mark"].create({"component_id": comp.id, "enrollment_id": e.id, "marks": m})
        o.action_verify()
        o.action_publish()

    def test_student_sees_gpa_and_transcript(self):
        self.authenticate("ayesha.p@example.com", "ayesha.p@example.com")
        page = self.url_open("/my/education/%s" % self.ayesha.id)
        self.assertEqual(page.status_code, 200)
        self.assertIn("Courses and GPA", page.text)
        self.assertIn("4.00", page.text)
        r = self.url_open("/my/education/%s/transcript" % self.ayesha.id)
        self.assertEqual(r.status_code, 200)
        self.assertIn("pdf", r.headers.get("Content-Type", "") + r.headers.get("Content-Disposition", ""))

    def test_no_transcript_of_someone_else(self):
        self.authenticate("ayesha.p@example.com", "ayesha.p@example.com")
        r = self.url_open("/my/education/%s/transcript" % self.other.id, allow_redirects=False)
        self.assertEqual(r.status_code, 404)
