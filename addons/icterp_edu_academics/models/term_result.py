"""Term GPA, CGPA and academic standing, one row per student per term.

GPA  = sum(grade points x credit hours) / sum(credit hours) over the term's completed courses
       from published offerings (withdrawn courses are excluded).
CGPA = the same over every term up to and including this one, counting only the latest
       attempt of a repeated subject.
Standing (thresholds in Settings): CGPA below the probation line -> probation; probation in N
consecutive terms -> suspension; below the warning line -> warning; otherwise good standing.
"""
from odoo import _, api, fields, models

STANDING = [("good", "Good standing"), ("warning", "Warning"), ("probation", "Probation"), ("suspension", "Suspension")]


class IcterpTermResult(models.Model):
    _name = "icterp.term.result"
    _description = "Term result"
    _order = "student_id, term_start desc"
    _rec_name = "term_id"

    student_id = fields.Many2one("op.student", required=True, index=True, ondelete="cascade")
    term_id = fields.Many2one("op.academic.term", required=True, index=True, ondelete="cascade")
    term_start = fields.Date(related="term_id.term_start_date", store=True)
    credits_attempted = fields.Float(digits=(6, 1))
    credits_earned = fields.Float(digits=(6, 1))
    quality_points = fields.Float(digits=(8, 2))
    gpa = fields.Float(string="GPA", digits=(4, 2))
    cumulative_credits = fields.Float(digits=(6, 1))
    cgpa = fields.Float(string="CGPA", digits=(4, 2))
    standing = fields.Selection(STANDING, default="good")

    _uniq = models.Constraint("unique(student_id, term_id)", "One result per student per term.")

    def _param(self, key, default):
        return float(self.env["ir.config_parameter"].sudo().get_param("icterp_edu_academics." + key, default) or default)

    @api.model
    def _counted(self, enrollments):
        return enrollments.filtered(lambda e: e.state == "completed" and e.published)

    @api.model
    def _recompute_for(self, students, from_term=None):
        """Rebuild every term row for these students (later terms depend on earlier ones)."""
        Enr = self.env["icterp.enrollment"].sudo()
        warn_below = self._param("warning_below", 2.2)
        prob_below = self._param("probation_below", 2.0)
        susp_after = int(self._param("suspension_after", 2))
        for student in students:
            all_enr = self._counted(Enr.search([("student_id", "=", student.id)]))
            terms = all_enr.mapped("term_id").sorted(lambda t: (t.term_start_date, t.id))
            stale = self.search([("student_id", "=", student.id), ("term_id", "not in", terms.ids)])
            stale.unlink()
            probation_run = 0
            for term in terms:
                in_term = all_enr.filtered(lambda e: e.term_id == term)
                att = sum(in_term.mapped("credit_hours"))
                qp = sum(e.grade_points * e.credit_hours for e in in_term)
                earned = sum(in_term.filtered("is_pass").mapped("credit_hours"))
                upto = all_enr.filtered(lambda e: (e.term_id.term_start_date, e.term_id.id) <= (term.term_start_date, term.id))
                latest = {}
                for e in upto.sorted(lambda r: (r.term_id.term_start_date, r.term_id.id)):
                    latest[e.subject_id.id] = e  # later attempts replace earlier ones
                cum_att = sum(e.credit_hours for e in latest.values())
                cum_qp = sum(e.grade_points * e.credit_hours for e in latest.values())
                gpa = round(qp / att, 2) if att else 0.0
                cgpa = round(cum_qp / cum_att, 2) if cum_att else 0.0
                if cum_att and cgpa < prob_below:
                    probation_run += 1
                    standing = "suspension" if probation_run >= susp_after else "probation"
                else:
                    probation_run = 0
                    standing = "warning" if cum_att and cgpa < warn_below else "good"
                vals = {"credits_attempted": att, "credits_earned": earned, "quality_points": round(qp, 2), "gpa": gpa,
                        "cumulative_credits": cum_att, "cgpa": cgpa, "standing": standing}
                row = self.search([("student_id", "=", student.id), ("term_id", "=", term.id)], limit=1)
                if row:
                    row.write(vals)
                else:
                    self.create(dict(vals, student_id=student.id, term_id=term.id))
        return True
