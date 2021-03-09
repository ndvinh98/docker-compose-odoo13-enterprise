# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from .account_batch_payment import check_valid_SEPA_str
from .account_journal import sanitize_communication

class ResCompany(models.Model):
    _inherit = "res.company"

    # TODO : complete methods _default_sepa_origid_id and _default_sepa_origid_issr for all countries of the SEPA

    def _default_sepa_origid_issr(self):
        """ DEPRECATED, done by _compute_sepa_origid
            Set default value for the field sepa_orgid_issr, which correspond to the field 'Issuer'
            of an 'OrganisationIdentification', as described in ISO 20022.
        """
        if self.partner_id.country_id.code == 'BE':
            return 'KBO-BCE'

    def _default_sepa_origid_id(self):
        """ DEPRECATED, done by _compute_sepa_origid
            Set default value for the fields sepa_orgid_id, which correspond to the field 'Identification'
            of an 'OrganisationIdentification', as described in ISO 20022.
        """
        if self.partner_id.country_id.code == 'BE' and self.partner_id.vat:
            return self.partner_id.vat[:2].upper() + self.partner_id.vat[2:].replace(' ', '')

    def _default_sepa_pain_version(self):
        """ DEPRECATED, done by _compute_sepa_pain_version
            Set default value for the field sepa_pain_version
        """
        if self.partner_id.country_id.code == 'DE':
            return 'pain.001.003.03'
        if self.partner_id.country_id.code == 'CH':
            return 'pain.001.001.03.ch.02'
        return 'pain.001.001.03'

    sepa_orgid_id = fields.Char('Identification', size=35, copy=False, compute='_compute_sepa_origid', readonly=False, store=True,
        help="Identification assigned by an institution (eg. VAT number).")
    sepa_orgid_issr = fields.Char('Issuer', size=35, copy=False, compute='_compute_sepa_origid', readonly=False, store=True,
        help="Entity that assigns the identification (eg. KBE-BCO or Finanzamt Muenchen IV).")
    sepa_initiating_party_name = fields.Char('Your Company Name', size=70, copy=False,
        help="Will appear in SEPA payments as the name of the party initiating the payment. Limited to 70 characters.")
    sepa_pain_version = fields.Selection([('pain.001.001.03', 'Generic'), ('pain.001.001.03.ch.02', 'Swiss Version'), ('pain.001.003.03', 'German Version')],
                                         string='SEPA Pain Version', help='SEPA may be a generic format, some countries differ from the SEPA recommandations made by the EPC (European Payment Councile) and thus the XML created need some tweakenings.',
                                         required=True,
                                         default='pain.001.001.03',
                                         compute='_compute_sepa_pain_version')
    @api.model
    def create(self, vals):
        # Overridden in order to set the name of the company as default value
        # for sepa_initiating_party_name field
        name = vals.get('name')
        if name and 'sepa_initiating_party_name' not in vals:
            vals['sepa_initiating_party_name'] = sanitize_communication(name)

        return super(ResCompany, self).create(vals)

    @api.depends('partner_id.country_id')
    def _compute_sepa_origid(self):
        """ Set default value for :
            - sepa_orgid_issr, which correspond to the field 'Issuer' of an 'OrganisationIdentification', as described in ISO 20022.
            - sepa_orgid_id, which correspond to the field 'Identification' of an 'OrganisationIdentification', as described in ISO 20022.
        """
        for company in self:
            if company.partner_id.country_id.code == 'BE':
                company.sepa_orgid_issr = 'KBO-BCE'
                company.sepa_orgid_id = company.vat[:2].upper() + company.vat[2:].replace(' ', '') if company.vat else ''
            else:
                company.sepa_orgid_issr = ''
                company.sepa_orgid_id = ''

    @api.depends('partner_id.country_id')
    def _compute_sepa_pain_version(self):
        """ Set default value for the field sepa_pain_version"""
        for company in self:
            if company.country_id.code == 'DE':
                company.sepa_pain_version = 'pain.001.003.03'
            if company.country_id.code == 'CH':
                company.sepa_pain_version = 'pain.001.001.03.ch.02'
            else:
                company.sepa_pain_version = 'pain.001.001.03'

    @api.constrains('sepa_orgid_id', 'sepa_orgid_issr', 'sepa_initiating_party_name')
    def _check_sepa_fields(self):
        for rec in self:
            if rec.sepa_orgid_id:
                check_valid_SEPA_str(rec.sepa_orgid_id)
            if rec.sepa_orgid_issr:
                check_valid_SEPA_str(rec.sepa_orgid_issr)
            if rec.sepa_initiating_party_name:
                check_valid_SEPA_str(rec.sepa_initiating_party_name)

    def _onchange_country(self):
        """ DEPRECATED, done by _compute_sepa_origid and _compute_sepa_pain_version"""
        if hasattr(super(ResCompany, self), '_onchange_country'):
            super(ResCompany, self)._onchange_country()
        if not self.sepa_orgid_id:
            self.sepa_orgid_id = self._default_sepa_origid_id()
        if not self.sepa_orgid_issr:
            self.sepa_orgid_issr = self._default_sepa_origid_issr()
        if not self.sepa_pain_version:
            self.sepa_pain_version = self._default_sepa_pain_version()

    @api.model
    def _set_default_sepa_origid_on_existing_companies(self):
        """ DEPRECATED, done by _compute_sepa_origid and _compute_sepa_pain_version"""
        for company in self.search([]):
            company.sepa_orgid_id = company._default_sepa_origid_id()
            company.sepa_orgid_issr = company._default_sepa_origid_issr()
            company.sepa_pain_version = company._default_sepa_pain_version()
