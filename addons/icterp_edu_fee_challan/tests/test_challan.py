import base64
from datetime import date, timedelta

from odoo.exceptions import UserError
from odoo.tests.common import HttpCase, TransactionCase, tagged


class ChallanCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        income = env["account.account"].search([("account_type", "=", "income"), ("company_ids", "in", env.company.id)], limit=1) \
            or env["account.account"].search([("account_type", "=", "income")], limit=1)
        cls.tuition = env["product.product"].create({"name": "Tuition fee T", "type": "service", "list_price": 50000,
                                                     "property_account_income_id": income.id, "taxes_id": [(6, 0, [])]})
        cls.lab = env["product.product"].create({"name": "Lab fee T", "type": "service", "list_price": 5000,
                                                 "property_account_income_id": income.id, "taxes_id": [(6, 0, [])]})
        fine_product = env.ref("icterp_edu_fee_challan.product_late_fine")
        fine_product.property_account_income_id = income
        cls.policy = env["icterp.fine.policy"].create({"name": "100/day", "method": "per_day", "amount": 100,
                                                       "max_amount": 1000, "grace_days": 2, "product_id": fine_product.id})
        env.company.challan_fine_policy_id = cls.policy
        cls.journal = env["account.journal"].search([("type", "=", "bank"), ("company_id", "=", env.company.id)], limit=1)
        cls.student = env["op.student"].create({"first_name": "Bilal", "last_name": "Khan", "name": "Bilal Khan",
                                                "gender": "m", "birth_date": date(2006, 1, 1), "email": "bilal.fee@example.com"})

    def fee_line(self, product, amount, when=None, student=None):
        return self.env["op.student.fees.details"].create({
            "student_id": (student or self.student).id, "product_id": product.id, "amount": amount,
            "date": when or date.today(), "state": "draft"})

    def make_challan(self, due=None):
        self.fee_line(self.tuition, 50000)
        self.fee_line(self.lab, 5000)
        wiz = self.env["icterp.generate.challans"].create({
            "student_ids": [(6, 0, self.student.ids)], "issue_date": date.today(), "due_date": due or date.today() + timedelta(days=10)})
        wiz.action_generate()
        return self.env["icterp.fee.challan"].search([("student_id", "=", self.student.id)], order="id desc", limit=1)


@tagged("post_install", "-at_install")
class TestFinePolicy(ChallanCase):
    def test_per_day_grace_and_cap(self):
        due = date(2026, 10, 10)
        self.assertEqual(self.policy.fine_for(due, date(2026, 10, 12)), 0)      # within grace
        self.assertEqual(self.policy.fine_for(due, date(2026, 10, 15)), 300)    # 3 days after grace
        self.assertEqual(self.policy.fine_for(due, date(2026, 12, 1)), 1000)    # capped

    def test_fixed(self):
        p = self.env["icterp.fine.policy"].create({"name": "fixed", "method": "fixed", "amount": 500,
                                                   "product_id": self.policy.product_id.id})
        self.assertEqual(p.fine_for(date(2026, 1, 1), date(2026, 1, 2)), 500)
        self.assertEqual(p.fine_for(date(2026, 1, 1), date(2026, 1, 1)), 0)


@tagged("post_install", "-at_install")
class TestChallanFlow(ChallanCase):

    def test_generate_and_issue(self):
        c = self.make_challan()
        self.assertEqual(c.state, "issued")
        self.assertEqual(c.amount, 55000)
        self.assertEqual(len(c.invoice_ids), 2)
        self.assertTrue(all(i.state == "posted" for i in c.invoice_ids))
        self.assertTrue(all(i.invoice_date_due == c.due_date for i in c.invoice_ids))
        self.assertEqual(len(c.fee_heads()), 2)
        # generating again does not bill the same invoices twice
        wiz = self.env["icterp.generate.challans"].create({"student_ids": [(6, 0, self.student.ids)],
                                                           "due_date": date.today() + timedelta(days=5)})
        wiz.action_generate()
        self.assertIn("Nothing to bill", wiz.result_note)

    def test_paid_on_time(self):
        c = self.make_challan(due=date.today() + timedelta(days=10))
        c.confirm_payment(date.today(), journal=self.journal, reference="SCROLL-1")
        self.assertEqual(c.state, "paid")
        self.assertEqual(c.fine_amount, 0)
        self.assertTrue(all(i.payment_state in ("paid", "in_payment") for i in c.invoice_ids))

    def test_paid_late_adds_fine(self):
        c = self.make_challan(due=date.today() - timedelta(days=7))  # 5 days after grace -> 500
        c.confirm_payment(date.today(), journal=self.journal)
        self.assertEqual(c.fine_amount, 500)
        self.assertTrue(c.fine_invoice_id)
        self.assertEqual(c.fine_invoice_id.amount_total, 500)
        self.assertIn(c.fine_invoice_id.payment_state, ("paid", "in_payment"))
        self.assertEqual(c.paid_amount, 55500)

    def test_short_payment_refused(self):
        c = self.make_challan(due=date.today() - timedelta(days=7))
        with self.assertRaises(UserError):
            c.confirm_payment(date.today(), amount=55000, journal=self.journal)  # forgot the fine

    def test_cannot_pay_twice_or_cancel_paid(self):
        c = self.make_challan()
        c.confirm_payment(date.today(), journal=self.journal)
        with self.assertRaises(UserError):
            c.confirm_payment(date.today(), journal=self.journal)
        with self.assertRaises(UserError):
            c.action_cancel()

    def test_bank_file_import(self):
        c = self.make_challan()
        csv_text = "challan,paid_date,amount,reference\n%s,%s,55000,BANK-77\nCH-NOPE,24/10/2026,100,\n" % (
            c.name, date.today().strftime("%d/%m/%Y"))
        wiz = self.env["icterp.challan.bank.import"].create({"file": base64.b64encode(csv_text.encode()),
                                                             "journal_id": self.journal.id})
        wiz.action_import()
        self.assertEqual(c.state, "paid")
        self.assertEqual(c.bank_reference, "BANK-77")
        self.assertIn("1 challan(s) confirmed", wiz.result_note)
        self.assertIn("CH-NOPE", wiz.result_note)

    def test_overdue_helper(self):
        c = self.make_challan(due=date.today() - timedelta(days=1))
        self.assertIn(c, self.student._unpaid_overdue_challans())


@tagged("post_install", "-at_install")
class TestScholarship(ChallanCase):

    def test_scholarship_discounts_chosen_heads_only(self):
        tuition = self.fee_line(self.tuition, 50000)
        lab = self.fee_line(self.lab, 5000)
        merit = self.env["icterp.scholarship"].create({"name": "Merit 50%", "percent": 50, "product_ids": [(6, 0, self.tuition.ids)]})
        award = self.env["icterp.student.scholarship"].create({"student_id": self.student.id, "scholarship_id": merit.id,
                                                               "date_from": date.today() - timedelta(days=30)})
        award.action_approve()
        self.assertEqual(tuition.discount, 50)
        self.assertEqual(lab.discount, 0)
        tuition.get_invoice()
        self.assertEqual(tuition.invoice_id.amount_total, 25000)
        award.action_cancel()
        self.assertEqual(lab.discount, 0)

    def test_waiver_is_100(self):
        line = self.fee_line(self.lab, 5000)
        waiver = self.env["icterp.scholarship"].create({"name": "Staff child waiver", "kind": "waiver", "percent": 100})
        self.env["icterp.student.scholarship"].create({"student_id": self.student.id, "scholarship_id": waiver.id,
                                                       "date_from": date.today() - timedelta(days=1)}).action_approve()
        self.assertEqual(line.discount, 100)
        self.assertEqual(line.after_discount_amount, 0)

    def test_invoiced_lines_not_touched(self):
        line = self.fee_line(self.tuition, 50000)
        line.get_invoice()
        s = self.env["icterp.scholarship"].create({"name": "Late award", "percent": 25})
        self.env["icterp.student.scholarship"].create({"student_id": self.student.id, "scholarship_id": s.id,
                                                       "date_from": date.today() - timedelta(days=1)}).action_approve()
        self.assertFalse(line.discount)


@tagged("post_install", "-at_install")
class TestChallanPortal(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        portal = env.ref("base.group_portal")
        income = env["account.account"].search([("account_type", "=", "income")], limit=1)
        product = env["product.product"].create({"name": "Tuition P", "type": "service",
                                                 "property_account_income_id": income.id, "taxes_id": [(6, 0, [])]})

        def student(first, login):
            s = env["op.student"].create({"first_name": first, "last_name": "F", "name": first + " F", "gender": "m",
                                          "birth_date": date(2006, 1, 1), "email": login})
            s.user_id = env["res.users"].create({"name": s.name, "login": login, "password": login,
                                                 "partner_id": s.partner_id.id, "group_ids": [(6, 0, portal.ids)]})
            env["op.student.fees.details"].create({"student_id": s.id, "product_id": product.id, "amount": 1000,
                                                   "date": date.today(), "state": "draft"})
            env["icterp.generate.challans"].create({"student_ids": [(6, 0, s.ids)], "due_date": date.today() + timedelta(days=9)}).action_generate()
            return s

        cls.ali = student("Ali", "ali.fee.p@example.com")
        cls.zain = student("Zain", "zain.fee.p@example.com")

    def test_own_challan_only(self):
        mine = self.env["icterp.fee.challan"].search([("student_id", "=", self.ali.id)])
        theirs = self.env["icterp.fee.challan"].search([("student_id", "=", self.zain.id)])
        self.authenticate("ali.fee.p@example.com", "ali.fee.p@example.com")
        page = self.url_open("/my/education/%s" % self.ali.id)
        self.assertIn(mine.name, page.text)
        self.assertEqual(self.url_open("/my/education/challan/%s" % mine.id).status_code, 200)
        self.assertEqual(self.url_open("/my/education/challan/%s" % theirs.id, allow_redirects=False).status_code, 404)
