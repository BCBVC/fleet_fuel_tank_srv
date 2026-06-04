
{
    "name" : "Integración del tanque de combustible con la gestión de flotas ",
    "version" : "15.0.0.0",
    "category" : "industries",
    "summary": 'Gestión del depósito de combustible de la flota Gestión del depósito de combustible del vehículo Gestión del depósito del vehículo Gestión del depósito del vehículo con la flota Consumo de combustible del vehículo Consumo de combustible del coche cisterna Tanque de combustible del coche Consumo del vehículo del depósito de combustible del vehículo',
    'description': """
   odoo Administración de tanques de combustible de flota Administración de tanques de flota Administre el tanque de combustible con la administración de flotas.
    Combustible de vehículos odoo Gestión de depósitos Gestión de depósitos de vehículos Gestione los depósitos de vehículos con la gestión de flotas.
    odoo car fuel Gestión de depósitos gestión de depósitos de vehículos Gestione los depósitos de vehículos con la gestión de flotas.

    odoo Consumo de combustible de flota Gestión de tanques Gestión de tanques de consumo de flota Administre el tanque de consumo de combustible con la gestión de flotas.
    odoo consumo de combustible del vehículo Gestión del tanque consumo del vehículo gestión del tanque Administre el consumo de combustible del vehículo con la gestión del consumo de la flota.
    odoo consumo de combustible del automóvil Gestión del tanque consumo de combustible del automóvil administración del tanque Administre el tanque del automóvil con la gestión de flotas.

Este es un módulo de gestión de combustible muy útil, especialmente las empresas de gestión de flotas requerirán un módulo,

El módulo mantiene registros de todos los llenados por diferentes vehículos, cuánto consumo para un vehículo en particular y también muestra su historial,

Esto puede ser útil para realizar un seguimiento del consumo de combustible.

Odoo vehículo consumo de combustible flota consumo de combustible vehículo
Consumo de combustible del automóvil Odoo Combustible en el consumo del vehículo Combustible en el automóvil
""",
    "author": "TLGA. JOHANNA QUINDE ABRIL - ANALISTA SENIOR DISEÑADOR DESARROLLO - BCBVC - 2024",
    "website" : "https://www.bomberos.gob.ec",
    'price': 79,
    'currency': "USD",
    'depends': ['base','fleet','hr'],
    'data': [
        "security/ir.model.access.csv",
        'security/fleet_security.xml',
        'views/fleet_vehicle_log_fuel.xml',
        'views/add_liters.xml',
        'views/fleet_tank_view.xml',
        'views/fleet_combustible_report.xml',
         'views/fleet_combustible_reportimp.xml',
    ],
    "auto_install": False,
    "application": True,
    "installable": True,
    "live_test_url":'https://youtu.be/GGKLVj4yzow',
    "images":['static/description/Banner.gif'],
    "license":'OPL-1',
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
