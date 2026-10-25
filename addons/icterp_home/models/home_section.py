from odoo import api, fields, models

# Sections created on install. Menus are matched by xmlid when the app is installed;
# prefixes also pull in apps installed later (for example a new education app).
DEFAULT_SECTIONS = [
    ("Education", "Students, admissions, classes, exams and fees", [], "openeducat_,icterp_edu"),
    ("Sales and customers", "Leads, quotations, contacts and your website", [
        "crm.crm_menu_root", "sale.sale_menu_root", "contacts.menu_contacts",
        "website.menu_website_configuration", "im_livechat.menu_livechat_root",
        "calendar.mail_menu_calendar"], ""),
    ("Finance and operations", "Invoices, purchasing, stock, production and projects", [
        "account.menu_finance", "purchase.menu_purchase_root", "stock.menu_stock_root",
        "mrp.menu_mrp_root", "project.menu_main_pm"], ""),
    ("People", "Employees, time off and payroll", [
        "hr.menu_hr_root", "hr_holidays.menu_hr_holidays_root", "payroll.payroll_menu_root"], ""),
    ("Everyday tools", "Messages, to-dos and dashboards", [
        "mail.menu_root_discuss", "project_todo.menu_todo_todos",
        "spreadsheet_dashboard.spreadsheet_dashboard_menu_root"], ""),
    ("Administration", "Settings, users and installed apps", [
        "base.menu_administration", "base.menu_management"], ""),
]
# Never shown as tiles.
HIDDEN_MENUS = ["icterp_home.menu_home", "base.menu_tests", "utm.menu_link_tracker_root"]


class IcterpHomeSection(models.Model):
    _name = "icterp.home.section"
    _description = "Home page section"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    hint = fields.Char(string="Description", translate=True,
                       help="Short line shown next to the section title.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    menu_ids = fields.Many2many(
        "ir.ui.menu", string="Apps", domain=[("parent_id", "=", False)],
        help="Apps shown in this section.")
    module_prefixes = fields.Char(
        string="Also include apps from modules starting with",
        help="Comma-separated, for example openeducat_. Apps installed later whose module "
             "name starts with one of these join this section automatically.")

    @api.model
    def _icterp_create_defaults(self):
        if self.with_context(active_test=False).search_count([]):
            return
        top = self.env["ir.ui.menu"].search([("parent_id", "=", False)])
        top_xmlids = top.get_external_id()
        for seq, (name, hint, xmlids, prefixes) in enumerate(DEFAULT_SECTIONS, start=1):
            menus = self.env["ir.ui.menu"]
            for xmlid in xmlids:
                menus |= self.env.ref(xmlid, raise_if_not_found=False) or self.env["ir.ui.menu"]
            # List prefix-matched apps too, so the section screen shows what it holds.
            for p in filter(None, prefixes.split(",")):
                menus |= top.filtered(lambda m: (top_xmlids.get(m.id) or "").startswith(p))
            self.create({
                "name": name, "hint": hint, "sequence": seq * 10,
                "menu_ids": [(6, 0, menus.ids)], "module_prefixes": prefixes,
            })

    @api.model
    def _icterp_sync_prefix_menus(self):
        """List apps that match a section's module prefixes, including apps installed after this module."""
        top = self.env["ir.ui.menu"].sudo().search([("parent_id", "=", False)])
        xmlids = top.get_external_id()
        taken = self.sudo().with_context(active_test=False).search([]).mapped("menu_ids")
        for section in self.sudo().with_context(active_test=False).search([("module_prefixes", "!=", False)]):
            prefixes = [p.strip() for p in section.module_prefixes.split(",") if p.strip()]
            new = top.filtered(lambda m: m not in taken and any((xmlids.get(m.id) or "").startswith(p) for p in prefixes))
            if new:
                section.menu_ids = [(4, m.id) for m in new]
                taken |= new

    @api.model
    def get_home_data(self):
        """Sections with the top-level menu ids they hold, for the home page.

        Which apps each user may open is left to the web client menu service,
        which only receives the menus the user has access to.
        """
        param = self.env["ir.config_parameter"].sudo()
        top = self.env["ir.ui.menu"].sudo().search([("parent_id", "=", False)])
        xmlids = top.get_external_id()
        hidden = {m.id for m in (self.env.ref(x, raise_if_not_found=False) for x in HIDDEN_MENUS) if m}
        used, sections = set(hidden), []
        for section in self.sudo().search([]):
            prefixes = [p.strip() for p in (section.module_prefixes or "").split(",") if p.strip()]
            ids = [m.id for m in section.menu_ids if m.id not in used]
            for menu in top:
                if menu.id in used or menu.id in ids:
                    continue
                module = (xmlids.get(menu.id) or "").split(".")[0]
                if module and any(module.startswith(p) for p in prefixes):
                    ids.append(menu.id)
            used.update(ids)
            sections.append({"id": section.id, "title": section.name, "hint": section.hint or "", "menu_ids": ids})
        return {
            "welcome": param.get_param("icterp_home.welcome") or "",
            "show_more": param.get_param("icterp_home.show_more", "True") != "False",
            "hidden_ids": sorted(hidden),
            "sections": sections,
        }
