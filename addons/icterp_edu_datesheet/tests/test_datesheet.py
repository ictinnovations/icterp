from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import HttpCase, tagged

from odoo.addons.icterp_edu_academics.tests.common import AcademicsCase


class DatesheetCase(AcademicsCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.s3 = cls._student("Usman", "Tariq", "usman.t@example.com")
        cls.s4 = cls._student("Maham", "Riaz", "maham.t@example.com")
        cls.s5 = cls._student("Saad", "Iqbal", "saad.t@example.com")
        cls.r1 = env["op.classroom"].create({"name": "Hall A", "code": "HA", "capacity": 3})
        cls.r2 = env["op.classroom"].create({"name": "Hall B", "code": "HB", "capacity": 3})
        cls.teachers = env["op.faculty"].browse()
        for i in range(3):
            cls.teachers |= env["op.faculty"].create({"first_name": "Inv%s" % i, "last_name": "T", "name": "Inv%s T" % i,
                                                      "birth_date": date(1980, 1, 1), "gender": "male"})

    def setUp(self):
        super().setUp()
        self.o_calc = self.offering(self.calc)
        self.o_prog = self.offering(self.prog1)
        for s in (self.s1, self.s2, self.s3):
            self.enroll(s, self.o_calc)
        for s in (self.s4, self.s5):
            self.enroll(s, self.o_prog)
        self.sched = self.env["icterp.exam.schedule"].create({"name": "Fall finals T", "term_id": self.term1.id})

    def paper(self, offering, day=date(2026, 12, 10), start=9.0, rooms=None):
        return self.env["icterp.exam.paper"].create({"schedule_id": self.sched.id, "offering_id": offering.id, "date": day,
                                                     "start_time": start, "duration": 3.0,
                                                     "room_ids": [(6, 0, (rooms or self.r1 | self.r2).ids)]})


@tagged("post_install", "-at_install")
class TestDatesheet(DatesheetCase):

    def test_student_clash_and_missing_room(self):
        self.enroll(self.s1, self.o_prog)  # s1 now sits both papers
        self.paper(self.o_calc)
        p2 = self.paper(self.o_prog, start=10.0)
        p2.room_ids = [(5, 0, 0)]
        self.sched.action_check_clashes()
        self.assertIn("Hamza Ali sits", self.sched.clash_report)
        self.assertIn("has no room", self.sched.clash_report)
        with self.assertRaises(UserError):
            self.sched.action_publish()

    def test_no_clash_on_different_days(self):
        self.enroll(self.s1, self.o_prog)
        self.paper(self.o_calc)
        self.paper(self.o_prog, day=date(2026, 12, 11))
        self.sched.action_check_clashes()
        self.assertEqual(self.sched.clash_count, 0)
        self.sched.action_publish()
        self.assertEqual(self.sched.state, "published")

    def test_seating_mixes_papers_and_respects_capacity(self):
        self.paper(self.o_calc)
        self.paper(self.o_prog)
        self.sched.action_generate_seating()
        seats = self.sched.seat_ids.sorted("seat_no")
        self.assertEqual(len(seats), 5)
        hall_a = seats.filtered(lambda s: s.room_id == self.r1).sorted("seat_no")
        self.assertEqual(len(hall_a), 3)
        self.assertNotEqual(hall_a[0].paper_id, hall_a[1].paper_id)  # neighbours sit different papers
        self.assertEqual(len(seats.mapped("student_id")), 5)

    def test_seating_too_few_seats(self):
        self.paper(self.o_calc, rooms=self.r1)
        self.paper(self.o_prog, rooms=self.r1)  # 5 students, 3 seats
        with self.assertRaises(UserError):
            self.sched.action_generate_seating()

    def test_invigilators_one_per_room_no_double_booking(self):
        self.paper(self.o_calc)
        self.paper(self.o_prog)
        self.sched.action_generate_seating()
        self.sched.action_assign_invigilators()
        duties = self.sched.duty_ids
        self.assertEqual(len(duties), 2)
        self.assertEqual(len(duties.mapped("faculty_id")), 2)
        self.sched.action_check_clashes()
        self.assertEqual(self.sched.clash_count, 0)

    def test_slip_lists_seat(self):
        self.paper(self.o_calc)
        self.sched.action_generate_seating()
        html = self.env["ir.actions.report"]._render_qweb_html("icterp_edu_datesheet.action_report_slip", self.sched.ids,
                                                               data={"student_ids": self.s1.ids})[0]
        html = html.decode() if isinstance(html, bytes) else html
        seat = self.sched.seat_ids.filtered(lambda s: s.student_id == self.s1)
        self.assertIn(seat.seat_no, html)
        self.assertIn("Calculus", html)
        self.assertNotIn("Usman", html)


@tagged("post_install", "-at_install")
class TestDatesheetPortal(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        portal = env.ref("base.group_portal")
        year = env["op.academic.year"].create({"name": "DS 2026", "start_date": date(2026, 1, 1), "end_date": date(2026, 12, 31)})
        term = env["op.academic.term"].create({"name": "Fall DS", "term_start_date": date(2026, 9, 1),
                                               "term_end_date": date(2026, 12, 31), "academic_year_id": year.id})
        course = env["op.course"].create({"name": "BSDS", "code": "BSDSP"})
        batch = env["op.batch"].create({"name": "DS 26", "code": "DS26P", "course_id": course.id,
                                        "start_date": date(2026, 9, 1), "end_date": date(2030, 6, 30)})
        subject = env["op.subject"].create({"name": "Statistics", "code": "ST101P"})
        o = env["icterp.course.offering"].create({"term_id": term.id, "course_id": course.id, "batch_id": batch.id, "subject_id": subject.id})
        o.action_open()

        def student(first, login, enrol=True):
            s = env["op.student"].create({"first_name": first, "last_name": "D", "name": first + " D", "gender": "m",
                                          "birth_date": date(2006, 1, 1), "email": login})
            s.user_id = env["res.users"].create({"name": s.name, "login": login, "password": login,
                                                 "partner_id": s.partner_id.id, "group_ids": [(6, 0, portal.ids)]})
            if enrol:
                env["icterp.enrollment"].create({"student_id": s.id, "offering_id": o.id})
            return s

        cls.omar = student("Omar", "omar.ds@example.com")
        cls.nida = student("Nida", "nida.ds@example.com", enrol=False)
        room = env["op.classroom"].create({"name": "Room 9", "code": "R9", "capacity": 10})
        cls.sched = env["icterp.exam.schedule"].create({"name": "Fall DS finals", "term_id": term.id})
        env["icterp.exam.paper"].create({"schedule_id": cls.sched.id, "offering_id": o.id, "date": date(2026, 12, 12),
                                         "start_time": 9.0, "duration": 2.0, "room_ids": [(6, 0, room.ids)]})
        cls.sched.action_generate_seating()
        cls.sched.action_publish()

    def test_student_sees_paper_and_slip(self):
        self.authenticate("omar.ds@example.com", "omar.ds@example.com")
        page = self.url_open("/my/education/%s" % self.omar.id)
        self.assertIn("Exam schedule", page.text)
        self.assertIn("R9-01", page.text)
        r = self.url_open("/my/education/%s/exam-slip/%s" % (self.omar.id, self.sched.id))
        self.assertEqual(r.status_code, 200)

    def test_cannot_get_slip_for_unrelated_schedule(self):
        self.authenticate("nida.ds@example.com", "nida.ds@example.com")
        r = self.url_open("/my/education/%s/exam-slip/%s" % (self.nida.id, self.sched.id), allow_redirects=False)
        self.assertEqual(r.status_code, 404)
        r = self.url_open("/my/education/%s/exam-slip/%s" % (self.omar.id, self.sched.id), allow_redirects=False)
        self.assertEqual(r.status_code, 404)
