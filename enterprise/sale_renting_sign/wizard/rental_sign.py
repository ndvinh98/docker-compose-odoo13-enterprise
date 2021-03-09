# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class RentalSign(models.TransientModel):
    _name = "rental.sign.wizard"
    _description = "Sign Documents from a SO"

    @api.model
    def default_get(self, fields):
        res = super(RentalSign, self).default_get(fields)
        res["order_id"] = self.env.context.get("active_id", None)
        default_template = self.env.company.rental_sign_tmpl_id
        # if document not properly accessible by all employees, avoid access error
        try:
            default_template.check_access_rule("read")
            res["template_id"] = self.env.company.rental_sign_tmpl_id.id
        except:
            pass
        return res

    template_id = fields.Many2one(
        "sign.template", "Document Template", required=True, ondelete="cascade"
    )
    order_id = fields.Many2one(
        "sale.order", "Sales Order", required=True, ondelete="cascade"
    )

    def next_step(self):
        pending_sign_request = self.order_id.sign_request_ids.filtered(
            lambda request: request.template_id == self.template_id
            and request.state == "sent"
        )
        if pending_sign_request:
            return pending_sign_request.go_to_document()
        else:
            action = self.env.ref("sign.action_sign_send_request").read([])[0]
            action["context"] = {
                "active_id": self.template_id.id,
                "sign_directly_without_mail": True,
                "default_sale_order_id": self.order_id.id,
            }
            return action
