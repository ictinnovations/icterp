import base64

from odoo import api, models
from odoo.tools import file_open


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model
    def _icterp_brand_bot(self):
        """Rename the system bot (OdooBot) and give it the ICTERP avatar.

        base.partner_root is a noupdate record owned by base, so an XML <record>
        in our module is skipped on upgrade; this runs on every install/upgrade.
        """
        bot = self.env.ref("base.partner_root", raise_if_not_found=False)
        if not bot:
            return
        with file_open("icterp_branding/static/img/assistant.png", "rb") as f:
            image = base64.b64encode(f.read())
        bot.with_context(active_test=False).sudo().write({"name": "ICTERP Assistant", "image_1920": image})
