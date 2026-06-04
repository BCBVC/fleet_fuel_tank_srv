# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
try:
   import qrcode
except ImportError:
   qrcode = None
try:
   import base64
except ImportError:
   base64 = None
from io import BytesIO
import pytz
from odoo import http
from odoo.http import Controller, request, route
import zipfile
import re
from datetime import datetime
from odoo.exceptions import ValidationError


from odoo import api, fields, models, _
from odoo.exceptions import UserError

from dateutil.relativedelta import relativedelta


class FleetVehicleCost(models.Model):
    _name = 'fleet.vehicle.cost'
    _description = 'Costo relacionado con un vehículo'
    _order = 'date desc, vehicle_id asc'

    name = fields.Char(related='vehicle_id.name', string='Nombre', store=True, readonly=False)
    vehicle_id = fields.Many2one('fleet.vehicle', 'Vehículo', required=True, help='Registro de este vehículo')
    cost_subtype_id = fields.Many2one('fleet.service.type', 'Tipo', help='Tipo de costo comprado')
    amount = fields.Float('Valor Subtotal', required=True)
    cost_type = fields.Selection([
        ('contract', 'Contrato'),
        ('services', 'Servicios'),
        ('fuel', 'Combustible'),
        ('other', 'Otros')
        ], string='Categoría del costo', default="other", help='Para propositos internos', required=True)
    parent_id = fields.Many2one('fleet.vehicle.cost', string='Costo padre', help='Costo principal a este costo actual')
    cost_ids = fields.One2many('fleet.vehicle.cost', 'parent_id', string='Servicios incluidos', copy=True)
    odometer_id = fields.Many2one('fleet.vehicle.odometer', string='Odometro', help='Medida del odometro del vehículo al momento de este registro')
    odometer = fields.Float(
        compute="_get_odometer", string='Valor Odometro',
        help='Medida del odómetro del vehículo al momento de este registro')
    odometer_unit = fields.Selection(related='vehicle_id.odometer_unit', string="Unidad", readonly=True)
    date = fields.Date(help='Fecha en que se ha ejecutado el costo', string="Fecha" )
    contract_id = fields.Many2one('fleet.vehicle.log.contract', string='Contrato', help='Contrato adjunto a este costo')
    auto_generated = fields.Boolean('Generada automáticamente', readonly=True)
    description = fields.Char("Descripción del Costo")
    company_id = fields.Many2one('res.company', 'Institución', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')

    def _get_odometer(self):
        self.odometer = 0
        for record in self:
            if record.odometer_id:
                record.odometer = record.odometer_id.value

    def _set_odometer(self):
        for record in self:
            if not record.odometer:
                raise UserError(_('No está permitido vaciar el valor del cuenta kilómetros de un vehículo.'))
            odometer = self.env['fleet.vehicle.odometer'].create({
                'value': record.odometer,
                'date': record.date or fields.Date.context_today(record),
                'vehicle_id': record.vehicle_id.id
            })
            self.odometer_id = odometer
                
    @api.model_create_multi
    def create(self, vals_list):
        for data in vals_list:

            if 'parent_id' in data and data['parent_id']:
                parent = self.browse(data['parent_id'])
                data['vehicle_id'] = parent.vehicle_id.id
                data['date'] = parent.date
                data['cost_type'] = parent.cost_type
            if 'contract_id' in data and data['contract_id']:
                contract = self.env['fleet.vehicle.log.contract'].browse(data['contract_id'])
                data['vehicle_id'] = contract.vehicle_id.id
                data['cost_subtype_id'] = contract.cost_subtype_id.id
                data['cost_type'] = contract.cost_type
            if 'odometer' in data and not data['odometer']:
                del data['odometer']
        return super(FleetVehicleCost, self).create(vals_list)



class FleetVehicleLogFuel(models.Model):
    _name = 'fleet.vehicle.log.fuel'
    _description = 'Registro de combustible para vehículos'
    _inherits = {'fleet.vehicle.cost': 'cost_id'}
    _order = 'id desc'
    _inherit = ['mail.thread']
    
    pdf_file_maquinistas = fields.Binary(string="Archivo PDF")
    pdf_file_maquinistas_name = fields.Char(string="Nombre del Archivo PDF")
    pdf_file_sala_situacional = fields.Binary(string="Nuevo Archivo PDF")
    pdf_file_sala_situacional_name = fields.Char(string="Nombre del Nuevo Archivo PDF")
    
    is_pdf_confirmed = fields.Boolean(string="PDF Confirmado", default=False)
    button_clicked = fields.Boolean(string="Botón clicado", default=False)
    show_subscription_info = fields.Boolean(string="Mostrar información de suscripción", default=False)
    is_firma_digital_clicked = fields.Boolean(string="Firma Digital Clicada", default=False)
    
    def action_show_subscription_info(self):
        self.ensure_one()
        self.show_subscription_info = True
        self.button_clicked = False
        return True
    
    def action_confirm_pdf_upload(self):

        if not self.pdf_file_maquinistas:
            raise ValueError("Debe cargar un archivo PDF antes de confirmar.")
        self.is_pdf_confirmed = True
        return True
    
    def write(self, vals):

        for record in self:
            if 'pdf_file_maquinistas' in vals and not vals.get('pdf_file_maquinistas_name'):

                if record.name: 
                    vals['pdf_file_maquinistas_name'] = f'{record.name}.pdf'
                else:
                    vals['pdf_file_maquinistas_name'] = 'orden_sin_nombre.pdf'  
        return super(FleetVehicleLogFuel, self).write(vals)

    def create(self, vals):

        record = super(FleetVehicleLogFuel, self).create(vals)
        if 'pdf_file_maquinistas' in vals and not vals.get('pdf_file_maquinistas_name'):
            record.pdf_file_maquinistas_name = f'{record.name}.pdf' if record.name else 'orden_sin_nombre.pdf'
        return record
    
    def action_manage_pdf(self):

        if not self.pdf_file_maquinistas:

            raise UserError("No hay un archivo PDF cargado para descargar.")


        return {
        'type': 'ir.actions.act_url',
        'url': f'/web/content/{self._name}/{self.id}/pdf_file_maquinistas/{self.pdf_file_maquinistas_name}?download=true',

        'target': 'self',       
    }
        
    def action_download_pdfs(self):

        tipo = self.env.context.get('tipo')
        mes = self.env.context.get('mes') 
        anio = self.env.context.get('anio')  
        
        if not tipo:
            raise UserError("No se proporcionó un tipo válido.")
        if not mes or not anio:
            raise UserError("Debe especificar el mes y el año para la descarga.")


        criterios = {
            'quinta_chica': {
                'name': 'QUINTA CHICA - CONAK CIA. LTDA',
                'pdf_field': 'pdf_file_sala_situacional',
                'name_field': 'pdf_file_sala_situacional_name'
            },
            'gapal': {
                'name': 'GAPAL - COMERCIAL PALACIOS REYES CIA. LTDA',
                'pdf_field': 'pdf_file_sala_situacional',
                'name_field': 'pdf_file_sala_situacional_name'
            },
            'eloy_alfaro': {
                'name': 'ELOY ALFARO - KIESEL S.A.',
                'pdf_field': 'pdf_file_sala_situacional',
                'name_field': 'pdf_file_sala_situacional_name'
            },
        }

        if tipo not in criterios:
            raise UserError("El tipo proporcionado no es válido.")

        criterio = criterios[tipo]


        registros = self.search([
            ('fuel_tank_id.name', '=', criterio['name']),
            ('date', '>=', f'{anio}-{mes.zfill(2)}-01'),
            ('date', '<', f'{anio}-{int(mes.zfill(2)) + 1}-01')
        ])
        if not registros:
            raise UserError(f"No se encontraron registros para {criterio['name']} en {mes}/{anio}.")


        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:

            for record in registros:
                pdf_data = getattr(record, criterio['pdf_field'], False)
                pdf_name = getattr(record, criterio['name_field'], False)
                if pdf_data and pdf_name:
                    zip_file.writestr(pdf_name, base64.b64decode(pdf_data))


        if not zip_buffer.getbuffer().nbytes:
            raise UserError("No se encontraron archivos PDF para los criterios especificados.")


        zip_buffer.seek(0)
        zip_base64 = base64.b64encode(zip_buffer.read())

        return {
            'type': 'ir.actions.act_url',
            'url': f'/download/fleet_pdfs?tipo={tipo}&mes={mes}&anio={anio}',
            'target': 'self',
        }
        

    @api.model
    def default_get(self, default_fields):
        res = super(FleetVehicleLogFuel, self).default_get(default_fields)
        service = self.env.ref('fleet.type_service_refueling', raise_if_not_found=False)
        res.update({
            'date': fields.Date.context_today(self),
            'cost_subtype_id': service and service.id or False,
            'cost_type': 'fuel'
        })
        return res
    name = fields.Char(string="Codigo")
    liter = fields.Float(string='Galones', required=True, default=None)
    price_per_liter = fields.Float(string='Precio por Galon', digits = (12,4))
    purchaser_id = fields.Many2one('res.partner', string='Proveedor')
    inv_ref = fields.Integer(string='Referencia de Factura', required=True, default=None)
    vendor_id = fields.Many2one('res.partner', string='Vendedor')
    notes = fields.Text()
    cost_id = fields.Many2one('fleet.vehicle.cost', string='Costo', required=True, ondelete='cascade')
    cost_amount = fields.Float(related='cost_id.amount', string='Monto', store=True, readonly=False)
    odometer_id = fields.Many2one('fleet.vehicle.odometer', string='Odometro', help='Medida del odometro del vehículo al momento de este registro')
    date_solicitud = fields.Datetime(
            string='Fecha Solicitud',
            required=True,
            default=lambda self: fields.datetime.now()
        )
    confirm_by = fields.Many2one(
        'res.users',
        string="Confirmado por",
        readonly=True,
        copy=False
    )
    confirm_date = fields.Datetime(
        string="Fecha confirmada",
        readonly=True,
        copy=False
    )
    approve_date = fields.Datetime(
        string="Fecha aprobación",
        readonly=True,
        copy=False
    )
    approve_by = fields.Many2one(
        'res.users',
        string="Aprobado por",
        readonly=True,
        copy=False
    )
    fire_station = fields.Selection([('adm', 'Administrativo'),
                                        ('est1', 'Estación 1'),
                                        ('est2', 'Estación 2'),
                                        ('est3', 'Estación 3'),
                                        ('est4', 'Estación 4'),
                                        ('est5', 'Estación 5'),
                                        ('est6', 'Estación 6'),
                                        ('est7', 'Estación 7'),
                                        ('est8', 'Estación 8'),
                                        ('est9', 'Estación 9'),
                                        ('est10', 'Estación 10'),
                                        ('est11', 'Estación 11'),
                                        ('est12', 'Estación 12'),
                                        ('est13', 'Estación 13')],

                                        string='Estación',
                                        help='Estacion de Bomberos', required=True)
    fin_date = fields.Datetime(
        string="Fecha Finalización",
        readonly=True,
        copy=False
    )
    fin_by = fields.Many2one(
        'res.users',
        string="Finalizado por",
        readonly=True,
        copy=False
    )
    qr_code = fields.Binary('QRcode', 
        compute="_generate_qr"
    )
    charging_mileage = fields.Integer(
        string='Kilometraje de carga',
        help='Kilometraje de carga',
        required=True,
        default=None
    )
    arrival_mileage = fields.Integer(
        string='Kilometraje de llegada',
        help='Kilometraje de llegada',
        required=True,
        default=None
    )
    vehicle_code = fields.Char(
        string="Código del Vehículo",
        store=True
    )
    gasoline_type = fields.Selection([('extra_eco', 'Extra - Eco'),
                                        ('super', 'Super'),
                                        ('diesel', 'Diesel')],
                                        string='Tipo de gasolina',
                                        help='Tipo de gasolina', required=True, default=None)
    
    @api.constrains('inv_ref')
    def _check_inv_ref(self):
        for record in self:
            if not record.show_subscription_info:
                continue  


            if record.inv_ref == 0:
                raise ValidationError(
                    'El campo Referencia de factura no puede ser cero o estar vacío. '
                    'Recuerde ingresar únicamente los 4 últimos dígitos del número de factura.'
                )


            if not re.fullmatch(r'\d{4}', str(record.inv_ref)):
                raise ValidationError(
                    'La Referencia de factura debe contener exactamente 4 dígitos.'
                )
    

    
    @api.constrains('liter')       
    def _check_liter(self):
        for record in self:
            if not record.show_subscription_info:
                continue  
            if record.liter <= 0:
                raise ValidationError('El campo Galones no puede ser cero o estar vacío. '
                                    'En caso de requerirlo, recuerde utilizar únicamente el punto "." como separador decimal.')
    
    @api.constrains('amount')         
    def _check_amount(self):
        for record in self:
            if not record.show_subscription_info:
                continue  
            if record.amount <= 0:
                raise ValidationError('El campo Valor Subtotal no puede ser cero o estar vacío. En caso de requerirlo, recuerde utilizar únicamente el punto "." como separador decimal.')
    
    @api.constrains('charging_mileage')
    def _check_charging_mileage(self):
        for record in self:
            if not record.show_subscription_info:
                continue  

            last_record = self.search(
                [('vehicle_id', '=', record.vehicle_id.id), ('id', '!=', record.id)],
                limit=1, order="id desc"
            )


            if last_record and record.charging_mileage <= last_record.charging_mileage:
                raise ValidationError(
                    "El valor de 'Kilometraje de carga' debe ser mayor al del último registro: %s." % last_record.charging_mileage
                )


            if record.charging_mileage <= 0:
                raise ValidationError(
                    "El campo 'Kilometraje de carga' no puede ser cero o estar vacío. "
                    "En caso de tratarse de un Bidón, ingrese el número 1."
                )

    @api.constrains('arrival_mileage')
    def _check_arrival_mileage(self):
        for record in self:
            if not record.show_subscription_info:
                continue  


            last_record = self.search(
                [('vehicle_id', '=', record.vehicle_id.id), ('id', '!=', record.id)],
                limit=1, order="id desc"
            )


            if last_record and record.arrival_mileage <= last_record.arrival_mileage:
                raise ValidationError(
                    "El valor de 'Kilometraje de llegada' debe ser mayor al del último registro: %s." % last_record.arrival_mileage
                )

            if record.arrival_mileage <= 0:
                raise ValidationError(
                    "El campo 'Kilometraje de llegada' no puede ser cero o estar vacío. "
                    "En caso de tratarse de un Bidón, ingrese el número 1."
                )
    
    @api.constrains("prev_odo")
    def _check_prev_odo(self):
        for record in self:

            last_record = self.search(
                [('vehicle_id', '=', record.vehicle_id.id), ('id', '!=', record.id)],
                limit=1, order="id desc"
            )


            if last_record and record.prev_odo <= last_record.prev_odo:
                raise ValidationError(
                    "El valor de 'Kilometraje de salida' debe ser mayor al del último registro: %s." % last_record.prev_odo
                )


            if record.prev_odo <= 0:
                raise ValidationError(
                    "El valor de 'Kilometraje de salida' no puede ser 0."
                )

    @api.constrains('fuel_tank_id') 
    def _check_fuel_tank_id(self):
        for record in self:
            if record.fuel_tank_id.id == 10:
                raise ValidationError('Seleccione una opción en el campo Gasolinera')
    
    @api.onchange('vehicle_id')
    def _onchange_vehicle(self):
        if self.vehicle_id:
            self.odometer_unit = self.vehicle_id.odometer_unit
            self.purchaser_id = self.vehicle_id.driver_id.id

    @api.onchange('liter', 'price_per_liter', 'amount')
    def _onchange_liter_price_amount(self):
        liter = float(self.liter)
        price_per_liter = float(self.price_per_liter)
        amount = float(self.amount)
        
        if amount > 0 and liter > 0 and (amount / liter) != price_per_liter:
            self.price_per_liter = amount / liter



    def action_cancel(self):
        for rec in self:
            rec.state = 'cancel'

    def action_confirm(self):
        for rec in self:
            rec.confirm_date =  fields.datetime.now()
            rec.confirm_by = rec.env.uid
            rec.write({'state': 'b_confirm'})


            domain = [  
                ('id', '=', 9)
            ]
            idusuario=self.env['res.users'].search(domain)
            if len(idusuario) > 0:
                idusua = 9
            else:
                idusua = 290

            rec.approve_date =  fields.datetime.now()
            rec.approve_by = idusua
            rec.write({'state': 'c_approve'})

    def action_approve(self):
        for rec in self:
            rec.approve_date =  fields.datetime.now()
            rec.approve_by = rec.env.uid
            rec.write({'state': 'c_approve'})
            
    def action_fin(self):
        for rec in self:
            rec.fin_date =  fields.datetime.now()
            rec.fin_by = rec.env.uid
            rec.write({'state': 'f_fin'})

    def action_firma(self):
        self.ensure_one()
        self.is_firma_digital_clicked = True  
        return self.env.ref('fleet_fuel_tank.report_fleet_vehicle_log_fuel').report_action(self)
    
    def action_imprimir(self):
        self.ensure_one()
        self.button_clicked = True  
        return self.env.ref('fleet_fuel_tank.report_fleet_vehicle_log_fuel_imp').report_action(self)
    


    def _generate_qr(self):
        for rec in self:
            if qrcode and base64:

                ecuador_tz = pytz.timezone("America/Guayaquil")
                

                if rec.approve_date:
                    approve_date_utc = rec.approve_date
                    approve_date_local = approve_date_utc.astimezone(ecuador_tz)

                    formatted_approve_date = approve_date_local.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    formatted_approve_date = "Sin fecha de aprobación"
                

                if rec.date_solicitud:
                    date_solicitud_utc = rec.date_solicitud
                    date_solicitud_local = date_solicitud_utc.astimezone(ecuador_tz)

                    formatted_date_solicitud = date_solicitud_local.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    formatted_date_solicitud = "Sin fecha de solicitud"
                

                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=3,
                    border=4,
                )

                qr.add_data("Orden Num: ")
                qr.add_data(rec.name)
                qr.add_data(", Estado: ")
                qr.add_data(rec.state)
                qr.add_data(", Fecha de solicitud: ")
                qr.add_data(formatted_date_solicitud)  
                qr.add_data(", Fecha de aprobación: ")
                qr.add_data(formatted_approve_date)  
                qr.add_data(", Aprobado por: ")
                qr.add_data(rec.approve_by.name if rec.approve_by else "N/A")
                qr.add_data(", Maquinista: ")
                qr.add_data(rec.employee_id.name if rec.employee_id else "N/A")
                qr.make(fit=True)
                

                img = qr.make_image()
                temp = BytesIO()
                img.save(temp, format="PNG")
                qr_image = base64.b64encode(temp.getvalue())
                

                rec.update({'qr_code': qr_image})
            else:
                raise UserError(_('No se cumplen los requisitos necesarios para ejecutar esta operación'))

    class FleetVehicleLogFuelController(Controller):

        @route('/download/fleet_pdfs', type='http', auth='user')
        def download_fleet_pdfs(self, tipo, mes=None, anio=None, **kwargs):

            criterios = {
                'quinta_chica': {
                    'name': 'QUINTA CHICA - CONAK CIA. LTDA',
                    'pdf_field': 'pdf_file_sala_situacional',
                    'name_field': 'pdf_file_sala_situacional_name'
                },
                'gapal': {
                    'name': 'GAPAL - COMERCIAL PALACIOS REYES CIA. LTDA',
                    'pdf_field': 'pdf_file_sala_situacional',
                    'name_field': 'pdf_file_sala_situacional_name'
                },
                'eloy_alfaro': {
                    'name': 'ELOY ALFARO - KIESEL S.A.',
                    'pdf_field': 'pdf_file_sala_situacional',
                    'name_field': 'pdf_file_sala_situacional_name'
                },
            }


            if tipo not in criterios:
                return request.not_found()


            if not mes or not anio:
                return request.make_response(
                    "Debe especificar el mes y el año como parámetros en la URL.",
                    headers=[('Content-Type', 'text/plain')],
                )

            try:
                mes = int(mes)
                anio = int(anio)
            except ValueError:
                return request.make_response(
                    "El mes y el año deben ser números válidos.",
                    headers=[('Content-Type', 'text/plain')],
                )


            if mes < 1 or mes > 12:
                return request.make_response(
                    "El mes debe estar entre 1 y 12.",
                    headers=[('Content-Type', 'text/plain')],
                )


            start_date = f"{anio}-{str(mes).zfill(2)}-01"
            end_date = f"{anio}-{str(mes + 1).zfill(2)}-01" if mes < 12 else f"{anio + 1}-01-01"


            criterio = criterios[tipo]


            registros = request.env['fleet.vehicle.log.fuel'].search([
                ('fuel_tank_id.name', '=', criterio['name']),
                ('date', '>=', start_date),
                ('date', '<', end_date)
            ])

            if not registros:
                return request.make_response(
                    f"No se encontraron registros para {criterio['name']} en {mes}/{anio}.",
                    headers=[('Content-Type', 'text/plain')],
                )


            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for record in registros:
                    pdf_data = getattr(record, criterio['pdf_field'])
                    pdf_name = getattr(record, criterio['name_field'])
                    if pdf_data and pdf_name:
                        zip_file.writestr(pdf_name, base64.b64decode(pdf_data))


            zip_buffer.seek(0)
            return request.make_response(
                zip_buffer.getvalue(),
                headers=[
                    ('Content-Type', 'application/zip'),
                    ('Content-Disposition', f'attachment; filename="{tipo}_{mes}_{anio}.zip"'),
                ]
            )
            