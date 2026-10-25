from odoo import fields, models


class OpAcademicTerm(models.Model):
    _inherit = "op.academic.term"

    registration_start = fields.Date(help="Students can be enrolled from this date.")
    registration_end = fields.Date(help="Last day to enrol. Managers can still enrol after it.")
    drop_deadline = fields.Date(help="Until this date a course can be dropped: it disappears from the transcript.")
    withdraw_deadline = fields.Date(help="Until this date a course can be withdrawn: it shows as W and does not count in the GPA.")
    offering_ids = fields.One2many("icterp.course.offering", "term_id", string="Course offerings")
