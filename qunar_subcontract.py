# -*- encoding: utf-8 -*-
##############################################################################
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see http://www.gnu.org/licenses/.
#
##############################################################################

from openerp import api,_,fields,models
from openerp.exceptions import except_orm

class qunar_subcontract(models.Model):
	_inherit="mrp.production"

	@api.multi
	def action_assign(self):
		stock_move_obj = self.env['stock.move']
		# in subcontract case
		if self.routing_id and self.routing_id.location_id and self.routing_id.location_id.usage =="supplier":
			#[Bug] if there already has one out order which state is not done, the new out marterial will append to it
			#In this case, how to find it out?
			moves = stock_move_obj.search([('origin','=',self.name),('location_dest_id.usage','=','supplier'),('state','!=','done')])
			if len(moves):
				raise except_orm(_('Warning'),_("you haven't finished your material moves in subcontract order."))

			#double check if there's no moves!
			done_moves = stock_move_obj.search([('origin','=',self.name),('location_dest_id.usage','=','supplier'),('state','=','done')])
			if not len(done_moves):
				raise except_orm(_('Warning'),_("Where's your material moves?!"))

		return super(qunar_subcontract,self).action_assign()

	@api.model
	def _make_service_procurement(self,line):
		# make it produce service procurement order normally.
		prod_obj = self.env['product.product']
		obj_data = self.env['ir.model.data']
		type_obj = self.env['stock.picking.type']
		company_id = self.env.user.company_id.id
		types = type_obj.search([('code', '=', 'incoming'), ('warehouse_id.company_id', '=', company_id)])
		if not types:
			types = type_obj.search([('code', '=', 'incoming'), ('warehouse_id', '=', False)])
			if not types: 
				raise except_orm(_('Error!'), _("Make sure you have at least an incoming picking type defined"))

		routes = self.env['procurement.rule'].search([('picking_type_id','=',types[0].id),('action','=','buy')])
		vals = {
		    'name': line.production_id.name,
		    'origin': line.production_id.name,
		    'company_id': line.production_id.company_id.id,
		    'date_planned': line.production_id.date_planned,
		    'product_id': line.product_id.id,
		    'product_qty': line.product_qty,
		    'product_uom': line.product_uom.id,
		    'product_uos_qty': line.product_uos_qty,
		    'product_uos': line.product_uos.id,
		    'location_id':routes[0].location_id.id,
		    'rule_id':routes[0].id,
		    }
		proc_obj = self.env["procurement.order"]
		proc = proc_obj.create(vals)
		proc_obj.run([proc])


class procurement_order(models.Model):
	_inherit="procurement.order"

	@api.model
	def _assign(self,procurement):
		if procurement.product_id.type=="service":
			return True
		return super(procurement_order,self)._assign(procurement)

	@api.model
	def _run(self,procurement):
		if procurement.product_id.type=="service":
			procurement.make_po()
			return True
		return super(procurement_order,self)._run(procurement)

class stock_move(models.Model):
	_inherit="stock.move"

	@api.model
	def get_price_unit(self,move):
		#if the move is from production location to internal location,using quant cost replace of price_unit in bom,
		#return the sum price of bom as the cost of production quant.
		move_obj = self.env['stock.move']
		bom_obj = self.env['mrp.bom']
		res={}
		if move.location_id.usage=="production" and move.location_dest_id.usage=="internal":
			raw_moves = move_obj.search([('raw_material_production_id','=',move.production_id.id)])
			for raw_move in raw_moves:
				costs = [q.cost for q in raw_move.quant_ids if q.product_id == raw_move.product_id]		
				if len(costs):
					res[raw_move.product_id.id] = costs[0]

			#compute the cost of production product
			#[Note] here we dont add service type product's price into subtotal,if you need you can change here.
			if len(res):
				subtotal = sum((lambda x,p:[ product.product_qty*p[product.product_id.id] for product in x if product.product_id.type!='service'])(move.production_id.bom_id.bom_line_ids,res))
				return subtotal
			#[FIXME]cause the production move done before marterial move,we cant get the cost of quant when we comsume&produce
			#so we use average price instead.
			return sum((lambda x:[ product.product_qty*product.product_id.standard_price for product in x if product.product_id.type!='service'])(move.production_id.bom_id.bom_line_ids))

		return super(stock_move,self).get_price_unit(move)


	"""@api.multi
	def action_done(self):
		#reverse the tuple ids of self
		self._ids =tuple(sorted(self._ids,reverse=True))
		return super(stock_move,self).action_done()"""