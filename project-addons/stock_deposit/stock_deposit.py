# -*- coding: utf-8 -*-
##############################################################################
#
#    Author: Santi Argüeso
#    Copyright 2014 Pexego Sistemas Informáticos S.L.
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
from openerp import models, fields, api


class stock_deposit(models.Model):
    _name = 'stock.deposit'
    _description = "Deposits"
    _inherit = ['mail.thread', 'ir.needaction_mixin']

    product_id = fields.Many2one(string='Product',
                                 related='move_id.product_id',
                                 store=True, readonly=True)
    product_uom_qty = fields.Float('Product qty',
                                   related='move_id.product_uom_qty',
                                   store=True, readonly=True)
    product_uom = fields.Many2one(related='move_id.product_uom',
                                  string='Uom',
                                  store=True,
                                  readonly=True)
    invoice_id = fields.Many2one('account.invoice', 'Invoice')
    move_id = fields.Many2one('stock.move', 'Deposit Move', required=True,
                              readonly=True, ondelete='cascade', select=1)
    picking_id = fields.Many2one(related='move_id.picking_id',
                                 string='Picking',
                                 store=True,
                                 readonly=True)
    partner_id = fields.Many2one(related='move_id.partner_id',
                                 string='Destination Address',
                                 store=True,
                                 readonly=True)
    sale_id = fields.Many2one(related='move_id.procurement_id.sale_line_id.order_id',
                              string='Sale',
                              store=True,
                              readonly=True)
    delivery_date = fields.Datetime('Date of Transfer')
    return_date = fields.Date('Return date')
    company_id = fields.Many2one(related='move_id.company_id',
                                 string='Date of Transfer',
                                 store=True,
                                 readonly=True)
    state = fields.Selection([('draft', 'Draft'), ('sale', 'Sale'),
                              ('returned', 'Returned'),
                              ('invoiced', 'Invoiced')], 'State',
                             readonly=True, required=True)
    sale_move_id = fields.Many2one('stock.move', 'Sale Move', required=False,
                                   readonly=True, ondelete='cascade', select=1)
    sale_picking_id = fields.Many2one(related='sale_move_id.picking_id',
                                      string='Sale picking',
                                      readonly=True)
    return_picking_id = fields.Many2one('stock.picking', 'Return Picking',
                                        required=False, readonly=True,
                                        ondelete='cascade', select=1)
    user_id = fields.Many2one('res.users', 'Comercial', required=False,
                              readonly=True, ondelete='cascade', select=1)

    @api.multi
    def sale(self):
        move_obj = self.env['stock.move']
        picking_type_id = self.env.ref('stock.picking_type_out')
        for deposit in self:
            picking = self.env['stock.picking'].create(
                {'picking_type_id': picking_type_id.id,
                 'partner_id': deposit.partner_id.id,
                 'invoice_state': '2binvoiced'})
            values = {
                'product_id': deposit.product_id.id,
                'product_uom_qty': deposit.product_uom_qty,
                'product_uom': deposit.product_uom.id,
                'partner_id': deposit.partner_id.id,
                'name': 'Sale Deposit: ' + deposit.move_id.name,
                'location_id': deposit.move_id.location_dest_id.id,
                'location_dest_id': deposit.partner_id.property_stock_customer.id,
                'invoice_state': '2binvoiced',
                'picking_id': picking.id,
                'procurement_id': deposit.move_id.procurement_id.id
            }
            move = move_obj.create(values)
            move.action_confirm()
            move.force_assign()
            move.action_done()
            deposit.write({'state': 'sale', 'sale_move_id': move.id})

    @api.one
    def _prepare_deposit_move(self, picking, group):
        deposit_id = self.env.ref('stock_deposit.stock_location_deposit')
        move_template = {
            'name': 'RET' or '',
            'product_id': self.product_id.id,
            'product_uom': self.product_uom.id,
            'product_uom_qty': self.product_uom_qty,
            'product_uos': self.product_uom.id,
            'location_id': deposit_id.id,
            'location_dest_id':
                picking.picking_type_id.default_location_dest_id.id,
            'picking_id': picking.id,
            'partner_id': self.partner_id.id,
            'move_dest_id': False,
            'state': 'draft',
            'company_id': self.company_id.id,
            'group_id': group.id,
            'procurement_id': False,
            'origin': False,
            'route_ids':
                picking.picking_type_id.warehouse_id and
                [(6, 0,
                  [x.id for x in
                   picking.picking_type_id.warehouse_id.route_ids])] or [],
            'warehouse_id': picking.picking_type_id.warehouse_id.id,
            'invoice_state': 'none'
        }
        return move_template

    @api.one
    def _create_stock_moves(self, picking=False):
        stock_move = self.env['stock.move']
        todo_moves = self.env['stock.move']
        new_group = self.env['procurement.group'].create(
            {'name': 'deposit RET', 'partner_id': self.partner_id.id})
        for vals in self._prepare_deposit_move(picking, new_group):
            todo_moves += stock_move.create(vals)

        todo_moves.action_confirm()
        todo_moves.force_assign()

    @api.multi
    def return_deposit(self):
        picking_type_id = self.env.ref('stock.picking_type_in')
        for deposit in self:
            picking = self.env['stock.picking'].create(
                {'picking_type_id': picking_type_id.id,
                 'partner_id': deposit.partner_id.id})
            deposit._create_stock_moves(picking)
            deposit.write({'state': 'returned',
                           'return_picking_id': picking.id})

    @api.model
    def send_advise_email(self):
        deposits = self.search([('return_date', '=', fields.Date.today())])
        #~ mail_pool = self.env['mail.mail']
        #~ mail_ids = self.env['mail.mail']
        template = self.env.ref('stock_deposit.stock_deposit_advise_partner', False)
        for deposit in deposits:
            ctx = dict(self._context)
            ctx.update({
                'default_model': 'stock.deposit',
                'default_res_id': deposit.id,
                'default_use_template': bool(template.id),
                'default_template_id': template.id,
                'default_composition_mode': 'comment',
                'mark_so_as_sent': True
            })
            composer_id = self.env['mail.compose.message'].with_context(
                ctx).create({})
            composer_id.with_context(ctx).send_mail()
            #~ mail_id = template.send_mail(deposit.id)
            #~ mail_ids += mail_pool.browse(mail_id)
        #~ if mail_ids:
            #~ mail_ids.send()
        return True
