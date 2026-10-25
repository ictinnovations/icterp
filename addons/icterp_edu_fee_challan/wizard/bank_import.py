"""Confirm many challans from the bank's daily file.

CSV columns (header row required, names are case-insensitive):
  challan, paid_date (YYYY-MM-DD or DD/MM/YYYY), amount, reference (optional)
Each row is confirmed on its own; a bad row is reported and the rest still go through.
"""
import base64
import csv
import io
from datetime import datetime

from odoo import _, fields, models
from odoo.exceptions import UserError


def _parse_date(text):
    text = (text or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise UserError(_("Unknown date %s", text))


class IcterpChallanBankImport(models.TransientModel):
    _name = "icterp.challan.bank.import"
    _description = "Import paid challans from the bank file"

    file = fields.Binary(required=True)
    filename = fields.Char()
    journal_id = fields.Many2one("account.journal", domain="[('type', '=', 'bank')]")
    result_note = fields.Text(readonly=True)

    def _rows(self):
        raw = base64.b64decode(self.file or b"")
        text = raw.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            yield {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}

    def action_import(self):
        self.ensure_one()
        Challan = self.env["icterp.fee.challan"]
        ok, problems = 0, []
        for n, row in enumerate(self._rows(), start=2):
            number = row.get("challan") or row.get("challan_no") or row.get("challan no")
            try:
                challan = Challan.search([("name", "=", number)], limit=1)
                if not challan:
                    raise UserError(_("no challan %s", number))
                amount = float((row.get("amount") or "0").replace(",", ""))
                with self.env.cr.savepoint():
                    challan.confirm_payment(_parse_date(row.get("paid_date") or row.get("date")), amount=amount,
                                            journal=self.journal_id or None, reference=row.get("reference") or None)
                ok += 1
            except UserError as e:
                problems.append(_("line %(n)s (%(no)s): %(err)s", n=n, no=number or "-", err=e.args[0] if e.args else e))
        note = _("%s challan(s) confirmed.", ok)
        if problems:
            note += "\n" + "\n".join(problems)
        self.result_note = note
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": self.id, "view_mode": "form", "target": "new"}
