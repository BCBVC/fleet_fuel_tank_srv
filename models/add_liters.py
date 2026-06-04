# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, _
from datetime import datetime
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

class liters_liters(models.Model):
    _name = 'liters.liters'
    _description = 'Galones litros'
    
    liters = fields.Float('Galones')
    liter_price = fields.Float('Precio por Galon')

    def add_liters(self):

            liters=self.liters
            price_per_liter = self.liter_price
            wizard_total_liter_price = liters * price_per_liter
            fuel_tank_obj=self.env['fuel.tank']
            history_obj = self.env['fuel.filling.history']
            date = datetime.now()
            defaultdate =  date.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
            filldate = defaultdate.split()[0]
            res_history = {
                'fuel_liter':liters,
                'price_per_liter':price_per_liter,
                'filling_date':filldate,
                'fuel_filling_id': self._context.get('active_id'),
            }
            history_obj.create(res_history)
            if self._context.get('active_id',False):
                browse_obj = fuel_tank_obj.browse(self._context['active_id'])
                liter_in_tank = browse_obj.liters
                price_per_liter_from_tank = browse_obj.average_price
                total_tank_litter_price = liter_in_tank * price_per_liter_from_tank
                
                total = liter_in_tank + liters
                if browse_obj.capacity < total:
                    raise UserError(_('Solo puedes tener '+ str(float(browse_obj.capacity) - float(liter_in_tank)) +' galones de capacidad'))
                final_average_price = 0
                if (total != 0):
                    final_average_price = (total_tank_litter_price + wizard_total_liter_price) / (total)
                else:
                    raise UserError(_('No puede tener una cantidad de combustible inferior a 1.'))
                browse_obj.write({'liters':total,'average_price':final_average_price,'last_fuel_adding_date':filldate})
            return True

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
