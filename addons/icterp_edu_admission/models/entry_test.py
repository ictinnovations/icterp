"""Entry test sitting: roll numbers, rooms, admit cards and marks."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class IcterpEntryTest(models.Model):
    _name = "icterp.entry.test"
    _description = "Admission entry test"
    _inherit = ["mail.thread"]
    _order = "date desc, id desc"

    name = fields.Char(required=True)
    register_id = fields.Many2one("op.admission.register", required=True, ondelete="cascade")
    date = fields.Date(required=True)
    start_time = fields.Float(default=10.0)
    duration = fields.Float(default=2.0)
    room_ids = fields.Many2many("op.classroom", string="Rooms")
    total_marks = fields.Float(default=100.0, required=True)
    roll_prefix = fields.Char(default="ET", help="Roll numbers look like ET-0001.")
    state = fields.Selection([("draft", "Draft"), ("scheduled", "Roll numbers issued"), ("done", "Marks entered")],
                             default="draft", required=True, tracking=True)
    admission_ids = fields.One2many("op.admission", "entry_test_id", string="Candidates")
    candidate_count = fields.Integer(compute="_compute_count")
    instructions = fields.Text(default="Bring this admit card and your CNIC or B-form. No phones or calculators.")

    def _compute_count(self):
        for t in self:
            t.candidate_count = len(t.admission_ids)

    def action_assign(self):
        """Give every applicant of the register without a test a roll number and a room."""
        for t in self:
            pending = t.register_id._applicants().filtered(lambda a: not a.entry_test_id).sorted(lambda a: (a.application_date, a.id))
            if not pending and not t.admission_ids:
                raise UserError(_("There are no applicants to schedule."))
            seats = sum(t.room_ids.mapped("capacity"))
            if t.room_ids and len(t.admission_ids) + len(pending) > seats:
                raise UserError(_("%(n)s candidates but only %(s)s seats in the rooms of %(test)s.",
                                  n=len(t.admission_ids) + len(pending), s=seats, test=t.name))
            # fill rooms in order, continuing after the candidates already placed
            rooms = list(t.room_ids.sorted("name"))
            used = {r.id: len(t.admission_ids.filtered(lambda a, r=r: a.test_room_id == r)) for r in rooms}
            number = len(t.admission_ids)
            for a in pending:
                number += 1
                room = next((r for r in rooms if used[r.id] < r.capacity), False)
                if room:
                    used[room.id] += 1
                a.write({"entry_test_id": t.id, "test_roll_no": "%s-%04d" % (t.roll_prefix or "ET", number),
                         "test_room_id": room.id if room else False})
            t.state = "scheduled"
        return True

    def action_done(self):
        for t in self:
            missing = t.admission_ids.filtered(lambda a: not a.test_taken)
            if missing:
                raise UserError(_("Enter test marks for: %s (use 0 for absent).", ", ".join(missing.mapped("name")[:20])))
            t.state = "done"

    def action_print_admit_cards(self):
        return self.env.ref("icterp_edu_admission.action_report_admit_card").report_action(self.admission_ids)

    def time_label(self):
        h, m = int(self.start_time), int(round((self.start_time % 1) * 60))
        return "%02d:%02d" % (h, m)
