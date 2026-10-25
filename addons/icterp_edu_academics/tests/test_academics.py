from datetime import date

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import tagged

from .common import AcademicsCase


@tagged("post_install", "-at_install")
class TestGrades(AcademicsCase):

    def test_percentage_letter_and_points(self):
        o = self.offering(self.prog1)
        comps = self.components(o)
        e = self.enroll(self.s1, o)
        self.give(e, comps, [8, 24, 41])  # 16 + 24 + 41 = 81%
        self.assertAlmostEqual(e.percentage, 81.0)
        self.assertEqual(e.grade_letter, "A-")
        self.assertAlmostEqual(e.grade_points, 3.67)
        self.assertTrue(e.is_pass)

    def test_absent_counts_zero_and_fail(self):
        o = self.offering(self.calc)
        comps = self.components(o)
        e = self.enroll(self.s1, o)
        self.give(e, comps, [5, 12, 0])
        self.env["icterp.assessment.mark"].search([("enrollment_id", "=", e.id), ("component_id", "=", comps[2].id)]).absent = True
        self.assertAlmostEqual(e.percentage, 22.0)
        self.assertEqual(e.grade_letter, "F")
        self.assertFalse(e.is_pass)

    def test_verify_needs_weights_100_and_all_marks(self):
        o = self.offering(self.calc)
        comps = self.components(o, (("Quiz", 10, 20), ("Final", 50, 50)))
        e = self.enroll(self.s1, o)
        self.give(e, comps, [5, 25])
        with self.assertRaises(UserError):
            o.action_verify()  # weights total 70
        comps[1].weight = 80
        e2 = self.enroll(self.s2, o)
        with self.assertRaises(UserError):
            o.action_verify()  # s2 has no marks
        self.give(e2, comps, [6, 30])
        o.action_verify()
        self.assertEqual(o.state, "verified")

    def test_marks_locked_after_verify(self):
        o = self.offering(self.calc)
        comps = self.components(o)
        e = self.enroll(self.s1, o)
        self.give(e, comps, [5, 15, 25])
        o.action_verify()
        mark = e.mark_ids[:1]
        with self.assertRaises(UserError):
            mark.write({"marks": 9})

    def test_marks_out_of_range_rejected(self):
        o = self.offering(self.calc)
        comps = self.components(o)
        e = self.enroll(self.s1, o)
        with self.assertRaises(ValidationError):
            self.give(e, comps[:1], [11])


@tagged("post_install", "-at_install")
class TestRegistrationRules(AcademicsCase):

    def test_prerequisite_blocks_then_allows(self):
        o_oop = self.offering(self.oop, term=self.term2)
        with self.assertRaises(ValidationError):
            self.enroll(self.s1, o_oop)
        o1 = self.offering(self.prog1)
        comps = self.components(o1)
        e = self.enroll(self.s1, o1)
        self.give(e, comps, [7, 20, 30])  # 14+20+30 = 64 -> C+ pass
        self.publish(o1)
        self.assertTrue(self.enroll(self.s1, o_oop))

    def test_capacity(self):
        o = self.offering(self.calc, capacity=1)
        self.enroll(self.s1, o)
        with self.assertRaises(ValidationError):
            self.enroll(self.s2, o)

    def test_credit_load_limit(self):
        self.course.max_unit_load = 6
        o1 = self.offering(self.prog1)
        self.enroll(self.s1, o1)  # 4
        o2 = self.offering(self.calc)
        with self.assertRaises(ValidationError):
            self.enroll(self.s1, o2)  # 4 + 3 > 6

    def test_same_subject_twice_in_a_term(self):
        a = self.offering(self.calc, section="A")
        b = self.offering(self.calc, section="B")
        self.enroll(self.s1, a)
        with self.assertRaises(ValidationError):
            self.enroll(self.s1, b)

    def test_closed_offering(self):
        o = self.env["icterp.course.offering"].create({"term_id": self.term1.id, "course_id": self.course.id,
                                                       "batch_id": self.batch.id, "subject_id": self.calc.id})
        with self.assertRaises(ValidationError):
            self.enroll(self.s1, o)

    def test_drop_and_withdraw(self):
        o = self.offering(self.calc)
        e1 = self.enroll(self.s1, o)
        e2 = self.enroll(self.s2, o)
        e1.action_drop()
        self.assertEqual(e1.state, "dropped")
        e2.action_withdraw()
        self.assertEqual(e2.grade_letter, "W")
        self.assertEqual(e2.quality_points, 0)
        self.assertEqual(o.enrolled_count, 0)

    def test_drop_deadline_for_non_managers(self):
        self.term1.drop_deadline = date(2000, 1, 1)
        o = self.offering(self.calc)
        e = self.enroll(self.s1, o)
        faculty_user = self.env["res.users"].create({
            "name": "Teacher T", "login": "teacher.t@example.com",
            "group_ids": [(6, 0, [self.env.ref("openeducat_core.group_op_faculty").id, self.env.ref("base.group_user").id])]})
        with self.assertRaises(UserError):
            e.with_user(faculty_user).action_drop()

    def test_bulk_enroll_reports_problems(self):
        o = self.offering(self.oop)  # nobody passed the prerequisite
        wiz = self.env["icterp.bulk.enroll"].with_context(default_offering_id=o.id).create({"offering_id": o.id})
        self.assertIn(self.s1, wiz.student_ids)
        wiz.action_enroll()
        self.assertIn("0 enrolled", wiz.result_note)
        self.assertIn("prerequisite", wiz.result_note)


@tagged("post_install", "-at_install")
class TestGpa(AcademicsCase):

    def _complete(self, student, subject, term, marks):
        o = self.env["icterp.course.offering"].search([("term_id", "=", term.id), ("subject_id", "=", subject.id)], limit=1) \
            or self.offering(subject, term=term)
        if o.state != "open":
            o.state = "open"
        comps = o.component_ids or self.components(o)
        e = self.enroll(student, o)
        self.give(e, comps, marks)
        return o, e

    def test_term_gpa_and_cgpa_with_repeat(self):
        o1, _e = self._complete(self.s1, self.prog1, self.term1, [2, 10, 20])  # 4+10+20=34 F (4 cr)
        o2, _e = self._complete(self.s1, self.calc, self.term1, [10, 30, 46])  # 20+30+46=96 A (3 cr)
        self.publish(o1)
        self.publish(o2)
        r1 = self.env["icterp.term.result"].search([("student_id", "=", self.s1.id), ("term_id", "=", self.term1.id)])
        self.assertAlmostEqual(r1.gpa, round((0 * 4 + 4.0 * 3) / 7, 2))
        self.assertEqual(r1.credits_earned, 3)
        # repeat Programming in term 2 and get an A: only the latest attempt counts in the CGPA
        o3, _e = self._complete(self.s1, self.prog1, self.term2, [10, 30, 45])
        self.publish(o3)
        r2 = self.env["icterp.term.result"].search([("student_id", "=", self.s1.id), ("term_id", "=", self.term2.id)])
        self.assertAlmostEqual(r2.gpa, 4.0)
        self.assertAlmostEqual(r2.cgpa, 4.0)
        self.assertAlmostEqual(r2.cumulative_credits, 7)
        self.assertAlmostEqual(self.s1.cgpa, 4.0)

    def test_probation_then_suspension(self):
        o1, _e = self._complete(self.s2, self.calc, self.term1, [5, 15, 30])  # 10+15+30=55 D+ 1.33
        self.publish(o1)
        r1 = self.env["icterp.term.result"].search([("student_id", "=", self.s2.id), ("term_id", "=", self.term1.id)])
        self.assertEqual(r1.standing, "probation")
        o2, _e = self._complete(self.s2, self.prog1, self.term2, [5, 15, 30])
        self.publish(o2)
        r2 = self.env["icterp.term.result"].search([("student_id", "=", self.s2.id), ("term_id", "=", self.term2.id)])
        self.assertEqual(r2.standing, "suspension")

    def test_unpublish_removes_term_result(self):
        o, _e = self._complete(self.s1, self.calc, self.term1, [10, 30, 46])
        self.publish(o)
        self.assertTrue(self.env["icterp.term.result"].search([("student_id", "=", self.s1.id)]))
        o.action_revert()
        self.assertFalse(self.env["icterp.term.result"].search([("student_id", "=", self.s1.id)]))

    def test_grade_change(self):
        o, e = self._complete(self.s1, self.calc, self.term1, [5, 15, 30])  # 55 D+
        self.publish(o)
        a_band = o.grade_scale_id.line_ids.filtered(lambda l: l.letter == "B")
        self.env["icterp.grade.change"].create({"enrollment_id": e.id, "new_band_id": a_band.id,
                                                "reason": "Recount approved"}).action_apply()
        self.assertEqual(e.grade_letter, "B")
        r = self.env["icterp.term.result"].search([("student_id", "=", self.s1.id), ("term_id", "=", self.term1.id)])
        self.assertAlmostEqual(r.gpa, 3.0)
        self.assertIn("Recount approved", e.message_ids[:1].body)

    def test_transcript_renders(self):
        o, _e = self._complete(self.s1, self.calc, self.term1, [10, 30, 46])
        self.publish(o)
        html = self.env["ir.actions.report"]._render_qweb_html("icterp_edu_academics.action_report_transcript", self.s1.ids)[0]
        html = html.decode() if isinstance(html, bytes) else html
        self.assertIn("Calculus", html)
        self.assertIn("4.00", html)


@tagged("post_install", "-at_install")
class TestImportMarks(AcademicsCase):
    """The entry point ICTExam will use."""

    def test_import_by_email_and_roll_number(self):
        o = self.offering(self.calc)
        comps = self.components(o)
        self.enroll(self.s1, o)
        self.enroll(self.s2, o)
        res = comps[2].import_marks([
            {"email": "hamza.t@example.com", "marks": 40, "external_ref": "attempt-1"},
            {"roll_number": "R-Iqra", "marks": 35},
            {"email": "nobody@example.com", "marks": 50},
        ], source="ictexam", external_ref="ictexam-final-77")
        self.assertEqual(res["created"], 2)
        self.assertEqual(len(res["unmatched"]), 1)
        self.assertEqual(comps[2].source, "ictexam")
        self.assertEqual(comps[2].external_ref, "ictexam-final-77")
        # re-import updates, does not duplicate
        res = comps[2].import_marks([{"email": "hamza.t@example.com", "marks": 44}], source="ictexam")
        self.assertEqual(res["updated"], 1)
        marks = self.env["icterp.assessment.mark"].search([("component_id", "=", comps[2].id)])
        self.assertEqual(len(marks), 2)
        self.assertEqual(marks.filtered(lambda m: m.student_id == self.s1).marks, 44)

    def test_import_question_marks(self):
        o = self.offering(self.calc)
        comp = self.env["icterp.assessment.component"].create({
            "offering_id": o.id, "name": "Final", "max_marks": 20, "weight": 100,
            "question_ids": [(0, 0, {"name": "Q1", "max_marks": 8, "external_ref": "q-11"}),
                             (0, 0, {"name": "Q2", "max_marks": 12})]})
        self.enroll(self.s1, o)
        comp.import_marks([{"student_id": self.s1.id, "questions": {"q-11": 6, "Q2": 10}}], source="ictexam")
        mark = self.env["icterp.assessment.mark"].search([("component_id", "=", comp.id)])
        self.assertEqual(mark.marks, 16)
        self.assertEqual(len(mark.question_mark_ids), 2)

    def test_import_refused_when_locked(self):
        o = self.offering(self.calc)
        comps = self.components(o)
        e = self.enroll(self.s1, o)
        self.give(e, comps, [5, 15, 25])
        o.action_verify()
        with self.assertRaises(UserError):
            comps[0].import_marks([{"student_id": self.s1.id, "marks": 9}])


@tagged("post_install", "-at_install")
class TestFacultyRules(AcademicsCase):

    def test_teacher_marks_only_own_course(self):
        group = self.env.ref("openeducat_core.group_op_faculty")
        t1 = self.env["res.users"].create({"name": "T One", "login": "t.one@example.com", "group_ids": [(6, 0, [group.id])]})
        t2 = self.env["res.users"].create({"name": "T Two", "login": "t.two@example.com", "group_ids": [(6, 0, [group.id])]})
        f1 = self.env["op.faculty"].create({"first_name": "T", "last_name": "One", "name": "T One",
                                            "birth_date": date(1980, 1, 1), "gender": "male"})
        f1.partner_id.user_id = t1
        o = self.offering(self.calc, faculty_id=f1.id)
        self.assertEqual(o.faculty_user_id, t1)
        comps = self.components(o)
        e = self.enroll(self.s1, o)
        self.env["icterp.assessment.mark"].with_user(t1).create({"component_id": comps[0].id, "enrollment_id": e.id, "marks": 7})
        with self.assertRaises(AccessError):
            self.env["icterp.assessment.mark"].with_user(t2).create({"component_id": comps[1].id, "enrollment_id": e.id, "marks": 20})
