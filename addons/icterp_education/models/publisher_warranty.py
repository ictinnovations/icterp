"""No reporting to OpenEduCat's servers.

openeducat_core adds a daily cron, hidden from the Scheduled Actions list, that posts the
database UUID, user counts, web.base.url, installed apps and the company name, email and phone
to srv.openeducat.org. A customer's ICTERP must not send that to a third party, so the call is
replaced with a no-op and the cron is switched off (data/branding_data.xml). The vendored copy
also has the endpoint blanked (vendor-openeducat.sh) in case this module is ever missing.
"""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class PublisherWarrantyContract(models.AbstractModel):
    _inherit = "publisher_warranty.contract"

    @api.model
    def _get_system_logs(self):
        _logger.debug("ICTERP: OpenEduCat publisher warranty report skipped")
        return {}

    def update_notification_openeducat(self, cron_mode=True):
        return True
