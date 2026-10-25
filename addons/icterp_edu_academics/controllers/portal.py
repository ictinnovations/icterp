from odoo import http
from odoo.http import request

from odoo.addons.icterp_edu_portal.controllers.portal import EducationPortal


class AcademicsPortal(EducationPortal):

    def _edu_extra_values(self, student, **kw):
        values = super()._edu_extra_values(student, **kw)
        Enr = request.env["icterp.enrollment"].sudo()
        values.update({
            "edu_term_results": request.env["icterp.term.result"].sudo().search(
                [("student_id", "=", student.id)], order="term_start desc"),
            # current registrations; grades only once the offering is published
            "edu_registrations": Enr.search([("student_id", "=", student.id), ("state", "in", ["enrolled", "withdrawn"])],
                                            order="term_id desc"),
            "edu_published": Enr.search([("student_id", "=", student.id), ("published", "=", True)], limit=1),
        })
        return values

    @http.route(["/my/education/<int:student_id>/transcript"], type="http", auth="user", website=True)
    def portal_education_transcript(self, student_id, **kw):
        student = self._edu_student_or_404(student_id)
        pdf, _type = request.env["ir.actions.report"].sudo()._render_qweb_pdf(
            "icterp_edu_academics.action_report_transcript", student.ids)
        name = "Transcript - %s.pdf" % (student.name or student.id)
        return request.make_response(pdf, headers=[
            ("Content-Type", "application/pdf"), ("Content-Length", len(pdf)),
            ("Content-Disposition", http.content_disposition(name))])
