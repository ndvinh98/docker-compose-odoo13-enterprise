# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import common, tagged
import base64
import requests


@tagged('post_install', '-at_install', 'external', '-standard')
class TestWinbooksImport(common.TransactionCase):

    def download_test_db(self):
        url = 'https://s3.amazonaws.com/winbooks-public/softwares/winbooks-classic-and-virtual-invoice/Tools/PARFILUX_2013.04.08.zip'
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        attachment = self.env['ir.attachment'].create({
            'datas': base64.b64encode(response.content),
            'name': 'PARFILUX_2013.04.08.zip',
            'mimetype': 'application/zip',
        })

    def test_winbooks_import(self):
        self.download_test_db()
        test_company = self.env['res.company'].create({
            'name': 'My Winbooks Company',
            'currency_id': self.env['res.currency'].search([('name', '=', 'EUR')]).id,
            'country_id': self.env.ref('base.be').id,
        })
        attachment = self.env['ir.attachment'].search([('name', '=', 'PARFILUX_2013.04.08.zip')])
        wizard = self.env['account.winbooks.import.wizard'].with_context(allowed_company_ids=[test_company.id]).create({
            'zip_file': attachment.datas,
        })
        wizard.with_context(allowed_company_ids=[test_company.id]).import_winbooks_file()

        self.assertTrue(self.env['account.move'].search([('company_id', '=', test_company.id)], limit=1))
