from odoo import http
from odoo.http import request

from odoo.addons.icterp_edu_portal.controllers.portal import EducationPortal


class ChallanPortal(EducationPortal):

    def _edu_extra_values(self, student, **kw):
        values = super()._edu_extra_values(student, **kw)
        values["edu_challans"] = request.env["icterp.fee.challan"].sudo().search(
            [("student_id", "=", student.id), ("state", "in", ["issued", "paid"])], order="issue_date desc", limit=20)
        return values

    @http.route(["/my/education/challan/<int:challan_id>"], type="http", auth="user", website=True)
    def portal_education_challan(self, challan_id, **kw):
        challan = request.env["icterp.fee.challan"].sudo().browse(challan_id).exists()
        # only a challan of one of this user's own students (or children)
        if not challan or challan.student_id not in self._edu_students() or challan.state not in ("issued", "paid"):
            raise request.not_found()
        pdf, _type = request.env["ir.actions.report"].sudo()._render_qweb_pdf(
            "icterp_edu_fee_challan.action_report_challan", challan.ids)
        return request.make_response(pdf, headers=[
            ("Content-Type", "application/pdf"), ("Content-Length", len(pdf)),
            ("Content-Disposition", http.content_disposition("Challan %s.pdf" % challan.name))])
