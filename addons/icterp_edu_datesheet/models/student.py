from odoo import models


class OpStudent(models.Model):
    _inherit = "op.student"

    def _exam_papers(self, schedule):
        """This student's papers in a schedule with their seat: [(paper, seat or False)]."""
        self.ensure_one()
        rows = []
        for paper in schedule.paper_ids.sorted(lambda p: (p.date, p.start_time)):
            if self in paper._students():
                seat = schedule.seat_ids.filtered(lambda s: s.paper_id == paper and s.student_id == self)[:1]
                rows.append((paper, seat))
        return rows
