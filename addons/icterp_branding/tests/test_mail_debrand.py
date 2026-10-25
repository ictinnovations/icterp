from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMailDebrand(TransactionCase):
    def test_invitation_says_icterp(self):
        self.env["mail.template"]._icterp_debrand_templates()
        tpl = self.env.ref("auth_signup.set_password_email")
        text = (tpl.subject or "") + (tpl.body_html or "")
        for phrase in ("Welcome to Odoo", "connect on Odoo", "connect to Odoo", "Odoo domain",
                       "Never heard of Odoo", "Odoo Tour", "Enjoy Odoo", "www.odoo.com"):
            self.assertNotIn(phrase, text)
        self.assertIn("Welcome to ICTERP", text)
        self.assertIn("Enjoy ICTERP!", text)

    def test_debrand_is_idempotent(self):
        model = self.env["mail.template"]
        model._icterp_debrand_templates()
        tpl = self.env.ref("auth_signup.set_password_email")
        before = tpl.body_html
        model._icterp_debrand_templates()
        self.assertEqual(before, tpl.body_html)
