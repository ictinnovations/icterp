"""Programme Educational Objectives, Programme Learning Outcomes and Course Learning Outcomes."""
from odoo import _, api, fields, models

LEVELS = [
    ("C1", "C1 Remember"), ("C2", "C2 Understand"), ("C3", "C3 Apply"), ("C4", "C4 Analyse"), ("C5", "C5 Evaluate"), ("C6", "C6 Create"),
    ("P1", "P1 Perception"), ("P2", "P2 Set"), ("P3", "P3 Guided response"), ("P4", "P4 Mechanism"),
    ("P5", "P5 Complex response"), ("P6", "P6 Adaptation"), ("P7", "P7 Origination"),
    ("A1", "A1 Receive"), ("A2", "A2 Respond"), ("A3", "A3 Value"), ("A4", "A4 Organise"), ("A5", "A5 Characterise"),
]


class IcterpObePeo(models.Model):
    _name = "icterp.obe.peo"
    _description = "Programme educational objective"
    _order = "course_id, code"

    course_id = fields.Many2one("op.course", string="Programme", required=True, index=True)
    code = fields.Char(required=True, default="PEO1")
    description = fields.Text(required=True)

    @api.depends("code", "course_id")
    def _compute_display_name(self):
        for r in self:
            r.display_name = "%s %s" % (r.code, r.course_id.code or "")


class IcterpObePlo(models.Model):
    _name = "icterp.obe.plo"
    _description = "Programme learning outcome"
    _order = "course_id, sequence, code"

    course_id = fields.Many2one("op.course", string="Programme", required=True, index=True)
    sequence = fields.Integer(default=10)
    code = fields.Char(required=True, default="PLO1")
    name = fields.Char(string="Title", required=True, help="For example: Engineering knowledge, Problem analysis.")
    description = fields.Text()
    peo_ids = fields.Many2many("icterp.obe.peo", string="Supports PEOs", domain="[('course_id', '=', course_id)]")
    clo_ids = fields.Many2many("icterp.obe.clo", "icterp_obe_clo_plo_rel", "plo_id", "clo_id", string="Mapped CLOs")

    _uniq = models.Constraint("unique(course_id, code)", "PLO codes must be unique within a programme.")

    @api.depends("code", "name")
    def _compute_display_name(self):
        for r in self:
            r.display_name = "%s %s" % (r.code, r.name or "")


class IcterpObeClo(models.Model):
    _name = "icterp.obe.clo"
    _description = "Course learning outcome"
    _order = "subject_id, sequence, code"

    subject_id = fields.Many2one("op.subject", string="Subject", required=True, index=True)
    sequence = fields.Integer(default=10)
    code = fields.Char(required=True, default="CLO1")
    description = fields.Text(required=True, help="What the student can do, starting with a verb.")
    domain = fields.Selection([("cognitive", "Cognitive"), ("psychomotor", "Psychomotor"), ("affective", "Affective")],
                              default="cognitive", required=True)
    level = fields.Selection(LEVELS, string="Bloom level", required=True, default="C2")
    plo_ids = fields.Many2many("icterp.obe.plo", "icterp_obe_clo_plo_rel", "clo_id", "plo_id", string="Mapped PLOs")

    _uniq = models.Constraint("unique(subject_id, code)", "CLO codes must be unique within a subject.")

    @api.depends("code", "subject_id")
    def _compute_display_name(self):
        for r in self:
            r.display_name = "%s %s" % (r.subject_id.code or "", r.code)

    @api.onchange("domain")
    def _onchange_domain(self):
        prefix = {"cognitive": "C", "psychomotor": "P", "affective": "A"}[self.domain or "cognitive"]
        if not (self.level or "").startswith(prefix):
            self.level = prefix + "1"


class OpSubject(models.Model):
    _inherit = "op.subject"

    clo_ids = fields.One2many("icterp.obe.clo", "subject_id", string="CLOs")
