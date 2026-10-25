from odoo import api, fields, models


class OpStudent(models.Model):
    _inherit = "op.student"

    enrollment_ids = fields.One2many("icterp.enrollment", "student_id", string="Course registrations")
    term_result_ids = fields.One2many("icterp.term.result", "student_id", string="Term results")
    cgpa = fields.Float(string="CGPA", compute="_compute_cgpa", digits=(4, 2))
    academic_standing = fields.Selection(
        [("good", "Good standing"), ("warning", "Warning"), ("probation", "Probation"), ("suspension", "Suspension")],
        string="Standing", compute="_compute_cgpa")
    transcript_serial = fields.Char(copy=False, readonly=True)

    @api.depends("term_result_ids.cgpa", "term_result_ids.standing", "term_result_ids.term_start")
    def _compute_cgpa(self):
        for s in self:
            latest = s.term_result_ids.sorted("term_start", reverse=True)[:1]
            s.cgpa = latest.cgpa if latest else 0.0
            s.academic_standing = latest.standing if latest else False

    def _transcript_terms(self):
        """[(term, [enrollments], term_result)] in term order, published results only."""
        self.ensure_one()
        enr = self.enrollment_ids.filtered(lambda e: e.published and e.state in ("completed", "withdrawn"))
        out = []
        for term in enr.mapped("term_id").sorted(lambda t: (t.term_start_date, t.id)):
            rows = enr.filtered(lambda e: e.term_id == term).sorted(lambda e: e.subject_id.code or "")
            result = self.term_result_ids.filtered(lambda r: r.term_id == term)[:1]
            out.append((term, rows, result))
        return out

    def action_print_transcript(self):
        for s in self.filtered(lambda r: not r.transcript_serial):
            s.transcript_serial = self.env["ir.sequence"].next_by_code("icterp.transcript")
        return self.env.ref("icterp_edu_academics.action_report_transcript").report_action(self)
