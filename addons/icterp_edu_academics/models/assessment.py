"""Assessments and marks.

A component is one weighted piece of a course: quiz, assignment, midterm, final, project.
Marks are stored per student per component. A component can also be split into questions
(each with its own maximum, and in the OBE module its own CLO); then the component mark is the
sum of the question marks.

External sources: every mark records where it came from (`source`) and an `external_ref`.
`import_marks()` is the single entry point an external system uses, so ICTExam can push
results later without touching the screens: rows are matched to students by student id,
login/email or roll number, and re-imports update the same rows instead of duplicating them.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

SOURCES = [("manual", "Entered by hand"), ("import", "Imported file"), ("ictexam", "ICTExam")]


class IcterpAssessmentComponent(models.Model):
    _name = "icterp.assessment.component"
    _description = "Assessment"
    _order = "offering_id, sequence, id"

    offering_id = fields.Many2one("icterp.course.offering", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    type = fields.Selection([
        ("quiz", "Quiz"), ("assignment", "Assignment"), ("mid", "Midterm"), ("final", "Final exam"),
        ("project", "Project"), ("lab", "Lab"), ("presentation", "Presentation"), ("other", "Other")],
        default="quiz", required=True)
    max_marks = fields.Float(required=True, default=10.0)
    weight = fields.Float(string="Weight (%)", required=True, help="Share of the final percentage. All weights of a course total 100.")
    source = fields.Selection(SOURCES, default="manual", required=True,
                              help="Where the marks come from. ICTExam assessments are filled by import_marks().")
    external_ref = fields.Char(string="External ID", index=True, help="For example the ICTExam assessment ID.")
    question_ids = fields.One2many("icterp.assessment.question", "component_id", string="Questions")
    mark_ids = fields.One2many("icterp.assessment.mark", "component_id", string="Marks")
    locked = fields.Boolean(compute="_compute_locked")

    @api.depends("offering_id.state")
    def _compute_locked(self):
        for c in self:
            c.locked = c.offering_id.state in ("verified", "published")

    @api.constrains("max_marks", "weight")
    def _check_values(self):
        for c in self:
            if c.max_marks <= 0:
                raise ValidationError(_("Maximum marks must be more than zero."))
            if not 0 <= c.weight <= 100:
                raise ValidationError(_("A weight must be between 0 and 100."))

    @api.constrains("question_ids", "max_marks")
    def _check_questions_total(self):
        for c in self:
            if c.question_ids and abs(sum(c.question_ids.mapped("max_marks")) - c.max_marks) > 0.001:
                raise ValidationError(_("The questions of %(name)s add up to %(q)s marks but the assessment is out of %(m)s.",
                                        name=c.name, q=sum(c.question_ids.mapped("max_marks")), m=c.max_marks))

    # ------------------------------------------------------------------ import API
    def _find_enrollment(self, row):
        """Match a row to an active enrollment of this offering."""
        self.ensure_one()
        enrollments = self.offering_id._active_enrollments()
        if row.get("student_id"):
            hit = enrollments.filtered(lambda e: e.student_id.id == int(row["student_id"]))
            if hit:
                return hit[:1]
        key = (row.get("email") or row.get("login") or "").strip().lower()
        if key:
            hit = enrollments.filtered(lambda e: (e.student_id.email or "").lower() == key
                                       or (e.student_id.user_id.login or "").lower() == key)
            if hit:
                return hit[:1]
        roll = (row.get("roll_number") or "").strip()
        if roll:
            details = self.env["op.student.course"].sudo().search([("roll_number", "=", roll)])
            hit = enrollments.filtered(lambda e: e.student_id in details.mapped("student_id"))
            if hit:
                return hit[:1]
        return self.env["icterp.enrollment"]

    def import_marks(self, rows, source="import", external_ref=None):
        """Create or update marks from a list of dicts.

        row keys: one of student_id / email / login / roll_number to find the student,
        then `marks` (component total) or `questions` {question name or external_ref: marks},
        optional `absent` (bool) and `external_ref` (per row, e.g. ICTExam attempt id).
        Returns {"updated": n, "created": n, "unmatched": [rows]}.
        """
        self.ensure_one()
        if self.locked:
            raise UserError(_("%s is verified or published; unpublish it before importing marks.", self.name))
        Mark = self.env["icterp.assessment.mark"]
        QMark = self.env["icterp.assessment.question.mark"]
        result = {"updated": 0, "created": 0, "unmatched": []}
        if external_ref:
            self.write({"external_ref": external_ref, "source": source})
        for row in rows:
            enr = self._find_enrollment(row)
            if not enr:
                result["unmatched"].append(row)
                continue
            vals = {"source": source, "absent": bool(row.get("absent")),
                    "external_ref": row.get("external_ref") or False}
            mark = Mark.search([("component_id", "=", self.id), ("enrollment_id", "=", enr.id)], limit=1)
            if row.get("questions") and self.question_ids:
                if not mark:
                    mark = Mark.create(dict(vals, component_id=self.id, enrollment_id=enr.id, marks=0))
                    result["created"] += 1
                else:
                    mark.write(vals)
                    result["updated"] += 1
                for qkey, qmarks in row["questions"].items():
                    q = self.question_ids.filtered(lambda x: x.name == qkey or (x.external_ref and x.external_ref == str(qkey)))[:1]
                    if not q:
                        continue
                    qm = QMark.search([("mark_id", "=", mark.id), ("question_id", "=", q.id)], limit=1)
                    if qm:
                        qm.marks = qmarks
                    else:
                        QMark.create({"mark_id": mark.id, "question_id": q.id, "marks": qmarks})
                mark._sum_questions()
            else:
                vals["marks"] = float(row.get("marks") or 0.0)
                if mark:
                    mark.write(vals)
                    result["updated"] += 1
                else:
                    Mark.create(dict(vals, component_id=self.id, enrollment_id=enr.id))
                    result["created"] += 1
        return result


class IcterpAssessmentQuestion(models.Model):
    _name = "icterp.assessment.question"
    _description = "Assessment question"
    _order = "component_id, sequence, id"

    component_id = fields.Many2one("icterp.assessment.component", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True, help="For example Q1 or 2(b).")
    max_marks = fields.Float(required=True)
    external_ref = fields.Char(string="External ID", help="For example the ICTExam question ID.")


class IcterpAssessmentMark(models.Model):
    _name = "icterp.assessment.mark"
    _description = "Assessment mark"
    _order = "component_id, enrollment_id"

    component_id = fields.Many2one("icterp.assessment.component", required=True, ondelete="cascade", index=True)
    enrollment_id = fields.Many2one("icterp.enrollment", required=True, ondelete="cascade", index=True)
    student_id = fields.Many2one(related="enrollment_id.student_id", store=True)
    offering_id = fields.Many2one(related="component_id.offering_id", store=True)
    max_marks = fields.Float(related="component_id.max_marks")
    marks = fields.Float()
    absent = fields.Boolean()
    source = fields.Selection(SOURCES, default="manual", required=True)
    external_ref = fields.Char(string="External ID")
    question_mark_ids = fields.One2many("icterp.assessment.question.mark", "mark_id", string="Question marks")

    _uniq = models.Constraint("unique(component_id, enrollment_id)", "A student has one mark per assessment.")

    @api.constrains("marks", "component_id")
    def _check_marks(self):
        for m in self:
            if m.marks < 0 or m.marks > m.component_id.max_marks + 1e-9:
                raise ValidationError(_("%(student)s: %(marks)s is outside 0 to %(max)s for %(comp)s.",
                                        student=m.student_id.name, marks=m.marks, max=m.component_id.max_marks,
                                        comp=m.component_id.name))

    def _check_editable(self):
        if self.env.su or self.env.user.has_group("openeducat_core.group_op_back_office_admin"):
            locked_ok = self.env.context.get("icterp_grade_change")
        else:
            locked_ok = False
        for m in self:
            if m.component_id.locked and not locked_ok:
                raise UserError(_("Marks of %s are locked: the results are verified or published.", m.offering_id.name))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._check_editable()
        return records

    def write(self, vals):
        if set(vals) - {"question_mark_ids"}:
            self._check_editable()
        return super().write(vals)

    def _sum_questions(self):
        for m in self:
            if m.question_mark_ids:
                m.marks = sum(m.question_mark_ids.mapped("marks"))


class IcterpAssessmentQuestionMark(models.Model):
    _name = "icterp.assessment.question.mark"
    _description = "Question mark"

    mark_id = fields.Many2one("icterp.assessment.mark", required=True, ondelete="cascade", index=True)
    question_id = fields.Many2one("icterp.assessment.question", required=True, ondelete="cascade")
    marks = fields.Float()

    _uniq = models.Constraint("unique(mark_id, question_id)", "One mark per question.")

    @api.constrains("marks")
    def _check_marks(self):
        for q in self:
            if q.marks < 0 or q.marks > q.question_id.max_marks + 1e-9:
                raise ValidationError(_("%(q)s: %(m)s is outside 0 to %(max)s.", q=q.question_id.name, m=q.marks,
                                        max=q.question_id.max_marks))
