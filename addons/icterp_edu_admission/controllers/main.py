"""Public admissions pages: open intakes, application form, application status.

Everything here is public, so:
- only registers marked `online` with open dates are shown or accept applications;
- the application is created through sudo() from a fixed list of fields (never **post);
- a hidden honeypot field stops simple bots;
- an applicant's status, admit card and challan are reachable only with the random access
  token emailed to them (or via application number + email on the lookup form).
"""
import re
from datetime import datetime

from odoo import _, fields, http
from odoo.http import request

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AdmissionWebsite(http.Controller):

    def _open_registers(self):
        today = fields.Date.context_today(request.env.user)
        return request.env["op.admission.register"].sudo().search([
            ("online", "=", True), ("state", "in", ["confirm", "application"]),
            ("start_date", "<=", today), ("end_date", ">=", today)], order="end_date")

    def _courses(self, register):
        if register.admission_base == "program" and register.program_id:
            courses = request.env["op.course"].sudo().search([("program_id", "=", register.program_id.id)])
            return courses or register.course_id
        return register.course_id

    @http.route(["/admission"], type="http", auth="public", website=True, sitemap=True)
    def admission_index(self, **kw):
        return request.render("icterp_edu_admission.page_admission_index", {"registers": self._open_registers()})

    @http.route(["/admission/apply/<int:register_id>"], type="http", auth="public", website=True, methods=["GET", "POST"], sitemap=False)
    def admission_apply(self, register_id, **post):
        register = self._open_registers().filtered(lambda r: r.id == register_id)
        if not register:
            return request.render("icterp_edu_admission.page_admission_closed", {})
        courses = self._courses(register)
        values = {"register": register, "courses": courses, "errors": {}, "post": post}
        if request.httprequest.method != "POST":
            return request.render("icterp_edu_admission.page_admission_form", values)

        if post.get("website_url"):  # honeypot: humans never see this field
            return request.render("icterp_edu_admission.page_admission_thanks", {"admission": False})
        errors = {}
        def req(name, label):
            v = (post.get(name) or "").strip()
            if not v:
                errors[name] = _("%s is required.", label)
            return v
        first = req("first_name", _("First name"))
        last = req("last_name", _("Last name"))
        email = req("email", _("Email")).lower()
        if email and not EMAIL_RE.match(email):
            errors["email"] = _("Enter a valid email address.")
        mobile = req("mobile", _("Mobile number"))
        gender = req("gender", _("Gender"))
        if gender and gender not in ("m", "f"):
            errors["gender"] = _("Choose a gender.")
        birth = None
        try:
            birth = datetime.strptime(req("birth_date", _("Date of birth")), "%Y-%m-%d").date()
        except ValueError:
            errors.setdefault("birth_date", _("Use the date picker for your date of birth."))
        course = courses.filtered(lambda c: str(c.id) == (post.get("course_id") or "")) if len(courses) > 1 else courses[:1]
        if not course:
            errors["course_id"] = _("Choose a programme.")

        def num(name, label):
            try:
                return float(post.get(name) or 0)
            except ValueError:
                errors[name] = _("%s must be a number.", label)
                return 0.0
        matric_o, matric_t = num("matric_obtained", _("Matric marks")), num("matric_total", _("Matric total")) or 1100
        inter_o, inter_t = num("inter_obtained", _("Intermediate marks")), num("inter_total", _("Intermediate total")) or 1100
        if not 0 <= matric_o <= matric_t:
            errors["matric_obtained"] = _("Matric marks must be between 0 and the total.")
        if not 0 <= inter_o <= inter_t:
            errors["inter_obtained"] = _("Intermediate marks must be between 0 and the total.")

        Admission = request.env["op.admission"].sudo()
        if email and not errors and Admission.search_count([("register_id", "=", register.id), ("email", "=ilike", email),
                                                            ("state", "not in", ["cancel", "reject"])]):
            errors["email"] = _("You have already applied with this email. Use Check my application to see your status.")
        if errors:
            values["errors"] = errors
            return request.render("icterp_edu_admission.page_admission_form", values)

        admission = Admission.create({
            "register_id": register.id, "course_id": course.id, "batch_id": False,
            "first_name": first, "middle_name": (post.get("middle_name") or "").strip() or False, "last_name": last,
            "name": " ".join(p for p in [first, (post.get("middle_name") or "").strip(), last] if p),
            "email": email, "mobile": mobile, "phone": mobile, "gender": gender, "birth_date": birth,
            "street": (post.get("street") or "").strip()[:200] or False, "city": (post.get("city") or "").strip()[:64] or False,
            "prev_institute_id": (post.get("prev_institute") or "").strip()[:200] or False,
            "matric_obtained": matric_o, "matric_total": matric_t, "inter_obtained": inter_o, "inter_total": inter_t,
            "board_name": (post.get("board_name") or "").strip()[:100] or False,
            "passing_year": (post.get("passing_year") or "").strip()[:10] or False,
            "hafiz": bool(post.get("hafiz")), "application_date": fields.Datetime.now(), "applied_online": True,
        })
        admission.submit_form()
        return request.render("icterp_edu_admission.page_admission_thanks", {"admission": admission})

    # ------------------------------------------------------------------ status
    @http.route(["/admission/status"], type="http", auth="public", website=True, methods=["GET", "POST"], sitemap=False)
    def admission_status_lookup(self, **post):
        error = False
        if request.httprequest.method == "POST":
            number = (post.get("application_number") or "").strip()
            email = (post.get("email") or "").strip().lower()
            a = request.env["op.admission"].sudo().search([("application_number", "=", number), ("email", "=ilike", email)], limit=1)
            if a:
                return request.redirect(a.status_url())
            error = _("No application matches that number and email.")
        return request.render("icterp_edu_admission.page_admission_lookup", {"error": error})

    def _by_token(self, admission_id, token):
        a = request.env["op.admission"].sudo().browse(admission_id).exists()
        if not a or not token or not a.access_token or not _consteq(a.access_token, token):
            raise request.not_found()
        return a

    @http.route(["/admission/status/<int:admission_id>/<string:token>"], type="http", auth="public", website=True, sitemap=False)
    def admission_status(self, admission_id, token, **kw):
        return request.render("icterp_edu_admission.page_admission_status", {"admission": self._by_token(admission_id, token)})

    @http.route(["/admission/status/<int:admission_id>/<string:token>/admit-card"], type="http", auth="public", website=True, sitemap=False)
    def admission_admit_card(self, admission_id, token, **kw):
        a = self._by_token(admission_id, token)
        if not a.test_roll_no:
            raise request.not_found()
        return self._pdf("icterp_edu_admission.action_report_admit_card", a, "Admit card %s.pdf" % a.test_roll_no)

    @http.route(["/admission/status/<int:admission_id>/<string:token>/challan"], type="http", auth="public", website=True, sitemap=False)
    def admission_challan(self, admission_id, token, **kw):
        a = self._by_token(admission_id, token)
        if not a.admission_challan_id:
            raise request.not_found()
        return self._pdf("icterp_edu_fee_challan.action_report_challan", a.admission_challan_id, "Challan %s.pdf" % a.admission_challan_id.name)

    def _pdf(self, report, records, name):
        pdf, _t = request.env["ir.actions.report"].sudo()._render_qweb_pdf(report, records.ids)
        return request.make_response(pdf, headers=[("Content-Type", "application/pdf"), ("Content-Length", len(pdf)),
                                                   ("Content-Disposition", http.content_disposition(name))])


def _consteq(a, b):
    import hmac
    return hmac.compare_digest(str(a), str(b))
