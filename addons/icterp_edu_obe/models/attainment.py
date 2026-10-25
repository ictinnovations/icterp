"""CLO and PLO attainment.

Per student per CLO (one course offering):
    percent = marks obtained / marks available, over every question mapped to the CLO plus every
    assessment mapped to the CLO as a whole (only assessments without questions).
    attained = percent >= student threshold (Settings, default 50%).
Per class per CLO:
    attained when the share of students who attained it >= class threshold (default 60%).
Per student per PLO (across all their courses with computed attainment):
    percent = marks obtained / marks available over every CLO mapped to that PLO.
Absent counts as zero; a student with no marks available for a CLO is not counted for it.
"""
from collections import defaultdict

from odoo import _, api, fields, models


def _param(env, key, default):
    return float(env["ir.config_parameter"].sudo().get_param("icterp_edu_obe." + key, default) or default)


class IcterpObeStudentClo(models.Model):
    _name = "icterp.obe.student.clo"
    _description = "Student CLO attainment"
    _order = "offering_id, student_id, clo_id"

    offering_id = fields.Many2one("icterp.course.offering", required=True, ondelete="cascade", index=True)
    student_id = fields.Many2one("op.student", required=True, ondelete="cascade", index=True)
    clo_id = fields.Many2one("icterp.obe.clo", required=True, ondelete="cascade", index=True)
    obtained = fields.Float(digits=(8, 2))
    available = fields.Float(digits=(8, 2))
    percent = fields.Float(digits=(5, 2))
    attained = fields.Boolean()


class IcterpObeClassClo(models.Model):
    _name = "icterp.obe.class.clo"
    _description = "Class CLO attainment"
    _order = "offering_id, clo_id"

    offering_id = fields.Many2one("icterp.course.offering", required=True, ondelete="cascade", index=True)
    term_id = fields.Many2one(related="offering_id.term_id", store=True)
    clo_id = fields.Many2one("icterp.obe.clo", required=True, ondelete="cascade")
    level = fields.Selection(related="clo_id.level")
    plo_codes = fields.Char(compute="_compute_plo_codes")
    students_assessed = fields.Integer()
    students_attained = fields.Integer()
    percent_attained = fields.Float(string="% students attaining", digits=(5, 1))
    average_percent = fields.Float(string="Average score %", digits=(5, 1))
    attained = fields.Boolean()

    def _compute_plo_codes(self):
        for r in self:
            plos = r.clo_id.plo_ids.filtered(lambda p: p.course_id == r.offering_id.course_id)
            r.plo_codes = ", ".join(plos.mapped("code"))

    @api.model
    def _items(self, offering):
        """(clo, kind, record, max) for every mapped question, and whole assessments mapped to a CLO."""
        items = []
        for comp in offering.component_ids:
            if comp.question_ids:
                for q in comp.question_ids.filtered("clo_id"):
                    items.append((q.clo_id, "question", q, q.max_marks))
            elif comp.clo_id:
                items.append((comp.clo_id, "component", comp, comp.max_marks))
        return items

    @api.model
    def _compute_for(self, offerings):
        StudentClo = self.env["icterp.obe.student.clo"].sudo()
        student_cut = _param(self.env, "student_threshold", 50.0)
        class_cut = _param(self.env, "class_threshold", 60.0)
        for offering in offerings:
            StudentClo.search([("offering_id", "=", offering.id)]).unlink()
            self.sudo().search([("offering_id", "=", offering.id)]).unlink()
            items = self._items(offering)
            marks = self.env["icterp.assessment.mark"].sudo().search([("offering_id", "=", offering.id)])
            by_comp = {(m.component_id.id, m.enrollment_id.id): m for m in marks}
            qmarks = {}
            for m in marks:
                for qm in m.question_mark_ids:
                    qmarks[(qm.question_id.id, m.enrollment_id.id)] = qm.marks
            per_clo = defaultdict(list)
            for enr in offering._active_enrollments():
                totals = defaultdict(lambda: [0.0, 0.0])
                for clo, kind, rec, maximum in items:
                    if kind == "question":
                        mark = by_comp.get((rec.component_id.id, enr.id))
                        if not mark:
                            continue
                        got = 0.0 if mark.absent else qmarks.get((rec.id, enr.id), 0.0)
                    else:
                        mark = by_comp.get((rec.id, enr.id))
                        if not mark:
                            continue
                        got = 0.0 if mark.absent else mark.marks
                    totals[clo.id][0] += got
                    totals[clo.id][1] += maximum
                for clo_id, (got, avail) in totals.items():
                    if not avail:
                        continue
                    pct = round(100.0 * got / avail, 2)
                    StudentClo.create({"offering_id": offering.id, "student_id": enr.student_id.id, "clo_id": clo_id,
                                       "obtained": got, "available": avail, "percent": pct, "attained": pct >= student_cut})
                    per_clo[clo_id].append(pct)
            for clo in offering.subject_id.clo_ids:
                scores = per_clo.get(clo.id, [])
                n_ok = len([p for p in scores if p >= student_cut])
                share = round(100.0 * n_ok / len(scores), 1) if scores else 0.0
                self.sudo().create({"offering_id": offering.id, "clo_id": clo.id, "students_assessed": len(scores),
                                    "students_attained": n_ok, "percent_attained": share,
                                    "average_percent": round(sum(scores) / len(scores), 1) if scores else 0.0,
                                    "attained": bool(scores) and share >= class_cut})
            offering.sudo().obe_computed_on = fields.Datetime.now()
        return True


class IcterpObeStudentPlo(models.Model):
    _name = "icterp.obe.student.plo"
    _description = "Student PLO attainment"
    _order = "student_id, plo_id"

    student_id = fields.Many2one("op.student", required=True, ondelete="cascade", index=True)
    plo_id = fields.Many2one("icterp.obe.plo", required=True, ondelete="cascade", index=True)
    course_id = fields.Many2one(related="plo_id.course_id", store=True)
    obtained = fields.Float(digits=(8, 2))
    available = fields.Float(digits=(8, 2))
    percent = fields.Float(digits=(5, 2))
    attained = fields.Boolean()
    clo_count = fields.Integer(string="CLOs counted")

    _uniq = models.Constraint("unique(student_id, plo_id)", "One PLO result per student.")

    @api.model
    def _compute_for(self, students):
        cut = _param(self.env, "student_threshold", 50.0)
        rows = self.env["icterp.obe.student.clo"].sudo().search([("student_id", "in", students.ids)])
        for student in students:
            self.sudo().search([("student_id", "=", student.id)]).unlink()
            totals = defaultdict(lambda: [0.0, 0.0, 0])
            for r in rows.filtered(lambda x: x.student_id == student):
                for plo in r.clo_id.plo_ids.filtered(lambda p: p.course_id == r.offering_id.course_id):
                    totals[plo.id][0] += r.obtained
                    totals[plo.id][1] += r.available
                    totals[plo.id][2] += 1
            for plo_id, (got, avail, n) in totals.items():
                if avail:
                    pct = round(100.0 * got / avail, 2)
                    self.sudo().create({"student_id": student.id, "plo_id": plo_id, "obtained": got, "available": avail,
                                        "percent": pct, "attained": pct >= cut, "clo_count": n})
        return True


class OpStudent(models.Model):
    _inherit = "op.student"

    plo_attainment_ids = fields.One2many("icterp.obe.student.plo", "student_id", string="PLO attainment")
