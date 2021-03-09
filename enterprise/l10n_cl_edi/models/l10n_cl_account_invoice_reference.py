# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class AccountInvoiceReference(models.Model):
    _name = 'l10n_cl.account.invoice.reference'
    _description = 'Cross Reference Docs for Chilean Electronic Invoicing'
    _rec_name = 'origin_doc_number'

    # these referenced documents are going to be changed in master, to a relation with latam document types
    # this was made to override the active documents in the latam document type model
    reference_documents = [
        ('29', '(29) Factura de Inicio'),
        ('30', '(30) Factura'),
        ('32', '(32) Factura de Ventas y Servicios no Afectos o Exentos de IVA'),
        ('33', '(33) Factura Electrónica'),
        ('34', '(34) Factura no Afecta o Exenta Electrónica'),
        ('35', '(35) Boleta de Venta'),
        ('38', '(38) Boleta exenta'),
        ('39', '(39) Boleta Electrónica'),
        ('40', '(40) Liquidación Factura'),
        ('41', '(41) Boleta Exenta Electrónica'),
        ('43', '(43) Liquidación Factura Electrónica'),
        ('45', '(45) Factura de Compra'),
        ('46', '(46) Factura de Compra Electrónica'),
        ('50', '(50) Guía de Despacho'),
        ('52', '(52) Guía de Despacho Electrónica'),
        ('55', '(55) Nota de Débito'),
        ('56', '(56) Nota de Débito Electrónica'),
        ('60', '(60) Nota de Crédito'),
        ('61', '(61) Nota de Crédito Electrónica'),
        ('70', '(70) Boleta de Honorarios'),
        ('71', '(71) Boleta de Honorarios Electrónica'),
        ('103', '(103) Liquidación'),
        ('108', '(108) SRF Solicitud de Registro de Factura'),
        ('110', '(110) Factura de Exportación Electrónica'),
        ('111', '(111) Nota de Débito de Exportación Electrónica'),
        ('112', '(112) Nota de Crédito de Exportación Electrónica'),
        ('500', '(500) Ajuste aumento Tipo de Cambio (código 500)'),
        ('501', '(501) Ajuste disminución Tipo de Cambio (código 501)'),
        ('801', '(801) Orden de Compra'),
        ('802', '(802) Nota de pedido'),
        ('803', '(803) Contrato'),
        ('804', '(804) Resolución'),
        ('805', '(805) Proceso ChileCompra'),
        ('806', '(806) Ficha ChileCompra'),
        ('807', '(807) DUS'),
        ('808', '(808) B/L (Conocimiento de embarque)'),
        ('809', '(809) AWB Airway Bill'),
        ('810', '(810) MIC/DTA'),
        ('811', '(811) Carta de Porte'),
        ('812', '(812) Resolución del SNA donde califica Servicios de Exportación'),
        ('813', '(813) Pasaporte'),
        ('814', '(814) Certificado de Depósito Bolsa Prod. Chile.'),
        ('815', '(815) Vale de Prenda Bolsa Prod. Chile'),
        ('901', '(901) Factura de ventas a empresas del territorio preferencial Res. Ex. N° 1057'),
        ('902', '(902) Conocimiento de Embarque (Marítimo o aéreo)'),
        ('903', '(903) Documento Único de Salida (DUS)'),
        ('904', '(904) Factura de Traspaso'),
        ('905', '(905) Factura de Reexpedición'),
        ('906', '(906) Boletas Venta Módulos ZF (todas)'),
        ('907', '(907) Facturas Venta Módulo ZF (todas)'),
        ('911', '(911) Declaración de Ingreso a Zona Franca Primaria'),
        ('914', '(914) Declaración de Ingreso (DIN)'),
        ('919', '(919) Resumen Ventas de nacionales pasajes sin Factura'),
        ('HEM', '(HEM) Hoja de Entrada de Materiales (HEM)'),
        ('HES', '(HES) Hoja de Entrada de Servicio (HES)'),
        ('MIG', '(MIG) Movimiento de Mercancías (MIGO)'),
        ('CHQ', '(CHQ) Cheque'),
        ('PAG', '(PAG) Pagaré'),
    ]

    origin_doc_number = fields.Char(string='Origin Document Number',
                                    help='Origin document number, the document you are referring to', required=True)
    reference_doc_code = fields.Selection([
            ('1', '1. Cancels Referenced Document'),
            ('2', '2. Corrects Referenced Document Text'),
            ('3', '3. Corrects Referenced Document Amount')
    ], string='SII Reference Code',
        help='Use one of these codes for credit or debit notes that intend to change taxable data in the origin '
             'referred document')
    l10n_cl_reference_doc_type_selection = fields.Selection(reference_documents, string='SII Doc Type Selector',
                                                            required=True)
    reason = fields.Char(string='Reason')
    move_id = fields.Many2one('account.move', ondelete='cascade', string='Originating Document')
    date = fields.Date(string='Document Date', required=True)
