from odoo.exceptions import ValidationError
from odoo.tests.common import tagged

from odoo.addons.icterp_edu_academics.tests.common import AcademicsCase


@tagged("post_install", "-at_install")
class TestObe(AcademicsCase):

    def setUp(self):
        super().setUp()
        env = self.env
        self.s3 = self._student("Rida", "Asif", "rida.t@example.com")
        self.plo1 = env["icterp.obe.plo"].create({"course_id": self.course.id, "code": "PLO1", "name": "Engineering knowledge"})
        self.plo2 = env["icterp.obe.plo"].create({"course_id": self.course.id, "code": "PLO2", "name": "Problem analysis"})
        self.clo1 = env["icterp.obe.clo"].create({"subject_id": self.calc.id, "code": "CLO1", "description": "Apply limits",
                                                  "level": "C3", "plo_ids": [(6, 0, self.plo1.ids)]})
        self.clo2 = env["icterp.obe.clo"].create({"subject_id": self.calc.id, "code": "CLO2", "description": "Analyse functions",
                                                  "level": "C4", "plo_ids": [(6, 0, self.plo2.ids)]})
        self.o = self.offering(self.calc)
        Comp = env["icterp.assessment.component"]
        self.quiz = Comp.create({"offering_id": self.o.id, "name": "Quiz", "max_marks": 10, "weight": 20, "clo_id": self.clo1.id})
        self.final = Comp.create({"offering_id": self.o.id, "name": "Final", "max_marks": 20, "weight": 80,
                                  "question_ids": [(0, 0, {"name": "Q1", "max_marks": 8, "clo_id": self.clo1.id, "external_ref": "ix-1"}),
                                                   (0, 0, {"name": "Q2", "max_marks": 12, "clo_id": self.clo2.id, "external_ref": "ix-2"})]})
        for s in (self.s1, self.s2, self.s3):
            self.enroll(s, self.o)
        self.quiz.import_marks([{"student_id": self.s1.id, "marks": 9}, {"student_id": self.s2.id, "marks": 2},
                                {"student_id": self.s3.id, "marks": 8}])
        # per-question marks arrive the way ICTExam will send them
        self.final.import_marks([
            {"email": "hamza.t@example.com", "questions": {"ix-1": 6, "ix-2": 3}},
            {"email": "iqra.t@example.com", "questions": {"ix-1": 2, "ix-2": 10}},
            {"email": "rida.t@example.com", "questions": {"ix-1": 7, "ix-2": 9}},
        ], source="ictexam")

    def test_student_and_class_clo_attainment(self):
        self.o.action_compute_clo_attainment()
        sc = self.env["icterp.obe.student.clo"]
        s1c1 = sc.search([("student_id", "=", self.s1.id), ("clo_id", "=", self.clo1.id)])
        self.assertAlmostEqual(s1c1.percent, round(100 * 15 / 18, 2))
        self.assertTrue(s1c1.attained)
        s1c2 = sc.search([("student_id", "=", self.s1.id), ("clo_id", "=", self.clo2.id)])
        self.assertAlmostEqual(s1c2.percent, 25.0)
        self.assertFalse(s1c2.attained)
        cls1 = self.o.clo_attainment_ids.filtered(lambda r: r.clo_id == self.clo1)
        self.assertEqual((cls1.students_assessed, cls1.students_attained), (3, 2))  # s1, s3
        self.assertAlmostEqual(cls1.percent_attained, 66.7)
        self.assertTrue(cls1.attained)
        self.assertEqual(cls1.plo_codes, "PLO1")

    def test_class_threshold_setting(self):
        self.env["ir.config_parameter"].sudo().set_param("icterp_edu_obe.class_threshold", "70")
        self.o.action_compute_clo_attainment()
        cls1 = self.o.clo_attainment_ids.filtered(lambda r: r.clo_id == self.clo1)
        self.assertFalse(cls1.attained)  # 66.7% < 70%

    def test_absent_counts_zero(self):
        mark = self.env["icterp.assessment.mark"].search([("component_id", "=", self.final.id), ("student_id", "=", self.s3.id)])
        mark.absent = True
        self.o.action_compute_clo_attainment()
        r = self.env["icterp.obe.student.clo"].search([("student_id", "=", self.s3.id), ("clo_id", "=", self.clo2.id)])
        self.assertEqual(r.percent, 0.0)

    def test_plo_attainment(self):
        wiz = self.env["icterp.obe.plo.compute"].create({"course_id": self.course.id})
        wiz.action_compute()
        plo = self.env["icterp.obe.student.plo"]
        s1p1 = plo.search([("student_id", "=", self.s1.id), ("plo_id", "=", self.plo1.id)])
        s1p2 = plo.search([("student_id", "=", self.s1.id), ("plo_id", "=", self.plo2.id)])
        self.assertTrue(s1p1.attained)
        self.assertFalse(s1p2.attained)
        self.assertAlmostEqual(s1p2.percent, 25.0)
        self.assertIn("3 students", wiz.result_note)

    def test_clo_must_belong_to_subject(self):
        other = self.env["icterp.obe.clo"].create({"subject_id": self.prog1.id, "code": "CLO1", "description": "x", "level": "C1"})
        with self.assertRaises(ValidationError):
            self.final.question_ids[0].clo_id = other

    def test_report_renders(self):
        self.o.action_compute_clo_attainment()
        html = self.env["ir.actions.report"]._render_qweb_html("icterp_edu_obe.action_report_clo", self.o.ids)[0]
        html = html.decode() if isinstance(html, bytes) else html
        self.assertIn("Apply limits", html)
        self.assertIn("Attained", html)
