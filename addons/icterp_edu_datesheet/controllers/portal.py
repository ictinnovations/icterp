from odoo import http
from odoo.http import request

from odoo.addons.icterp_edu_portal.controllers.portal import EducationPortal


class DatesheetPortal(EducationPortal):

    def _edu_published_schedules(self, student):
        terms = student.enrollment_ids.filtered(lambda e: e.state in ("enrolled", "completed")).mapped("term_id")
        return request.env["icterp.exam.schedule"].sudo().search(
            [("state", "=", "published"), ("term_id", "in", terms.ids)], order="date_from desc")

    def _edu_extra_values(self, student, **kw):
        values = super()._edu_extra_values(student, **kw)
        exams = []
        for sched in self._edu_published_schedules(student):
            rows = student.sudo()._exam_papers(sched)
            if rows:
                exams.append({"schedule": sched, "rows": rows, "held": sched._slip_held(student.sudo())})
        values["edu_exams"] = exams
        return values

    @http.route(["/my/education/<int:student_id>/exam-slip/<int:schedule_id>"], type="http", auth="user", website=True)
    def portal_education_exam_slip(self, student_id, schedule_id, **kw):
        student = self._edu_student_or_404(student_id)
        sched = self._edu_published_schedules(student).filtered(lambda s: s.id == schedule_id)
        if not sched or sched._slip_held(student.sudo()):
            raise request.not_found()
        pdf, _type = request.env["ir.actions.report"].sudo()._render_qweb_pdf(
            "icterp_edu_datesheet.action_report_slip", sched.ids, data={"student_ids": student.ids})
        return request.make_response(pdf, headers=[
            ("Content-Type", "application/pdf"), ("Content-Length", len(pdf)),
            ("Content-Disposition", http.content_disposition("Exam slip - %s.pdf" % sched.name))])
