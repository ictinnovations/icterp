from odoo.addons.web.controllers.webmanifest import WebManifest
from odoo.http import request

ICTERP_COLOUR = "#1d4ed8"


class IcterpWebManifest(WebManifest):

    def _get_webmanifest(self):
        manifest = super()._get_webmanifest()
        manifest["name"] = request.env["ir.config_parameter"].sudo().get_param("web.web_app_name", "ICTERP")
        manifest["background_color"] = ICTERP_COLOUR
        manifest["theme_color"] = ICTERP_COLOUR
        manifest["icons"] = [{
            "src": "/icterp_branding/static/img/icterp-icon-%s.png" % size.split("x")[0],
            "sizes": size,
            "type": "image/png",
        } for size in ("192x192", "512x512")]
        return manifest
