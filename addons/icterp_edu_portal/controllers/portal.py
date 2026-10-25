"""Education pages in the ICTERP portal.

Who sees what:
- a student sees their own record;
- a parent sees every child linked to them (op.parent.user_id, or res.users.child_ids).

Every read goes through sudo() but is always filtered by a student id taken from
_edu_students(), which is built from the logged-in user only. A student id in the URL is only
used after checking it is in that set, so nobody can open another family's pages by changing
the number.
"""
from datetime import datetime, time, timedelta

from odoo import fields, http
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal


class EducationPortal(CustomerPortal):

    # ------------------------------------------------------------------ who
    def _edu_students(self):
        user = request.env.user
        if user._is_public():
            return request.env["op.student"].sudo().browse()
        Student = request.env["op.student"].sudo()
        students = Student.search([("user_id", "=", user.id)])
        parents = request.env["op.parent"].sudo().search([("user_id", "=", user.id)])
        students |= parents.mapped("student_ids")
        children = user.sudo().child_ids
        if children:
            students |= Student.search([("user_id", "in", children.ids)])
        return students

    def _edu_student_or_404(self, student_id):
        student = self._edu_students().filtered(lambda s: s.id == student_id)
        if not student:
            raise request.not_found()
        return student

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if "edu_count" in counters:
            values["edu_count"] = len(self._edu_students())
        return values

    # ------------------------------------------------------------------ data
    def _edu_batches(self, student):
        details = student.course_detail_ids.filtered(lambda d: d.state != "finished") or student.course_detail_ids
        return details.mapped("batch_id")

    def _edu_week(self, offset):
        today = fields.Date.context_today(request.env.user)
        monday = today - timedelta(days=today.weekday()) + timedelta(weeks=offset)
        return monday, monday + timedelta(days=6)

    def _edu_timetable(self, student, offset):
        monday, sunday = self._edu_week(offset)
        batches = self._edu_batches(student)
        sessions = request.env["op.session"].sudo().search([
            ("batch_id", "in", batches.ids),
            ("state", "!=", "cancel"),
            ("start_datetime", ">=", datetime.combine(monday, time.min)),
            ("start_datetime", "<=", datetime.combine(sunday, time.max)),
        ], order="start_datetime")
        days = []
        for i in range(7):
            day = monday + timedelta(days=i)
            todays = sessions.filtered(
                lambda s, d=day: fields.Datetime.context_timestamp(s, s.start_datetime).date() == d)
            if todays or i < 5:
                days.append({"date": day, "sessions": todays})
        return {"monday": monday, "sunday": sunday, "days": days, "offset": offset}

    def _edu_attendance(self, student):
        lines = request.env["op.attendance.line"].sudo().search([
            ("student_id", "=", student.id), ("attendance_id.state", "=", "done"),
        ], order="attendance_date desc")
        total = len(lines)
        present = len(lines.filtered("present"))
        return {
            "total": total,
            "present": present,
            "absent": len(lines.filtered("absent")),
            "late": len(lines.filtered("late")),
            "excused": len(lines.filtered("excused")),
            "percent": round(100.0 * present / total) if total else None,
            "recent": lines[:20],
        }

    def _edu_results(self, student):
        # only validated mark sheets: draft marks are still being entered by teachers
        return request.env["op.marksheet.line"].sudo().search([
            ("student_id", "=", student.id), ("marksheet_reg_id.state", "=", "validated"),
        ], order="id desc")

    def _edu_assignments(self, student):
        assignments = request.env["op.assignment"].sudo().search([
            ("allocation_ids", "in", student.ids), ("state", "in", ["publish", "finish"]),
        ], order="submission_date desc")
        subs = request.env["op.assignment.sub.line"].sudo().search([
            ("student_id", "=", student.id), ("assignment_id", "in", assignments.ids),
        ])
        by_assignment = {s.assignment_id.id: s for s in subs}
        return [{"assignment": a, "submission": by_assignment.get(a.id)} for a in assignments]

    def _edu_fees(self, student):
        rows = []
        details = request.env["op.student.fees.details"].sudo().search(
            [("student_id", "=", student.id), ("state", "!=", "cancel")], order="date, id")
        for fee in details:
            invoice = fee.invoice_id
            posted = invoice and invoice.state == "posted"
            rows.append({
                "fee": fee,
                "invoice": invoice if posted else False,
                "paid": bool(posted and invoice.payment_state in ("paid", "in_payment")),
                "due": invoice.amount_residual if posted else fee.after_discount_amount or fee.amount,
                "url": invoice.get_portal_url() if posted else False,
            })
        return rows

    def _edu_library(self, student):
        return request.env["op.media.movement"].sudo().search([
            ("student_id", "=", student.id), ("state", "in", ["issue", "reserve", "lost"]),
        ], order="return_date")

    # ------------------------------------------------------------------ pages
    @http.route(["/my/education"], type="http", auth="user", website=True)
    def portal_my_education(self, **kw):
        students = self._edu_students()
        if len(students) == 1:
            return request.redirect("/my/education/%s" % students.id)
        return request.render("icterp_edu_portal.portal_my_education", {
            "students": students, "page_name": "education",
        })

    @http.route(["/my/education/<int:student_id>"], type="http", auth="user", website=True)
    def portal_my_education_student(self, student_id, week=0, **kw):
        student = self._edu_student_or_404(student_id)
        try:
            offset = max(-52, min(52, int(week)))
        except (TypeError, ValueError):
            offset = 0
        values = {
            "student": student,
            "multi": len(self._edu_students()) > 1,
            "is_self": student.user_id == request.env.user,
            "timetable": self._edu_timetable(student, offset),
            "attendance": self._edu_attendance(student),
            "results": self._edu_results(student),
            "assignments": self._edu_assignments(student),
            "fees": self._edu_fees(student),
            "library": self._edu_library(student),
            "today": fields.Date.context_today(request.env.user),
            "page_name": "education_student",
            "message": kw.get("message"),
            "error": kw.get("error"),
        }
        values.update(self._edu_extra_values(student, **kw))
        return request.render("icterp_edu_portal.portal_my_education_student", values)

    def _edu_extra_values(self, student, **kw):
        """Hook for other education modules (registration, exams, fees) to add their portal data."""
        return {}

    @http.route(["/my/education/<int:student_id>/assignment/<int:assignment_id>/submit"],
                type="http", auth="user", website=True, methods=["POST"])
    def portal_education_submit(self, student_id, assignment_id, answer="", **kw):
        student = self._edu_student_or_404(student_id)
        url = "/my/education/%s#assignments" % student.id
        # parents can read their child's work but only the student hands it in
        if student.user_id != request.env.user:
            raise request.not_found()
        assignment = request.env["op.assignment"].sudo().search([
            ("id", "=", assignment_id), ("allocation_ids", "in", student.ids), ("state", "=", "publish"),
        ])
        if not assignment:
            raise request.not_found()
        answer = (answer or "").strip()
        if not answer:
            return request.redirect(url.replace("#", "?error=empty#"))
        Sub = request.env["op.assignment.sub.line"].sudo()
        sub = Sub.search([("assignment_id", "=", assignment.id), ("student_id", "=", student.id)], limit=1)
        if sub and sub.state not in ("draft", "change"):
            return request.redirect(url.replace("#", "?error=locked#"))
        vals = {"description": answer, "state": "submit", "submission_date": fields.Datetime.now()}
        if sub:
            sub.write(vals)
        else:
            Sub.create(dict(vals, assignment_id=assignment.id, student_id=student.id))
        return request.redirect(url.replace("#", "?message=submitted#"))
