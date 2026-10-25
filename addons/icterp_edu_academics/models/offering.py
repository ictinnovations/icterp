"""A course offering: one subject taught to one batch/section in one term.

Result workflow:
  draft -> open (students can be enrolled) -> verified (marks complete, weights total 100)
  -> published (grades fixed, term GPA/CGPA recomputed, visible in the portal).
A published offering can be reverted to verified by a manager, with a reason in the chatter.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class IcterpCourseOffering(models.Model):
    _name = "icterp.course.offering"
    _description = "Course offering"
    _inherit = ["mail.thread"]
    _order = "term_id desc, subject_id, section"

    name = fields.Char(compute="_compute_name", store=True)
    term_id = fields.Many2one("op.academic.term", required=True, index=True, tracking=True)
    course_id = fields.Many2one("op.course", string="Course / programme", required=True, tracking=True)
    batch_id = fields.Many2one("op.batch", tracking=True)
    subject_id = fields.Many2one("op.subject", required=True, index=True, tracking=True)
    section = fields.Char(default="A", required=True)
    faculty_id = fields.Many2one("op.faculty", string="Teacher", tracking=True)
    faculty_user_id = fields.Many2one("res.users", compute="_compute_faculty_user", store=True, index=True,
                                      help="The teacher's login: may enter marks for this course.")
    credit_hours = fields.Float(tracking=True)
    capacity = fields.Integer(default=50, help="0 = no limit.")
    classroom_id = fields.Many2one("op.classroom", string="Room")
    grade_scale_id = fields.Many2one(
        "icterp.grade.scale", required=True,
        default=lambda self: self.env.ref("icterp_edu_academics.grade_scale_hec", raise_if_not_found=False))
    state = fields.Selection(
        [("draft", "Draft"), ("open", "Open"), ("verified", "Results verified"), ("published", "Results published")],
        default="draft", required=True, tracking=True)
    enrollment_ids = fields.One2many("icterp.enrollment", "offering_id", string="Students")
    component_ids = fields.One2many("icterp.assessment.component", "offering_id", string="Assessments")
    enrolled_count = fields.Integer(compute="_compute_counts", store=True)
    weight_total = fields.Float(compute="_compute_weight_total", string="Weights total (%)")
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    _uniq = models.Constraint("unique(term_id, subject_id, batch_id, section)",
                              "This subject is already offered to that batch and section in this term.")

    @api.depends("subject_id", "section", "term_id", "batch_id")
    def _compute_name(self):
        for o in self:
            parts = [o.subject_id.code or o.subject_id.name or "", o.batch_id.code or "", o.section or "", o.term_id.name or ""]
            o.name = " / ".join(p for p in parts if p)

    @api.depends("faculty_id.user_id", "faculty_id.partner_id.user_ids")
    def _compute_faculty_user(self):
        for o in self:
            # OpenEduCat links a teacher to a login through the partner's user_id; a portal or
            # internal user created on the teacher's contact also counts.
            o.faculty_user_id = o.faculty_id.user_id or o.faculty_id.partner_id.user_ids[:1]

    @api.depends("enrollment_ids.state")
    def _compute_counts(self):
        for o in self:
            o.enrolled_count = len(o.enrollment_ids.filtered(lambda e: e.state in ("enrolled", "completed")))

    @api.depends("component_ids.weight")
    def _compute_weight_total(self):
        for o in self:
            o.weight_total = sum(o.component_ids.mapped("weight"))

    @api.onchange("subject_id")
    def _onchange_subject(self):
        if self.subject_id and not self.credit_hours:
            self.credit_hours = self.subject_id.credit_hours

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("credit_hours") and vals.get("subject_id"):
                vals["credit_hours"] = self.env["op.subject"].browse(vals["subject_id"]).credit_hours
        return super().create(vals_list)

    @api.constrains("credit_hours")
    def _check_credits(self):
        for o in self:
            if o.credit_hours < 0:
                raise ValidationError(_("Credit hours cannot be negative."))

    # ------------------------------------------------------------------ workflow
    def action_open(self):
        self.write({"state": "open"})

    def _active_enrollments(self):
        return self.enrollment_ids.filtered(lambda e: e.state in ("enrolled", "completed"))

    def action_verify(self):
        for o in self:
            if abs(o.weight_total - 100.0) > 0.01:
                raise UserError(_("%(name)s: assessment weights add up to %(total)s%%, they must total 100%%.",
                                  name=o.name, total=round(o.weight_total, 2)))
            missing = []
            for enr in o._active_enrollments():
                have = set(enr.mark_ids.mapped("component_id").ids)
                for comp in o.component_ids:
                    if comp.id not in have:
                        missing.append("%s: %s" % (enr.student_id.name, comp.name))
            if missing:
                raise UserError(_("Marks are missing for:\n%s", "\n".join(missing[:30])))
            o.state = "verified"

    def action_publish(self):
        terms = self.env["icterp.term.result"]
        for o in self:
            if o.state != "verified":
                raise UserError(_("Verify the results of %s before publishing them.", o.name))
            enrollments = o._active_enrollments()
            enrollments._fix_grade()
            enrollments.write({"state": "completed"})
            o.state = "published"
            o.message_post(body=_("Results published for %s students.", len(enrollments)))
            terms._recompute_for(enrollments.mapped("student_id"), o.term_id)
            o._notify_parents(enrollments)
        return True

    def _notify_parents(self, enrollments):
        """If parent alerts are installed, queue a results alert per student."""
        if "icterp.edu.alert" not in self.env:
            return
        Alert = self.env["icterp.edu.alert"]
        for enr in enrollments:
            detail = _("%(subject)s: %(grade)s (%(pct).0f%%)", subject=self.subject_id.name, grade=enr.grade_letter or "-",
                       pct=enr.percentage)
            Alert._enqueue(enr.student_id, "result", detail, "offering:%s:%s" % (self.id, enr.id))

    def action_revert(self):
        for o in self:
            if o.state != "published":
                continue
            o.state = "verified"
            o.enrollment_ids.filtered(lambda e: e.state == "completed").write({"state": "enrolled"})
            o.message_post(body=_("Results unpublished by %s.", self.env.user.name))
            self.env["icterp.term.result"]._recompute_for(o.enrollment_ids.mapped("student_id"), o.term_id)

    def action_reset_draft(self):
        self.filtered(lambda o: o.state in ("open", "verified")).write({"state": "draft"})

    def action_bulk_enroll(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "res_model": "icterp.bulk.enroll", "view_mode": "form", "target": "new",
            "context": {"default_offering_id": self.id},
        }
