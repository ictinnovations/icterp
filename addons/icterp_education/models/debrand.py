"""Access-rights labels without the OpenEduCat name.

The education apps register their security categories and privileges as "OpenEduCat",
"OpenEduCat Others", "Openeducat Activity Privilege" and so on, which shows on every user's
Access Rights tab. Called from data/branding_data.xml on install and upgrade.
"""
import re

from odoo import api, models

_NAME = re.compile(r"open\s*edu\s*cat(?:-ce)?", re.I)


def _rename(records):
    for rec in records:
        new = _NAME.sub("Education", rec.name or "").replace("Education Education", "Education").strip()
        if new and new != rec.name:
            rec.name = new


class IrModuleCategory(models.Model):
    _inherit = "ir.module.category"

    @api.model
    def _icterp_debrand_education(self):
        _rename(self.sudo().search([("name", "ilike", "educat")]))
        if "res.groups.privilege" in self.env:
            _rename(self.env["res.groups.privilege"].sudo().search([("name", "ilike", "educat")]))
        _rename(self.env["res.groups"].sudo().search([("name", "ilike", "openeducat")]))
        return True
