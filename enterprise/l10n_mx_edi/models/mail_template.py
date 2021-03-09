# -*- coding: utf-8 -*-

from odoo import api, models


class MailTemplate(models.Model):
    _inherit = "mail.template"

    def generate_email(self, res_ids, fields=None):
        self.ensure_one()
        res = super(MailTemplate, self).generate_email(res_ids, fields=fields)

        multi_mode = True
        if isinstance(res_ids, int):
            res_ids = [res_ids]
            multi_mode = False

        if self.model not in ['account.move', 'account.payment']:
            return res
        for record in self.env[self.model].browse(res_ids):
            if record.company_id.country_id != self.env.ref('base.mx'):
                continue
            attachment = record.l10n_mx_edi_retrieve_last_attachment()
            if attachment:
                (res[record.id] if multi_mode else res).setdefault('attachments', []).append((attachment.name, attachment.datas))
        return res
