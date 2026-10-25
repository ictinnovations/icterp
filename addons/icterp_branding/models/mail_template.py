import re

from odoo import api, models

# Odoo wording in stock email templates (the user invitation above all) and its ICTERP
# replacement. Patterns, not exact copies, so small upstream wording changes still match.
_REPLACEMENTS = [
    (r"invites you to connect to Odoo", "invites you to connect to ICTERP"),
    (r"Welcome to Odoo", "Welcome to ICTERP"),
    (r"to connect on Odoo\.", "to connect on ICTERP."),
    (r"Your Odoo domain is:", "Your ICTERP address is:"),
    (r"http://yourcompany\.odoo\.com", "https://yourcompany.icterp.com"),
    (r"Never heard of Odoo\?[^<]*", "ICTERP keeps your customers, sales, invoices and stock in one place.\n"),
    (r"Have a look at the <a [^>]*odoo\.com/page/tour[^>]*>Odoo Tour</a> to discover the tool\.\s*<br/><br/>", ""),
    (r"Enjoy Odoo!", "Enjoy ICTERP!"),
    (r"Powered by <a ([^>]*)href=\"https://www\.odoo\.com[^\"]*\"([^>]*)>Odoo</a>",
     r'Powered by <a \1href="https://icterp.com"\2>ICTERP</a>'),
]


class MailTemplate(models.Model):
    _inherit = "mail.template"

    @api.model
    def _icterp_debrand_templates(self):
        """Rewrite Odoo wording in email templates as ICTERP.

        The stock templates are noupdate records owned by other modules, so an XML
        <record> here would be skipped on upgrade; this runs on every install/upgrade.
        """
        for template in self.with_context(active_test=False).sudo().search([]):
            vals = {}
            for field in ("subject", "body_html"):
                text = template[field]
                if not text or "Odoo" not in text:
                    continue
                new = text
                for pattern, repl in _REPLACEMENTS:
                    new = re.sub(pattern, repl, new)
                if new != text:
                    vals[field] = new
            if vals:
                template.write(vals)
