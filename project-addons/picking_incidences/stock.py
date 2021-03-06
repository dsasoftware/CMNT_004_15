# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2015 Pexego Sistemas Informáticos All Rights Reserved
#    $Omar Castiñeira Saavedra <omar@pexego.es>$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
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

from openerp import fields, models, api, _, exceptions
import openerp.addons.decimal_precision as dp
from openerp.tools.float_utils import float_compare, float_round


class StockMove(models.Model):

    _inherit = "stock.move"

    qty_ready = fields.\
        Float('Qty ready', readonly=True, copy=False,
              digits=dp.get_precision('Product Unit of Measure'))
    qty_confirmed = fields.\
        Float('Qty confirmed', copy=False,
              digits=dp.get_precision('Product Unit of Measure'))

    @api.multi
    def action_cancel(self):
        for move in self:
            if move.picking_id and move.picking_id.block_picking:
                raise exceptions.\
                    Warning(_("Cannot cancel this move because it is being "
                              "processed in Vstock."))
        return super(StockMove, self).action_cancel()


class StockPicking(models.Model):

    _inherit = "stock.picking"

    with_incidences = fields.Boolean('With incidences', readonly=True,
                                     copy=False)
    block_picking = fields.Boolean('Albarán procesado Vstock')

    #~ @api.multi
    #~ def write(self, vals):
        #~ res = super(StockPicking, self).write(vals)
        #~ if vals.get('with_incidences', False):
            #~ for pick in self:
                #~ no_incidence = True
                #~ for move in pick.move_lines:
                    #~ if not move.qty_ready or move.qty_ready > \
                            #~ move.reserved_availability:
                        #~ no_incidence = False
                        #~ break
                #~ if no_incidence:
                    #~ pick.with_incidences = False
        #~ return res

    @api.one
    def action_accept_ready_qty(self):
        self.with_incidences = False
        new_moves = []
        for move in self.move_lines:
            if move.state in ('done', 'cancel'):
                # ignore stock moves cancelled or already done
                continue
            precision = move.product_uom.rounding
            remaining_qty = move.product_uom_qty - move.qty_ready
            remaining_qty = float_round(remaining_qty,
                                        precision_rounding=precision)
            if not move.qty_ready:
                new_moves.append(move.id)
            elif float_compare(remaining_qty, 0,
                               precision_rounding=precision) > 0 and \
                float_compare(remaining_qty, move.product_qty,
                              precision_rounding=precision) < 0:
                new_move = move.split(move, remaining_qty)
                new_moves.append(new_move)
        if new_moves:
            new_moves = self.env['stock.move'].browse(new_moves)
            bcko_id = self._create_backorder(self, backorder_moves=new_moves)
            bck = self.browse(bcko_id)
            new_moves.write({'qty_ready': 0.0})
            self.do_unreserve()
            self.recheck_availability()
        self.message_post(body=_("User %s accepted ready quantities.") %
                          (self.env.user.name))
        self.action_done()

    @api.multi
    def action_assign(self):
        res = super(StockPicking, self).action_assign()
        for pick in self:
            pick.write({'with_incidences': False})
        return res

    @api.cr_uid_ids_context
    def do_enter_transfer_details(self, cr, uid, picking, context=None):
        for pick in self.pool['stock.picking'].browse(cr, uid, picking,
                                                      context=context):
            if pick.with_incidences:
                raise exceptions.Warning(_("Cannot process picking with "
                                           "incidences. Please fix or "
                                           "ignore it."))
        return super(StockPicking, self).do_enter_transfer_details(cr, uid,
                                                                   picking,
                                                                   context)

    @api.multi
    def action_done(self):
        for pick in self:
            if pick.with_incidences:
                raise exceptions.Warning(_("Cannot process picking with "
                                           "incidences. Please fix or "
                                           "ignore it."))
        return super(StockPicking, self).action_done()

    @api.onchange('move_type')
    def onchange_move_type(self):
        if self.move_type == "direct":
            for line in self.move_lines:
                line.qty_confirmed = line.reserved_availability
        else:
            for line in self.move_lines:
                line.qty_confirmed = 0.0

    @api.multi
    def action_cancel(self):
        for pick in self:
            if pick.with_incidences and pick.picking_type_code == 'incoming':
                raise exceptions.\
                    Warning(_("Cannot cancel an incoming picking with "
                              "incidences. You can only process it."))
            if pick.block_picking:
                raise exceptions.\
                    Warning(_("Cannot cancel this picking because it is being "
                              "processed in Vstock."))
        return super(StockPicking, self).action_cancel()

    @api.multi
    def action_copy_reserv_qty(self):
        for pick in self:
            for move in pick.move_lines:
                move.qty_confirmed = move.reserved_availability

    @api.multi
    def action_accept_confirmed_qty(self):
        for pick in self:
            #check move lines confirmed qtys
            for move in pick.move_lines:
                if move.qty_confirmed > move.reserved_availability:
                    raise exceptions.\
                        Warning(_("Cannot assign more qty that reserved "
                                  "availability."))
            new_moves = []
            for move in pick.move_lines:
                if move.state in ('done', 'cancel'):
                    # ignore stock moves cancelled or already done
                    continue
                precision = move.product_uom.rounding
                remaining_qty = move.product_uom_qty - move.qty_confirmed
                remaining_qty = float_round(remaining_qty,
                                            precision_rounding=precision)
                if not move.qty_confirmed:
                    new_moves.append(move.id)
                elif float_compare(remaining_qty, 0,
                                   precision_rounding=precision) > 0 and \
                    float_compare(remaining_qty, move.product_qty,
                                  precision_rounding=precision) < 0:
                    new_move = move.split(move, remaining_qty)
                    new_moves.append(new_move)
                if not move.product_uom_qty:
                    move.state = 'draft'
                    move.unlink()
            if new_moves:
                new_moves = self.env['stock.move'].browse(new_moves)
                bckid = self._create_backorder(self, backorder_moves=new_moves)
                bck = self.browse(bckid)
                bck.write({'move_type': 'one'})
                self.action_assign()
            self.message_post(body=_("User %s accepted confirmed qties.") %
                              (self.env.user.name))
