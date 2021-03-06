# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2010 NaN Projectes de Programari Lliure, S.L.
#                       http://www.NaN-tic.com
#    Copyright (C) 2016 Comunitea Servicios Tecnológicos, S.L.
#                       http://www.comunitea.com
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp import models, api, fields

class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.multi
    def action_date_assign(self):
        for inv in self:
            # In a Refund, due date is current date because it does not depend on client mode payment
            if inv.type == 'out_refund':
                res = {'value': {'date_due': fields.Date.context_today(self),
                                 'payment_term': False}}
            else:
                res = inv.with_context(partner_id=inv.partner_id.
                                       commercial_partner_id.id).\
                    onchange_payment_term_date_invoice(inv.payment_term.id,
                                                       inv.date_invoice)
            if res and res.get('value'):
                inv.write(res['value'])
        return True

    @api.multi
    def action_move_create(self):
        for inv in self:
            super(AccountInvoice, inv.
                  with_context(partner_id=inv.partner_id.
                               commercial_partner_id.id)).\
                action_move_create()
        return True
