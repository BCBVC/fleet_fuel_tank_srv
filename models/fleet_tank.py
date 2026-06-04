# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, _
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError
import time

class fuel_tank(models.Model):
	
	_name = 'fuel.tank'
	_description = 'Depósito de combustible'

	def _filling_fuel_percentage(self):
		total_percentage = 0.0
		for record in self:
			capacity = record.capacity
			liters = record.liters
			if capacity != 0.0:
				total_percentage = (liters * 100)/capacity
				per_list = str(total_percentage).split('.')
				ans = per_list[0] +'.'+ per_list[1][:2]
				record.percentage_fuel = ans + ' %'
			else:
				record.percentage_fuel = False

		
	name = fields.Char(string='Nombre',required=True)
	capacity = fields.Float(string='Capacidad')
	location = fields.Char(string='Ubicación')
	last_clean_date = fields.Date(string='Última fecha de limpieza')
	liters = fields.Float(string='Galones',readonly=True)
	average_price = fields.Float(string='Precio promedio',readonly=True,default=0.0)
	last_filling_date = fields.Date(string='Última fecha de llenado',readonly=True)
	last_filling_amount = fields.Float(string='Last Filling Amount',readonly=True,default=0.0)
	last_filling_price_liter = fields.Float(string='Último precio de llenado',readonly=True,default=0.0)
	fule_filling_history_ids = fields.One2many('fuel.filling.history', 'fuel_filling_id', string='Historial', readonly=True)
	percentage_fuel = fields.Char(compute = '_filling_fuel_percentage', string='Combustible de llenado total')
	last_fuel_adding_date =fields.Date(string='Última fecha de combustible agregado',readonly=True)


class fleet_vehicle_log_fuel(models.Model):
	_inherit = 'fleet.vehicle.log.fuel'
	
	def unlink(self):
		for fuel_id in self:
			fuel_tank_id = fuel_id.fuel_tank_id.id
			liters = fuel_id.liter
			fuel_tank_obj = self.env['fuel.tank']
			if fuel_tank_id:
				tank_liters = fuel_tank_obj.browse(fuel_tank_id).liters
				total_liters = tank_liters + liters
				fuel_tank_obj.browse(fuel_tank_id).write({'liters':total_liters})
		super(fleet_vehicle_log_fuel, self).unlink()



	@api.onchange('fuel_tank_id')
	def onchange_fuel_tank(self):
		res = {}
		if self.fuel_tank_id:
			res['price_per_liter'] = self.fuel_tank_id.average_price
		return {'value': res}

	fuel_tank_id = fields.Many2one('fuel.tank',string='Gasolinera',required=True, default=lambda self: self.env['fuel.tank'].search([], limit=1))
	employee_id = fields.Many2one('hr.employee',string='Empleado',required=True, default=lambda  self: self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1))
	previous_odometer = fields.Float(string='Lectura anterior del odometro',readonly=True)
	prev_odo = fields.Integer(string='Kilometraje de salida', tracking=True, required=True )
	state = fields.Selection(
        [('a_draft','Solicita'),
			('b_confirm','Confimado'),
			('c_approve','Aprobado'),
			('f_fin','Finalizado'),
			('cancel','Cancelado')],
        string='Estado',
        default='a_draft',
        copy=False,
        tracking=True 
    )
	vehicle_plate = fields.Char(
        string="Placa"
    )

	@api.constrains("previous_odometer")
	def _check_odometer(self):
		if self.odometer < self.previous_odometer:
			return False
		return True

	@api.onchange('vehicle_id')
	def onchange_vehicle(self):
	
		val = {}
		if self.vehicle_id:

			vehicle_ids  =  self.env['fleet.vehicle'].search([('id','=',self.vehicle_id.id)], limit=1)
			
			if vehicle_ids:
				prev_odometer = vehicle_ids.read(['odometer'])[0].get('odometer')
				license_plate = vehicle_ids.read(['license_plate'])[0].get('license_plate')
				codigo_vehi = vehicle_ids.read(['codigo_vehi'])[0].get('codigo_vehi')

				val = {
						'previous_odometer': prev_odometer,
						'prev_odo': prev_odometer,
						'vehicle_plate': license_plate,
						'vehicle_code': codigo_vehi,
					}
			else:
				val = {
						'previous_odometer': 0.0,
						'prev_odo': 0.0,
						'vehicle_plate': '',
						'vehicle_code': '',
					}
		return {'value': val}


	@api.model
	def create(self,vals):
		log_id = self.search([('vehicle_id','=',vals.get('vehicle_id'))])
		odometer_forward = 0.0
		if log_id:
			odometer_forward = max(log_id).odometer
		else:
			odometer_forward = 0.0





		date = datetime.now()
		defaultdate =  date.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
		filldate = defaultdate.split()[0]
		hr_employee_obj=self.env['hr.employee']
		fuel_tnk_obj=self.env['fuel.tank']
		system_date = filldate
		odo_fuel_obj = self.env['odometer.filling.history']
		vehicle_obj = self.env['fleet.vehicle']
		fuel_tank_id = vals.get('fuel_tank_id',False)

		vehicle_id = vals.get('vehicle_id',False)
		if vehicle_id:
			vehicle = vehicle_obj.browse(vehicle_id)
		liters = vals.get('liter',0.0)
		price_per_liter = vals.get('price_per_liter',0.0)
		odometer_latest = vals.get('odometer',0.0)


		if vals.get('liter',0.0):
			fuel_litter = vals.get('liter',0.0)
		else:
			fuel_litter = self.liter
		if vals.get('fuel_tank_id'):
			fuel_tan = vals.get('fuel_tank_id')
		else:
			fuel_tan = self.fuel_tank_id.id
		fuel_tan_liter = fuel_tnk_obj.browse(fuel_tan).liters


			
		seq = self.env['ir.sequence'].next_by_code('combustible.carga') or '/'

		vals.update({'name': seq})

		odometer_final = odometer_latest - odometer_forward


		odometercrea = self.env['fleet.vehicle.odometer'].create({
								'value': vals.get('prev_odo'),
								'date': datetime.now(),
								'vehicle_id': vehicle_id
							})
		self.odometer_id = odometercrea
		
		great_average_obj = self.env['compsuption.great.average']
		consuption_average = 0.0
		log_id = super(fleet_vehicle_log_fuel, self).create(vals)
		if odometer_final != 0.0:
			consuption_average = ((liters/odometer_final)*100)
			great_average_obj.create({'great_average':consuption_average,'vehicle_id':vehicle_id, 'employee_id':employee_id,'consumption_average_id': log_id.id, 'modified_date': system_date})
		odometer_vals = {
			'fuel_liter':liters,
			'price_per_liter':price_per_liter,
			'filling_date':system_date,
			'fuel_filling_odometer_id': fuel_tank_id,
		}
		odo_fuel_obj.create(odometer_vals)
		amount = vals.get('amount',0.0)
		fuel_tank_obj = self.env['fuel.tank']
		ft_liters = fuel_tank_obj.browse(fuel_tank_id).liters
		final_liters = ft_liters - liters
		great_con_ids = great_average_obj.search([('vehicle_id','=',vehicle_id)])

		res = {
			'liters':final_liters,
			'last_filling_price_liter':price_per_liter,
			'last_filling_amount':amount,
			'last_filling_date':system_date,
		}
		res_vehicle = {
			'consuption_average':consuption_average,
		}
		fuel_tank_obj.browse(fuel_tank_id).write(res)
		vehicle_obj.browse(vehicle_id).write(res_vehicle)
		return log_id

	def write(self, vals):
		liters = 0.0
		price_per_liter = 0.0
		fuel_tank_obj = self.env['fuel.tank']
		if vals.get('odometer'):
			previous_odometer = self.previous_odometer or 0.0
			if previous_odometer >= vals.get('odometer'):
				raise   UserError(_('El valor del odómetro debe ser mayor que el valor del odómetro anterior!'))
				
		if self.fuel_tank_id:
			ft_liters = self.fuel_tank_id.liters
			if vals.get('liter'):
				liters = vals.get('liter')
		ft_liters = fuel_tank_obj.browse(self.fuel_tank_id.id).liters
		liters = vals.get('liter')

		if vals.get('liter',0.0):
			fuel_litter = vals.get('liter',0.0)
		else:
			fuel_litter = self.liter
		if vals.get('fuel_tank_id'):
			fuel_tan = vals.get('fuel_tank_id')
		else:
			fuel_tan = self.fuel_tank_id.id
		fuel_tan_liter = fuel_tank_obj.browse(fuel_tan).liters


		odometercrea = self.env['fleet.vehicle.odometer'].create({
						'value': vals.get('prev_odo'),
						'date': datetime.now(),
						'vehicle_id': self.vehicle_id.id
					})
		vals["odometer_id"] = odometercrea

		if liters:
			final_liters = ft_liters - liters
			if vals.get('price_per_liter'):
				price_per_liter = vals.get('price_per_liter') or 0.0
			amount = liters * price_per_liter
			system_date = time.strftime("%Y-%m-%d")
			old_liters = self.liter
			ft_liters = fuel_tank_obj.browse(self.fuel_tank_id.id).liters
			ft_liters_updated = 0.0
			if old_liters > liters:
				difference_litter = old_liters - liters
				ft_liters_updated = ft_liters + difference_litter
			if liters > old_liters:
				difference_litter = liters - old_liters
				ft_liters_updated = ft_liters - difference_litter
			res = {
				'liters':ft_liters_updated,
				'last_filling_price_liter':price_per_liter,
				'last_filling_amount':amount,
				'last_filling_date':system_date,
			}
			fuel_tank_obj.browse(self.fuel_tank_id.id).write(res)
		return super(fleet_vehicle_log_fuel, self).write(vals)
	
	

class fleet_vehicle(models.Model):
	_inherit = 'fleet.vehicle'
	
	consuption_average = fields.Float(string="Promedio de consumo",readonly=True)
	grant_consuption_average = fields.Float(compute='_get_grant_consuption_average',  string='Promedio de Consumo Superior',store=True)
	consumption_average_history_ids = fields.One2many('compsuption.great.average', 'vehicle_id', string='Historial de consumo', readonly=True)

	def _get_grant_consuption_average(self):
		val = 0.0
		res = {}
		for vehicle in self:
			counter = 0
			val = 0.0
			if vehicle.consumption_average_history_ids:
				for line in vehicle.consumption_average_history_ids:
					val += line.great_average
					counter += 1
				res[vehicle.id] = val/counter
			else:
				res[vehicle.id] = 0.0
		return res

class FuelFillingHistory(models.Model):
	_name = 'fuel.filling.history'
	_description = 'Historial de Carga de combustible'

	fuel_liter = fields.Float(string='Galones',readonly=False)
	price_per_liter = fields.Float(string='Precio',readonly=False)
	filling_date = fields.Date(string='Fecha',readonly=False)
	fuel_filling_id = fields.Many2one('fuel.tank',string='Referencia de carga de combustible', required=True, ondelete='cascade')

class OdometerFillingHistory(models.Model):
	_name = 'odometer.filling.history'
	_description = "Historial de carga del odómetro"

	fuel_liter = fields.Float(string='Galones')
	price_per_liter = fields.Float(string='Precio')
	filling_date = fields.Date(string='Fecha')
	fuel_filling_odometer_id = fields.Many2one('fuel.tank',string='Referencia de carga de combustible', required=True, ondelete='cascade')

class compsuption_great_average(models.Model):
	_name = 'compsuption.great.average'
	_description = 'Consumo Promedio'
	
	great_average = fields.Float(string='Consumo Promedio')
	vehicle_id = fields.Many2one('fleet.vehicle',string="Vehiculo")
	consumption_average_id = fields.Many2one('fleet.vehicle.log.fuel',string='Identificación promedio de consumo', ondelete='cascade')
	modified_date = fields.Date(string='Fecha de Carga')
	employee_id = fields.Many2one('hr.employee',string='Empleado')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
