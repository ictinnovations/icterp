from odoo import fields, models


class OpSubject(models.Model):
    _inherit = "op.subject"

    credit_hours = fields.Float(default=3.0, help="Credit hours used for GPA and the credit load limits.")
    prerequisite_ids = fields.Many2many(
        "op.subject", "icterp_subject_prerequisite_rel", "subject_id", "prerequisite_id",
        string="Prerequisites", help="The student must have passed these before enrolling.")
