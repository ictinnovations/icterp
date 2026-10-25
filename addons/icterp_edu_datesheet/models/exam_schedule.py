"""Exam date sheet: when and where each course's paper is sat, who sits where, who invigilates.

A schedule (for example "Fall 2026 Finals") has one paper per course offering. Papers that
overlap in time form a slot; a slot's students share that slot's rooms.

- Clash check: a student with two overlapping papers, a teacher invigilating two places at once,
  a slot with more students than seats, a paper with no room.
- Seating: students of a slot are interleaved paper by paper (neighbours sit different papers)
  and filled into the slot's rooms up to each room's seats.
- Invigilation: per room per slot, max(minimum per room, students / students per invigilator)
  teachers, picked from teachers free at that time with the fewest duties so far.
"""
import math
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


def _hhmm(value):
    h = int(value or 0)
    m = int(round(((value or 0) - h) * 60))
    if m == 60:
        h, m = h + 1, 0
    return "%02d:%02d" % (h, m)


class IcterpExamSchedule(models.Model):
    _name = "icterp.exam.schedule"
    _description = "Exam date sheet"
    _inherit = ["mail.thread"]
    _order = "date_from desc, id desc"

    name = fields.Char(required=True)
    term_id = fields.Many2one("op.academic.term", required=True)
    kind = fields.Selection([("mid", "Midterm"), ("final", "Final"), ("supplementary", "Supplementary"), ("other", "Other")],
                            default="final", required=True)
    date_from = fields.Date()
    date_to = fields.Date()
    state = fields.Selection([("draft", "Draft"), ("published", "Published"), ("done", "Done")], default="draft",
                             required=True, tracking=True)
    paper_ids = fields.One2many("icterp.exam.paper", "schedule_id", string="Papers")
    seat_ids = fields.One2many("icterp.exam.seat", "schedule_id", string="Seats")
    duty_ids = fields.One2many("icterp.exam.duty", "schedule_id", string="Invigilation duties")
    min_invigilators = fields.Integer(string="Invigilators per room (minimum)", default=1)
    students_per_invigilator = fields.Integer(default=30)
    hold_unpaid = fields.Boolean(string="Hold slips for overdue fees",
                                 help="Students with an overdue fee challan cannot download their exam slip.")
    clash_report = fields.Text(readonly=True)
    clash_count = fields.Integer(readonly=True)

    # ------------------------------------------------------------------ helpers
    def _slots(self):
        """Group overlapping papers: [(date, start, end, papers)] in time order."""
        self.ensure_one()
        slots = []
        for paper in self.paper_ids.sorted(lambda p: (p.date, p.start_time)):
            for slot in slots:
                if slot[0] == paper.date and paper.start_time < slot[2] and slot[1] < paper.end_time:
                    slot[1], slot[2] = min(slot[1], paper.start_time), max(slot[2], paper.end_time)
                    slot[3] |= paper
                    break
            else:
                slots.append([paper.date, paper.start_time, paper.end_time, paper])
        return slots

    def _slot_label(self, slot):
        return "%s %s-%s" % (fields.Date.to_string(slot[0]), _hhmm(slot[1]), _hhmm(slot[2]))

    # ------------------------------------------------------------------ clashes
    def _find_clashes(self):
        self.ensure_one()
        problems = []
        papers = self.paper_ids
        for p in papers.filtered(lambda x: not x.room_ids):
            problems.append(_("%s has no room.", p.display_name))
        for i, a in enumerate(papers):
            for b in papers[i + 1:]:
                if not a._overlaps(b):
                    continue
                both = a._students() & b._students()
                for s in both:
                    problems.append(_("%(student)s sits %(a)s and %(b)s at the same time.",
                                      student=s.name, a=a.offering_id.subject_id.name, b=b.offering_id.subject_id.name))
        for slot in self._slots():
            students = sum(len(p._students()) for p in slot[3])
            seats = sum(slot[3].mapped("room_ids").mapped("capacity"))
            if slot[3].mapped("room_ids") and students > seats:
                problems.append(_("%(slot)s: %(n)s students but only %(seats)s seats.", slot=self._slot_label(slot),
                                  n=students, seats=seats))
        duties = self.duty_ids
        for i, a in enumerate(duties):
            for b in duties[i + 1:]:
                if a.faculty_id == b.faculty_id and a.date == b.date and a.start_time < b.end_time and b.start_time < a.end_time:
                    problems.append(_("%(t)s invigilates %(r1)s and %(r2)s at the same time.", t=a.faculty_id.name,
                                      r1=a.room_id.name, r2=b.room_id.name))
        return problems

    def action_check_clashes(self):
        for s in self:
            problems = s._find_clashes()
            s.clash_count = len(problems)
            s.clash_report = "\n".join(problems) if problems else _("No clashes found.")
        return True

    # ------------------------------------------------------------------ seating
    def action_generate_seating(self):
        Seat = self.env["icterp.exam.seat"]
        for sched in self:
            sched.seat_ids.unlink()
            for slot in sched._slots():
                papers = slot[3]
                rooms = papers.mapped("room_ids").sorted(lambda r: (r.code or r.name or ""))
                queues = [list(p._students().sorted("name")) for p in papers]
                queue_papers = list(papers)
                order = []  # round-robin so neighbours sit different papers
                while any(queues):
                    for idx, q in enumerate(queues):
                        if q:
                            order.append((queue_papers[idx], q.pop(0)))
                capacity = sum(rooms.mapped("capacity"))
                if len(order) > capacity:
                    raise UserError(_("%(slot)s: %(n)s students but only %(c)s seats in the rooms given.",
                                      slot=sched._slot_label(slot), n=len(order), c=capacity))
                pos = 0
                for room in rooms:
                    for seat_no in range(1, room.capacity + 1):
                        if pos >= len(order):
                            break
                        paper, student = order[pos]
                        Seat.create({"schedule_id": sched.id, "paper_id": paper.id, "student_id": student.id,
                                     "room_id": room.id, "seat_no": "%s-%02d" % (room.code or room.name, seat_no)})
                        pos += 1
            sched.message_post(body=_("Seating plan generated: %s seats.", len(sched.seat_ids)))
        return True

    # ------------------------------------------------------------------ invigilation
    def action_assign_invigilators(self):
        Duty = self.env["icterp.exam.duty"]
        Faculty = self.env["op.faculty"]
        for sched in self:
            if not sched.seat_ids:
                raise UserError(_("Generate the seating plan first: invigilators are assigned per room in use."))
            sched.duty_ids.unlink()
            load = defaultdict(int)
            teachers = Faculty.search([])
            if not teachers:
                raise UserError(_("Add teachers (faculty) first."))
            for slot in sched._slots():
                seats = sched.seat_ids.filtered(lambda s: s.paper_id in slot[3])
                busy = Faculty
                for room in seats.mapped("room_id").sorted("name"):
                    n_students = len(seats.filtered(lambda s: s.room_id == room))
                    need = max(sched.min_invigilators or 1,
                               math.ceil(n_students / max(sched.students_per_invigilator or 30, 1)))
                    free = (teachers - busy).sorted(lambda t: (load[t.id], t.name or ""))
                    if len(free) < need:
                        raise UserError(_("%(slot)s: not enough free teachers for room %(room)s.",
                                          slot=sched._slot_label(slot), room=room.name))
                    for t in free[:need]:
                        Duty.create({"schedule_id": sched.id, "date": slot[0], "start_time": slot[1], "end_time": slot[2],
                                     "room_id": room.id, "faculty_id": t.id})
                        load[t.id] += 1
                        busy |= t
        return True

    def action_publish(self):
        for s in self:
            s.action_check_clashes()
            if s.clash_count:
                raise UserError(_("Fix the clashes before publishing:\n%s", s.clash_report))
            s.state = "published"

    def action_done(self):
        self.write({"state": "done"})

    def action_draft(self):
        self.write({"state": "draft"})

    def action_print_datesheet(self):
        return self.env.ref("icterp_edu_datesheet.action_report_datesheet").report_action(self)

    def action_print_seating(self):
        return self.env.ref("icterp_edu_datesheet.action_report_seating").report_action(self)

    def _slip_held(self, student):
        """True when the student's slip is held for overdue fees (fee challan module installed)."""
        self.ensure_one()
        return bool(self.hold_unpaid and hasattr(student, "_unpaid_overdue_challans") and student._unpaid_overdue_challans())

    def _seats_by_room(self):
        """[(slot label, room, seats, duties)] for the seating plan report."""
        self.ensure_one()
        out = []
        for slot in self._slots():
            seats = self.seat_ids.filtered(lambda s: s.paper_id in slot[3])
            for room in seats.mapped("room_id").sorted("name"):
                duties = self.duty_ids.filtered(lambda d: d.room_id == room and d.date == slot[0]
                                                and d.start_time < slot[2] and slot[1] < d.end_time)
                out.append((self._slot_label(slot), room, seats.filtered(lambda s: s.room_id == room).sorted("seat_no"), duties))
        return out


class IcterpExamPaper(models.Model):
    _name = "icterp.exam.paper"
    _description = "Exam paper"
    _order = "date, start_time, id"

    schedule_id = fields.Many2one("icterp.exam.schedule", required=True, ondelete="cascade", index=True)
    offering_id = fields.Many2one("icterp.course.offering", required=True, domain="[('term_id', '=', term_id)]")
    term_id = fields.Many2one(related="schedule_id.term_id")
    date = fields.Date(required=True)
    start_time = fields.Float(required=True, default=9.0)
    duration = fields.Float(string="Duration (hours)", required=True, default=3.0)
    end_time = fields.Float(compute="_compute_end", store=True)
    room_ids = fields.Many2many("op.classroom", string="Rooms")
    student_count = fields.Integer(compute="_compute_student_count")

    _uniq = models.Constraint("unique(schedule_id, offering_id)", "This course already has a paper in this date sheet.")

    @api.depends("offering_id", "date", "start_time")
    def _compute_display_name(self):
        for p in self:
            p.display_name = "%s (%s %s)" % (p.offering_id.subject_id.name or "", fields.Date.to_string(p.date) if p.date else "",
                                             _hhmm(p.start_time))

    @api.depends("start_time", "duration")
    def _compute_end(self):
        for p in self:
            p.end_time = p.start_time + p.duration

    @api.constrains("start_time", "duration")
    def _check_times(self):
        for p in self:
            if not 0 <= p.start_time < 24 or p.duration <= 0 or p.start_time + p.duration > 24:
                raise ValidationError(_("A paper must start and end on the same day."))

    def _students(self):
        self.ensure_one()
        return self.offering_id._active_enrollments().mapped("student_id")

    def _compute_student_count(self):
        for p in self:
            p.student_count = len(p._students()) if p.offering_id else 0

    def _overlaps(self, other):
        return self.date == other.date and self.start_time < other.end_time and other.start_time < self.end_time

    def time_label(self):
        return "%s-%s" % (_hhmm(self.start_time), _hhmm(self.end_time))


class IcterpExamSeat(models.Model):
    _name = "icterp.exam.seat"
    _description = "Exam seat"
    _order = "schedule_id, room_id, seat_no"

    schedule_id = fields.Many2one("icterp.exam.schedule", required=True, ondelete="cascade", index=True)
    paper_id = fields.Many2one("icterp.exam.paper", required=True, ondelete="cascade", index=True)
    student_id = fields.Many2one("op.student", required=True, index=True)
    room_id = fields.Many2one("op.classroom", required=True)
    seat_no = fields.Char(required=True)

    _uniq = models.Constraint("unique(paper_id, student_id)", "A student has one seat per paper.")


class IcterpExamDuty(models.Model):
    _name = "icterp.exam.duty"
    _description = "Invigilation duty"
    _order = "date, start_time, room_id"

    schedule_id = fields.Many2one("icterp.exam.schedule", required=True, ondelete="cascade", index=True)
    date = fields.Date(required=True)
    start_time = fields.Float(required=True)
    end_time = fields.Float(required=True)
    room_id = fields.Many2one("op.classroom", required=True)
    faculty_id = fields.Many2one("op.faculty", string="Invigilator", required=True)
