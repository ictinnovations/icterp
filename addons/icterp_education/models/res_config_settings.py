"""Settings screen without the OpenEduCat upsell.

The education apps ship Settings boxes for OpenEduCat's paid Enterprise modules (a checkbox that
can never install anything here, flagged "Openeducat Enterprise Module") and documentation links
to doc.openeducat.org. Both are stripped from the combined Settings view, and the app tab is
renamed to Education.
"""
from odoo import api, models

APP_NAMES = {"OpenEduCat": "Education"}


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type != "form":
            return arch, view
        installable = set(self.env["ir.module.module"].sudo().search([("state", "!=", "uninstallable")]).mapped("name"))
        for box in arch.xpath("//div[contains(@class, 'o_setting_box')] | //setting"):
            upsell = box.xpath(".//*[contains(@title, 'Enterprise Module')]")
            missing = [f.get("name") for f in box.xpath(".//field[starts-with(@name, 'module_')]")
                       if f.get("name")[len("module_"):] not in installable]
            if upsell or missing:
                box.getparent().remove(box)
        for link in arch.xpath("//a[contains(@href, 'openeducat')]"):
            link.getparent().remove(link)
        for app in arch.xpath("//app"):
            for attr in ("string", "data-string"):
                if (app.get(attr) or "").startswith(("OpenEduCat", "OpenEducat")):
                    app.set(attr, "Education")
        # a section left with no boxes is just an orphan heading
        for cont in arch.xpath("//div[contains(@class, 'o_settings_container')]"):
            if not len(cont):
                prev = cont.getprevious()
                if prev is not None and prev.tag == "h2":
                    prev.getparent().remove(prev)
                cont.getparent().remove(cont)
        return arch, view
