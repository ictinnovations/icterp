"""ICTERP icons on the Apps screen for the apps ICTERP uses.

Community shows module icons on the Apps cards (the `icon` URL) and on the module form
(`icon_image`). Both point at Odoo's own artwork; for the modules below they point at the
ICTERP set in static/img/apps/ instead. Other modules keep their own icons.
"""
from odoo import api, fields, models

from .ir_ui_menu import _icon_b64

MODULE_ICONS = {
    "mail": "discuss",
    "calendar": "calendar",
    "project_todo": "todo",
    "contacts": "contacts",
    "crm": "crm",
    "sale": "sales",
    "sale_management": "sales",
    "spreadsheet_dashboard": "dashboards",
    "account": "invoicing",
    "project": "project",
    "utm": "links",
    "stock": "inventory",
    "purchase": "purchase",
    "mrp": "manufacturing",
    "hr": "employees",
    "website": "website",
    "pos_restaurant": "restaurant",
    "point_of_sale": "pos",
    "website_sale": "ecommerce",
    "mass_mailing": "email",
    "hr_expense": "expenses",
    "hr_holidays": "timeoff",
    "hr_recruitment": "recruitment",
    "marketing_card": "card",
    "maintenance": "maintenance",
    "data_recycle": "recycle",
    "website_slides": "elearning",
    "website_event": "events",
    "fleet": "fleet",
    "im_livechat": "livechat",
    "survey": "survey",
    "repair": "repair",
    "hr_attendance": "attendance",
    "mass_mailing_sms": "sms",
    "hr_skills": "skills",
    "lunch": "lunch",
    "website_hr_recruitment": "jobs",
}


class IrModuleModule(models.Model):
    _inherit = "ir.module.module"

    icterp_icon_url = fields.Char(compute="_compute_icterp_icon_url")

    @api.depends("name", "icon")
    def _compute_icterp_icon_url(self):
        for module in self:
            name = MODULE_ICONS.get(module.name)
            module.icterp_icon_url = "/icterp_branding/static/img/apps/%s.svg" % name if name else module.icon

    @api.depends("icon")
    def _get_icon_image(self):
        super()._get_icon_image()
        for module in self:
            name = MODULE_ICONS.get(module.name)
            if name:
                module.icon_image = _icon_b64(name)
