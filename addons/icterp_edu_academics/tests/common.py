from datetime import date

from odoo.tests.common import TransactionCase


class AcademicsCase(TransactionCase):
    """A small university: two terms, a BSCS course with a 21 credit-hour limit, three subjects."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.year = env["op.academic.year"].create({"name": "2026-27 T", "start_date": date(2026, 1, 1), "end_date": date(2027, 12, 31)})
        cls.term1 = env["op.academic.term"].create({"name": "Fall 2026 T", "term_start_date": date(2026, 9, 1),
                                                    "term_end_date": date(2026, 12, 31), "academic_year_id": cls.year.id})
        cls.term2 = env["op.academic.term"].create({"name": "Spring 2027 T", "term_start_date": date(2027, 1, 15),
                                                    "term_end_date": date(2027, 5, 31), "academic_year_id": cls.year.id})
        cls.course = env["op.course"].create({"name": "BS Computer Science T", "code": "BSCST", "max_unit_load": 21})
        cls.batch = env["op.batch"].create({"name": "BSCS 26", "code": "BSCS26T", "course_id": cls.course.id,
                                            "start_date": date(2026, 9, 1), "end_date": date(2030, 6, 30)})
        cls.prog1 = env["op.subject"].create({"name": "Programming Fundamentals", "code": "CS101T", "credit_hours": 4})
        cls.oop = env["op.subject"].create({"name": "Object Oriented Programming", "code": "CS102T", "credit_hours": 4,
                                            "prerequisite_ids": [(6, 0, cls.prog1.ids)]})
        cls.calc = env["op.subject"].create({"name": "Calculus", "code": "MT101T", "credit_hours": 3})
        cls.s1 = cls._student("Hamza", "Ali", "hamza.t@example.com")
        cls.s2 = cls._student("Iqra", "Noor", "iqra.t@example.com")

    @classmethod
    def _student(cls, first, last, email):
        s = cls.env["op.student"].create({"first_name": first, "last_name": last, "name": "%s %s" % (first, last),
                                          "gender": "m", "birth_date": date(2006, 1, 1), "email": email})
        cls.env["op.student.course"].create({"student_id": s.id, "course_id": cls.course.id, "batch_id": cls.batch.id,
                                             "roll_number": "R-" + first})
        return s

    def offering(self, subject, term=None, **kw):
        vals = {"term_id": (term or self.term1).id, "course_id": self.course.id, "batch_id": self.batch.id,
                "subject_id": subject.id, "section": kw.pop("section", "A")}
        vals.update(kw)
        o = self.env["icterp.course.offering"].create(vals)
        o.action_open()
        return o

    def components(self, offering, spec=(("Quiz", 10, 20), ("Midterm", 30, 30), ("Final", 50, 50))):
        Comp = self.env["icterp.assessment.component"]
        return [Comp.create({"offering_id": offering.id, "name": n, "max_marks": m, "weight": w}) for n, m, w in spec]

    def enroll(self, student, offering):
        return self.env["icterp.enrollment"].create({"student_id": student.id, "offering_id": offering.id})

    def give(self, enrollment, comps, marks):
        Mark = self.env["icterp.assessment.mark"]
        for comp, m in zip(comps, marks):
            Mark.create({"component_id": comp.id, "enrollment_id": enrollment.id, "marks": m})

    def publish(self, offering):
        offering.action_verify()
        offering.action_publish()
