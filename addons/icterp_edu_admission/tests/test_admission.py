from datetime import date, timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import HttpCase, TransactionCase, tagged


def _register(env, **kw):
    tag = str(env["op.course"].search_count([]) + 1)
    course = env["op.course"].create({"name": "BS Software Engineering " + tag, "code": "BSSE" + tag})
    today = fields.Date.today()
    vals = {"name": "BSSE Fall A", "course_id": course.id, "start_date": today - timedelta(days=10),
            "end_date": today + timedelta(days=20), "min_count": 1, "max_count": 2, "waiting_count": 1, "state": "application",
            "online": True, "weight_matric": 10, "weight_inter": 40, "weight_test": 50, "hafiz_bonus": 2,
            "admission_fee": 15000, "minimum_age_criteria": 10}
    vals.update(kw)
    return env["op.admission.register"].create(vals)


def _apply(env, reg, first, matric, inter, email=None, hafiz=False):
    a = env["op.admission"].create({
        "register_id": reg.id, "course_id": reg.course_id.id, "first_name": first, "last_name": "A", "name": first + " A",
        "email": email or "%s.adm@example.com" % first.lower(), "gender": "m", "birth_date": date(2007, 1, 1),
        "application_date": fields.Datetime.now(), "matric_obtained": matric, "inter_obtained": inter, "hafiz": hafiz})
    a.submit_form()
    return a


@tagged("post_install", "-at_install")
class TestMerit(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        income = env["account.account"].search([("account_type", "=", "income")], limit=1)
        env.ref("icterp_edu_admission.product_admission_fee").property_account_income_id = income
        cls.reg = _register(env)
        cls.test = env["icterp.entry.test"].create({"name": "ET A", "register_id": cls.reg.id, "date": fields.Date.today() + timedelta(days=5),
                                                    "total_marks": 100})
        cls.room = env["op.classroom"].create({"name": "Test Hall", "code": "TH", "capacity": 3})
        cls.test.room_ids = cls.room

    def test_aggregate_and_hafiz_bonus(self):
        a = _apply(self.env, self.reg, "Ahmed", 990, 880)  # 90%, 80%
        a.write({"entry_test_id": self.test.id, "test_marks": 70})
        self.assertAlmostEqual(a.aggregate, round((10 * 90 + 40 * 80 + 50 * 70) / 100, 3))
        a.hafiz = True
        self.assertAlmostEqual(a.aggregate, round((10 * 90 + 40 * 80 + 50 * 70) / 100 + 2, 3))
        self.assertTrue(a.test_taken)

    def test_roll_numbers_and_rooms(self):
        apps = [_apply(self.env, self.reg, n, 800, 800) for n in ("Ali", "Bano", "Chand")]
        self.test.action_assign()
        self.assertEqual([a.test_roll_no for a in apps], ["ET-0001", "ET-0002", "ET-0003"])
        self.assertTrue(all(a.test_room_id == self.room for a in apps))
        _apply(self.env, self.reg, "Dua", 800, 800)
        with self.assertRaises(UserError):
            self.test.action_assign()  # 4 candidates, 3 seats

    def test_merit_list(self):
        top = _apply(self.env, self.reg, "Top", 1000, 1000)
        mid = _apply(self.env, self.reg, "Mid", 900, 900)
        low = _apply(self.env, self.reg, "Low", 700, 700)
        last = _apply(self.env, self.reg, "Last", 600, 600)
        nomarks = _apply(self.env, self.reg, "Absent", 1000, 1000)
        for a, m in ((top, 90), (mid, 80), (low, 60), (last, 50)):
            a.write({"entry_test_id": self.test.id, "test_marks": m})
        self.reg.action_generate_merit()
        self.assertEqual((top.merit_rank, top.merit_status), (1, "selected"))
        self.assertEqual((mid.merit_rank, mid.merit_status), (2, "selected"))
        self.assertEqual(low.merit_status, "waiting")
        self.assertEqual(last.merit_status, "not_selected")
        self.assertEqual(nomarks.merit_status, "pending")

    def test_offer_creates_challan_and_payment_confirms_seat(self):
        a = _apply(self.env, self.reg, "Offer", 1000, 1000)
        a.write({"entry_test_id": self.test.id, "test_marks": 95})
        self.reg.action_generate_merit()
        self.reg.action_send_offers()
        self.assertTrue(a.offer_sent_on)
        self.assertEqual(a.offer_expires_on, a.offer_sent_on + timedelta(days=7))
        challan = a.admission_challan_id
        self.assertEqual(challan.state, "issued")
        self.assertEqual(challan.amount, 15000)
        self.assertEqual(challan.due_date, a.offer_expires_on)
        self.assertEqual(challan.partner_id, a.partner_id)
        self.assertTrue(self.env["mail.mail"].search([("model", "=", "op.admission"), ("res_id", "=", a.id)]))
        journal = self.env["account.journal"].search([("type", "=", "bank")], limit=1)
        challan.confirm_payment(fields.Date.today(), journal=journal)
        self.assertEqual(a.state, "admission")

    def test_no_offer_before_merit(self):
        _apply(self.env, self.reg, "Early", 1000, 1000)
        with self.assertRaises(UserError):
            self.reg.action_send_offers()


@tagged("post_install", "-at_install")
class TestAdmissionWebsite(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.reg = _register(cls.env, name="BSSE Online W")
        cls.closed = _register(cls.env, name="Closed W", online=False)

    def _form(self, **over):
        data = {"first_name": "Faiza", "last_name": "Web", "email": "faiza.web@example.com", "mobile": "03001234567",
                "gender": "f", "birth_date": "2007-02-02", "matric_obtained": "1000", "matric_total": "1100",
                "inter_obtained": "950", "inter_total": "1100", "hafiz": "1"}
        data.update(over)
        page = self.url_open("/admission/apply/%s" % self.reg.id).text
        import re
        data["csrf_token"] = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        return self.url_open("/admission/apply/%s" % self.reg.id, data=data)

    def test_index_lists_only_online_registers(self):
        page = self.url_open("/admission").text
        self.assertIn("BSSE Online W", page)
        self.assertNotIn("Closed W", page)
        self.assertIn("not taking applications", self.url_open("/admission/apply/%s" % self.closed.id).text)

    def test_apply_creates_submitted_application(self):
        r = self._form()
        self.assertEqual(r.status_code, 200)
        a = self.env["op.admission"].search([("email", "=", "faiza.web@example.com")])
        self.assertTrue(a)
        self.assertEqual(a.state, "submit")
        self.assertTrue(a.applied_online)
        self.assertTrue(a.hafiz)
        self.assertIn(a.application_number, r.text)
        # same email again is refused
        r2 = self._form()
        self.assertIn("already applied", r2.text)
        self.assertEqual(self.env["op.admission"].search_count([("email", "=", "faiza.web@example.com")]), 1)

    def test_validation_and_honeypot(self):
        r = self._form(email="not-an-email", inter_obtained="2000")
        self.assertIn("valid email", r.text)
        self.assertFalse(self.env["op.admission"].search([("email", "=", "not-an-email")]))
        self._form(email="bot@example.com", website_url="http://spam")
        self.assertFalse(self.env["op.admission"].search([("email", "=", "bot@example.com")]))

    def test_status_needs_token(self):
        self._form(email="status.web@example.com")
        a = self.env["op.admission"].search([("email", "=", "status.web@example.com")])
        ok = self.url_open(a.status_url())
        self.assertEqual(ok.status_code, 200)
        self.assertIn(a.application_number, ok.text)
        bad = self.url_open("/admission/status/%s/%s" % (a.id, "0" * 32), allow_redirects=False)
        self.assertEqual(bad.status_code, 404)
