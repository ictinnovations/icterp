from lxml import etree

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestEducationBranding(TransactionCase):
    def test_bot_is_icterp(self):
        self.assertEqual(self.env.ref("base.partner_root").name, "ICTERP Assistant")

    def test_menus_renamed(self):
        self.assertEqual(self.env.ref("openeducat_core.menu_op_school_root").name, "Education")
        self.assertEqual(self.env.ref("openeducat_attendance.menu_op_attendance_root").name, "Attendance")

    def test_settings_have_no_openeducat_upsell(self):
        admin = self.env.ref("base.user_admin")
        arch = self.env["res.config.settings"].with_user(admin).get_views([(False, "form")])["views"]["form"]["arch"]
        self.assertNotIn("Enterprise Module", arch)
        self.assertNotIn("openeducat.org", arch)
        tree = etree.fromstring(arch)
        names = [a.get("string") for a in tree.xpath("//app")]
        self.assertIn("Education", names)
        self.assertFalse([n for n in names if n and n.lower().startswith("openeducat")])
        self.assertFalse(tree.xpath("//field[@name='module_openeducat_achievement_enterprise']"))

    def test_module_names(self):
        core = self.env["ir.module.module"].search([("name", "=", "openeducat_core")])
        self.assertEqual(core.shortdesc, "Education: Core")


@tagged("post_install", "-at_install")
class TestNoTelemetry(TransactionCase):
    def test_cron_is_off(self):
        cron = self.env.ref("openeducat_core.ir_cron_module_update_notification_openeducat")
        self.assertFalse(cron.active)

    def test_no_network_call(self):
        from unittest.mock import patch
        with patch("requests.post", side_effect=AssertionError("network call to OpenEduCat")) as post:
            self.env["publisher_warranty.contract"].update_notification_openeducat(None)
            self.assertEqual(self.env["publisher_warranty.contract"]._get_system_logs(), {})
            post.assert_not_called()


@tagged("post_install", "-at_install")
class TestAccessLabels(TransactionCase):
    def test_no_openeducat_in_access_labels(self):
        cats = self.env["ir.module.category"].search([("name", "ilike", "openeducat")])
        self.assertFalse(cats, cats.mapped("name"))
        if "res.groups.privilege" in self.env:
            privs = self.env["res.groups.privilege"].search([("name", "ilike", "openeducat")])
            self.assertFalse(privs, privs.mapped("name"))
