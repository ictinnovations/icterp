"""A student's registration in a course offering, and the grade that comes out of it.

Rules checked on enrolment (managers can override with the context key icterp_force_enroll):
  - the offering is open and has seats;
  - the student passed every prerequisite subject;
  - the term's credit load stays within the course's maximum unit load (when one is set);
  - the student is not already enrolled in the same subject this term.
Drop before the term's drop deadline removes the course; withdraw before the withdraw deadline
leaves a W that does not count in the GPA.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class IcterpEnrollment(models.Model):
    _name = "icterp.enrollment"
    _description = "Course registration"
    _inherit = ["mail.thread"]
    _order = "term_id desc, student_id, subject_id"
    _rec_name = "offering_id"

    student_id = fields.Many2one("op.student", required=True, index=True, ondelete="cascade")
    offering_id = fields.Many2one("icterp.course.offering", required=True, index=True, ondelete="restrict")
    term_id = fields.Many2one(related="offering_id.term_id", store=True, index=True)
    subject_id = fields.Many2one(related="offering_id.subject_id", store=True, index=True)
    credit_hours = fields.Float(related="offering_id.credit_hours", store=True)
    state = fields.Selection(
        [("enrolled", "Enrolled"), ("dropped", "Dropped"), ("withdrawn", "Withdrawn"), ("completed", "Completed")],
        default="enrolled", required=True, tracking=True, index=True)
    enrolled_on = fields.Date(default=fields.Date.context_today)
    changed_on = fields.Date(string="Dropped / withdrawn on")
    is_repeat = fields.Boolean(compute="_compute_is_repeat", store=True,
                               help="The student took this subject in an earlier term. Only the latest attempt counts in the CGPA.")
    mark_ids = fields.One2many("icterp.assessment.mark", "enrollment_id", string="Marks")

    percentage = fields.Float(compute="_compute_result", store=True, digits=(5, 2))
    grade_letter = fields.Char(compute="_compute_result", store=True)
    grade_points = fields.Float(compute="_compute_result", store=True, digits=(4, 2))
    is_pass = fields.Boolean(compute="_compute_result", store=True)
    grade_override = fields.Char(tracking=True, help="Set by a grade change, with the reason in the chatter.")
    grade_override_points = fields.Float(digits=(4, 2), tracking=True)
    quality_points = fields.Float(compute="_compute_quality", store=True, digits=(6, 2))
    published = fields.Boolean(compute="_compute_published", store=True)

    _uniq = models.Constraint("unique(student_id, offering_id)", "The student is already registered in this course.")

    @api.depends("student_id", "subject_id", "term_id.term_start_date")
    def _compute_is_repeat(self):
        for e in self:
            if not (e.student_id and e.subject_id and e.term_id):
                e.is_repeat = False
                continue
            earlier = self.search_count([
                ("id", "!=", e._origin.id or 0), ("student_id", "=", e.student_id.id), ("subject_id", "=", e.subject_id.id),
                ("state", "=", "completed"), ("term_id.term_start_date", "<", e.term_id.term_start_date)])
            e.is_repeat = bool(earlier)

    @api.depends("mark_ids.marks", "mark_ids.absent", "offering_id.component_ids.weight",
                 "offering_id.component_ids.max_marks", "offering_id.grade_scale_id", "state",
                 "grade_override", "grade_override_points")
    def _compute_result(self):
        for e in self:
            if e.state == "withdrawn":
                e.percentage, e.grade_letter, e.grade_points, e.is_pass = 0.0, "W", 0.0, False
                continue
            pct = 0.0
            for m in e.mark_ids:
                comp = m.component_id
                if comp.max_marks and not m.absent:
                    pct += (m.marks / comp.max_marks) * comp.weight
            e.percentage = round(pct, 2)
            if e.grade_override:
                e.grade_letter = e.grade_override
                e.grade_points = e.grade_override_points
                band = e.offering_id.grade_scale_id.line_ids.filtered(lambda l: l.letter == e.grade_override)[:1]
                e.is_pass = band.is_pass if band else e.grade_override_points > 0
                continue
            band = e.offering_id.grade_scale_id._grade_for(e.percentage) if e.offering_id.grade_scale_id else False
            e.grade_letter = band.letter if band else False
            e.grade_points = band.points if band else 0.0
            e.is_pass = bool(band and band.is_pass)

    @api.depends("grade_points", "credit_hours", "state")
    def _compute_quality(self):
        for e in self:
            e.quality_points = e.grade_points * e.credit_hours if e.state in ("enrolled", "completed") else 0.0

    @api.depends("offering_id.state")
    def _compute_published(self):
        for e in self:
            e.published = e.offering_id.state == "published"

    def _fix_grade(self):
        """Force the stored grade to be recomputed (used at publish time)."""
        self._compute_result()
        self._compute_quality()

    # ------------------------------------------------------------------ rules
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get("icterp_force_enroll"):
            records._check_enrollment_rules()
        return records

    def _passed_subjects(self, student):
        done = self.search([("student_id", "=", student.id), ("state", "=", "completed"), ("is_pass", "=", True)])
        return done.mapped("subject_id")

    def _check_enrollment_rules(self):
        for e in self:
            o = e.offering_id
            if o.state != "open":
                raise ValidationError(_("%s is not open for registration.", o.name))
            if o.capacity and o.enrolled_count > o.capacity:
                raise ValidationError(_("%(name)s is full (%(cap)s seats).", name=o.name, cap=o.capacity))
            missing = o.subject_id.prerequisite_ids - self._passed_subjects(e.student_id)
            if missing:
                raise ValidationError(_("%(student)s has not passed the prerequisite(s) for %(subject)s: %(list)s.",
                                        student=e.student_id.name, subject=o.subject_id.name,
                                        list=", ".join(missing.mapped("name"))))
            twin = self.search([("id", "!=", e.id), ("student_id", "=", e.student_id.id), ("term_id", "=", e.term_id.id),
                                ("subject_id", "=", e.subject_id.id), ("state", "in", ["enrolled", "completed"])], limit=1)
            if twin:
                raise ValidationError(_("%(student)s is already registered in %(subject)s this term.",
                                        student=e.student_id.name, subject=e.subject_id.name))
            max_load = o.course_id.max_unit_load
            if max_load:
                load = sum(self.search([("student_id", "=", e.student_id.id), ("term_id", "=", e.term_id.id),
                                        ("state", "in", ["enrolled", "completed"])]).mapped("credit_hours"))
                if load > max_load + 1e-9:
                    raise ValidationError(_("%(student)s would carry %(load)s credit hours this term; the maximum for %(course)s is %(max)s.",
                                            student=e.student_id.name, load=load, course=o.course_id.name, max=max_load))

    def _today(self):
        return fields.Date.context_today(self)

    def action_drop(self):
        manager = self.env.user.has_group("openeducat_core.group_op_back_office_admin")
        for e in self:
            if e.state != "enrolled":
                raise UserError(_("Only an active registration can be dropped."))
            deadline = e.term_id.drop_deadline
            if deadline and self._today() > deadline and not manager:
                raise UserError(_("The drop deadline for %(term)s was %(date)s. Withdraw the course instead.",
                                  term=e.term_id.name, date=deadline))
            e.write({"state": "dropped", "changed_on": self._today()})

    def action_withdraw(self):
        manager = self.env.user.has_group("openeducat_core.group_op_back_office_admin")
        for e in self:
            if e.state != "enrolled":
                raise UserError(_("Only an active registration can be withdrawn."))
            deadline = e.term_id.withdraw_deadline
            if deadline and self._today() > deadline and not manager:
                raise UserError(_("The withdraw deadline for %(term)s was %(date)s.", term=e.term_id.name, date=deadline))
            e.write({"state": "withdrawn", "changed_on": self._today()})

    def action_reinstate(self):
        for e in self.filtered(lambda r: r.state in ("dropped", "withdrawn")):
            e.write({"state": "enrolled", "changed_on": False})
            e._check_enrollment_rules()
