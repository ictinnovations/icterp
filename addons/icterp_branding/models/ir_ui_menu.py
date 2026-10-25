"""ICTERP app icons in the apps menu.

The icons are swapped when the menu is sent to the browser, not written into each app's
menu record, so upgrading an app (which reloads its own icon) can't undo them, and an app
installed later picks its icon up as soon as one exists here. Apps with no ICTERP icon keep
their own.
"""
import base64
from functools import lru_cache

from odoo import api, models
from odoo.tools.misc import file_path

# app menu xmlid -> icon file in static/img/apps/
APP_ICONS = {
    "mail.menu_root_discuss": "discuss",
    "project_todo.menu_todo_todos": "todo",
    "calendar.mail_menu_calendar": "calendar",
    "contacts.menu_contacts": "contacts",
    "crm.crm_menu_root": "crm",
    "sale.sale_menu_root": "sales",
    "spreadsheet_dashboard.spreadsheet_dashboard_menu_root": "dashboards",
    "account.menu_finance": "invoicing",
    "project.menu_main_pm": "project",
    "utm.menu_link_tracker_root": "links",
    "base.menu_management": "apps",
    "base.menu_administration": "settings",
    "base.menu_tests": "tests",
    "stock.menu_stock_root": "inventory",
    "purchase.menu_purchase_root": "purchase",
    "mrp.menu_mrp_root": "manufacturing",
    "hr.menu_hr_root": "employees",
    "hr_holidays.menu_hr_holidays_root": "timeoff",
    "website.menu_website_configuration": "website",
}


@lru_cache(maxsize=None)
def _icon_b64(name):
    with open(file_path("icterp_branding/static/img/apps/%s.svg" % name), "rb") as handle:
        return base64.b64encode(handle.read()).decode()


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    @api.model
    def load_menus(self, debug):
        menus = super().load_menus(debug)
        for menu in menus.values():
            icon = APP_ICONS.get(menu.get("xmlid") or "")
            if icon:
                menu["web_icon_data"] = _icon_b64(icon)
                menu["web_icon_data_mimetype"] = "image/svg+xml"
        return menus

    @api.model
    def load_menus_root(self):
        root = super().load_menus_root()
        for menu in root.get("children", []):
            icon = APP_ICONS.get(menu.get("xmlid") or "")
            if icon:
                menu["web_icon_data"] = _icon_b64(icon)
        return root
