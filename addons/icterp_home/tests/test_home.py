from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestIcterpHome(TransactionCase):
    def setUp(self):
        super().setUp()
        self.action = self.env.ref("icterp_home.action_home")
        self.Section = self.env["icterp.home.section"]

    def _settings(self, **vals):
        settings = self.env["res.config.settings"].create(vals)
        settings.execute()
        return settings

    def test_admin_lands_on_home(self):
        self.assertEqual(self.env.ref("base.user_admin").action_id.id, self.action.id)

    def test_new_internal_user_gets_home(self):
        user = self.env["res.users"].create({"name": "Home Test", "login": "home_test_internal"})
        self.assertEqual(user.action_id.id, self.action.id)

    def test_portal_user_untouched(self):
        user = self.env["res.users"].create({
            "name": "Home Portal",
            "login": "home_test_portal",
            "group_ids": [(6, 0, [self.env.ref("base.group_portal").id])],
        })
        self.assertFalse(user.action_id)

    def test_explicit_home_kept(self):
        other = self.env.ref("base.action_res_users")
        user = self.env["res.users"].create({
            "name": "Home Own", "login": "home_test_own", "action_id": other.id,
        })
        self.assertEqual(user.action_id.id, other.id)

    def test_assign_skips_users_with_home(self):
        other = self.env.ref("base.action_res_users")
        user = self.env["res.users"].create({"name": "Home Keep", "login": "home_test_keep"})
        user.action_id = other.id
        self.env["res.users"]._icterp_home_assign()
        self.assertEqual(user.action_id.id, other.id)

    def test_menu_is_first_app(self):
        menu = self.env.ref("icterp_home.menu_home")
        self.assertFalse(menu.parent_id)
        self.assertEqual(menu.action, self.action)

    def test_default_sections_created(self):
        names = self.Section.search([]).mapped("name")
        self.assertIn("Administration", names)
        admin = self.Section.search([("name", "=", "Administration")])
        self.assertIn(self.env.ref("base.menu_administration"), admin.menu_ids)

    def test_home_data_hides_home_menu_and_respects_order(self):
        data = self.Section.get_home_data()
        home = self.env.ref("icterp_home.menu_home").id
        self.assertIn(home, data["hidden_ids"])
        for s in data["sections"]:
            self.assertNotIn(home, s["menu_ids"])
        seqs = [self.Section.browse(s["id"]).sequence for s in data["sections"]]
        self.assertEqual(seqs, sorted(seqs))

    def test_menu_shown_once(self):
        settings_menu = self.env.ref("base.menu_administration")
        self.Section.create({"name": "Dup", "sequence": 999, "menu_ids": [(6, 0, settings_menu.ids)]})
        data = self.Section.get_home_data()
        hits = [s["title"] for s in data["sections"] if settings_menu.id in s["menu_ids"]]
        self.assertEqual(hits, ["Administration"])

    def test_prefix_pulls_in_later_apps(self):
        self.Section.search([]).write({"module_prefixes": False})
        contacts = self.env.ref("base.menu_management")
        self.Section.search([]).write({"menu_ids": [(3, contacts.id)]})
        self.Section.create({"name": "Base apps", "sequence": 1, "module_prefixes": "bas"})
        data = self.Section.get_home_data()
        first = data["sections"][0]
        self.assertEqual(first["title"], "Base apps")
        self.assertIn(contacts.id, first["menu_ids"])

    def test_archived_section_not_returned(self):
        admin = self.Section.search([("name", "=", "Administration")])
        admin.active = False
        titles = [s["title"] for s in self.Section.get_home_data()["sections"]]
        self.assertNotIn("Administration", titles)

    def test_settings_welcome_and_more(self):
        self._settings(icterp_home_enabled=True, icterp_home_show_more=False,
                       icterp_home_welcome="Welcome to Greenfield College")
        data = self.Section.get_home_data()
        self.assertEqual(data["welcome"], "Welcome to Greenfield College")
        self.assertFalse(data["show_more"])
        self._settings(icterp_home_enabled=True, icterp_home_show_more=True)
        self.assertTrue(self.Section.get_home_data()["show_more"])

    def test_settings_disable_and_enable(self):
        admin = self.env.ref("base.user_admin")
        self._settings(icterp_home_enabled=False, icterp_home_show_more=True)
        self.assertFalse(admin.action_id)
        user = self.env["res.users"].create({"name": "Off", "login": "home_test_off"})
        self.assertFalse(user.action_id)
        self._settings(icterp_home_enabled=True, icterp_home_show_more=True)
        self.assertEqual(admin.action_id.id, self.action.id)
        self.assertEqual(user.action_id.id, self.action.id)

    def test_settings_defaults_read_back(self):
        values = self.env["res.config.settings"].default_get(["icterp_home_enabled", "icterp_home_show_more"])
        self.assertTrue(values["icterp_home_enabled"])
        self.assertTrue(values["icterp_home_show_more"])

    def test_prefix_section_lists_its_apps(self):
        students = self.env.ref("openeducat_core.menu_op_student_root", raise_if_not_found=False)
        if not students:
            self.skipTest("education not installed")
        # Opening Configure sections lists apps installed after icterp_home as well.
        self.env["res.config.settings"].create({}).action_icterp_home_sections()
        edu = self.Section.search([("name", "=", "Education")])
        self.assertIn(students, edu.menu_ids)
