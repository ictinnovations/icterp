import re
from datetime import date, datetime, timedelta

from odoo.tests.common import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestEducationPortal(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        portal = env.ref("base.group_portal")
        cls.course = env["op.course"].create({"name": "Grade 8", "code": "G8P"})
        cls.batch = env["op.batch"].create({"name": "G8 A", "code": "G8AP", "course_id": cls.course.id,
                                            "start_date": date(2026, 9, 1), "end_date": date(2027, 6, 30)})

        def student(first, last, login):
            s = env["op.student"].create({"first_name": first, "last_name": last, "name": "%s %s" % (first, last),
                                          "gender": "f", "birth_date": date(2013, 5, 5), "email": login})
            env["op.student.course"].create({"student_id": s.id, "course_id": cls.course.id, "batch_id": cls.batch.id})
            s.user_id = env["res.users"].create({"name": s.name, "login": login, "password": login,
                                                 "partner_id": s.partner_id.id, "group_ids": [(6, 0, portal.ids)]})
            return s

        cls.amna = student("Amna", "Khan", "amna.portal@example.com")
        cls.zoya = student("Zoya", "Malik", "zoya.portal@example.com")
        rel = env["op.parent.relationship"].search([], limit=1) or env["op.parent.relationship"].create({"name": "Mother"})
        mum = env["res.partner"].create({"name": "Sana Khan", "email": "sana.portal@example.com"})
        cls.parent = env["op.parent"].create({"name": mum.id, "student_ids": [(6, 0, cls.amna.ids)], "relationship_id": rel.id})
        cls.parent.user_id = env["res.users"].create({"name": "Sana Khan", "login": "sana.portal@example.com",
                                                      "password": "sana.portal@example.com", "partner_id": mum.id,
                                                      "group_ids": [(6, 0, portal.ids)]})

        faculty = env["op.faculty"].create({"first_name": "Bilal", "last_name": "Ahmed", "name": "Bilal Ahmed",
                                            "birth_date": date(1985, 1, 1), "gender": "male"})
        atype = env["grading.assignment.type"].create({"name": "Homework", "code": "HWP"})
        cls.assignment = env["op.assignment"].create({
            "name": "Essay on rivers", "course_id": cls.course.id, "batch_id": cls.batch.id,
            "issued_date": datetime.now(), "submission_date": datetime.now() + timedelta(days=7),
            "assignment_type": atype.id, "faculty_id": faculty.id, "description": "Write 300 words.",
            "allocation_ids": [(6, 0, (cls.amna | cls.zoya).ids)], "state": "publish",
        })

    def _get(self, url):
        return self.url_open(url, allow_redirects=False)

    def _csrf(self):
        page = self.url_open("/my/education/%s" % self.amna.id).text
        m = (re.search(r'name="csrf_token" value="([^"]+)"', page)
             or re.search(r"""csrf_token["']?\s*:\s*["']([^"']+)""", page))
        self.assertTrue(m, "no CSRF token on the page")
        return m.group(1)

    def test_student_lands_on_own_page(self):
        self.authenticate("amna.portal@example.com", "amna.portal@example.com")
        r = self._get("/my/education")
        self.assertIn(r.status_code, (302, 303))
        self.assertTrue(r.headers["Location"].endswith("/my/education/%s" % self.amna.id))
        page = self.url_open("/my/education/%s" % self.amna.id)
        self.assertEqual(page.status_code, 200)
        self.assertIn("Amna Khan", page.text)
        self.assertIn("Essay on rivers", page.text)
        self.assertIn("Hand in", page.text)

    def test_student_cannot_open_another_student(self):
        self.authenticate("amna.portal@example.com", "amna.portal@example.com")
        self.assertEqual(self._get("/my/education/%s" % self.zoya.id).status_code, 404)

    def test_parent_sees_child_only(self):
        self.authenticate("sana.portal@example.com", "sana.portal@example.com")
        page = self.url_open("/my/education/%s" % self.amna.id)
        self.assertEqual(page.status_code, 200)
        self.assertIn("Amna Khan", page.text)
        self.assertNotIn("Hand in", page.text)  # parents read, students hand in
        self.assertEqual(self._get("/my/education/%s" % self.zoya.id).status_code, 404)

    def test_student_hands_in_assignment(self):
        self.authenticate("amna.portal@example.com", "amna.portal@example.com")
        url = "/my/education/%s/assignment/%s/submit" % (self.amna.id, self.assignment.id)
        r = self.url_open(url, data={"answer": "Rivers carry water to the sea.", "csrf_token": self._csrf()},
                          allow_redirects=False)
        self.assertIn(r.status_code, (302, 303))
        sub = self.env["op.assignment.sub.line"].search([("assignment_id", "=", self.assignment.id),
                                                         ("student_id", "=", self.amna.id)])
        self.assertEqual(sub.state, "submit")
        self.assertEqual(sub.description, "Rivers carry water to the sea.")

    def test_parent_cannot_hand_in(self):
        self.authenticate("sana.portal@example.com", "sana.portal@example.com")
        url = "/my/education/%s/assignment/%s/submit" % (self.amna.id, self.assignment.id)
        r = self.url_open(url, data={"answer": "x", "csrf_token": self._csrf()}, allow_redirects=False)
        self.assertEqual(r.status_code, 404)
        self.assertFalse(self.env["op.assignment.sub.line"].search([("assignment_id", "=", self.assignment.id)]))

    def test_cannot_hand_in_for_classmate(self):
        self.authenticate("amna.portal@example.com", "amna.portal@example.com")
        url = "/my/education/%s/assignment/%s/submit" % (self.zoya.id, self.assignment.id)
        r = self.url_open(url, data={"answer": "x", "csrf_token": self._csrf()}, allow_redirects=False)
        self.assertEqual(r.status_code, 404)

    def test_public_user_redirected_to_login(self):
        r = self._get("/my/education/%s" % self.amna.id)
        self.assertIn(r.status_code, (302, 303))
        self.assertIn("/web/login", r.headers["Location"])
