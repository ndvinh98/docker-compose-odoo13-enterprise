# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class AccountJournal(models.Model):

    _inherit = 'account.journal'

    l10n_ar_afip_ws = fields.Selection(selection='_get_l10n_ar_afip_ws', compute='_compute_l10n_ar_afip_ws',
                                       string='AFIP WS')

    def _get_l10n_ar_afip_ws(self):
        return [('wsfe', _('Domestic market -without detail- RG2485 (WSFEv1)')),
                ('wsfex', _('Export -with detail- RG2758 (WSFEXv1)')),
                ('wsbfe', _('Fiscal Bond -with detail- RG2557 (WSBFE)'))]

    def _get_l10n_ar_afip_pos_types_selection(self):
        """ Add more options to the selection field AFIP POS System, re order options by common use """
        res = super()._get_l10n_ar_afip_pos_types_selection()
        res.insert(0, ('RAW_MAW', _('Electronic Invoice - Web Service')))
        res.insert(3, ('BFEWS', _('Electronic Fiscal Bond - Web Service')))
        res.insert(5, ('FEEWS', _('Export Voucher - Web Service')))
        return res

    @api.depends('l10n_ar_afip_pos_system')
    def _compute_l10n_ar_afip_ws(self):
        """ Depending on AFIP POS System selected set the proper AFIP WS """
        type_mapping = {'RAW_MAW': 'wsfe', 'FEEWS': 'wsfex', 'BFEWS': 'wsbfe'}
        for rec in self:
            rec.l10n_ar_afip_ws = type_mapping.get(rec.l10n_ar_afip_pos_system, False)

    def _l10n_ar_create_document_sequences(self):
        """ After creating the document sequences we try to sync document next numbers with the last numbers in AFIP """
        res = super()._l10n_ar_create_document_sequences()
        if self.l10n_ar_afip_ws:
            self.company_id.sudo()._get_key_and_certificate()
            try:
                self.l10n_ar_sync_next_number_with_afip()
            except Exception as error:
                _logger.info(_('Could not synchronize next number with the AFIP last numbers %s'), repr(error))
        return res

    def l10n_ar_sync_next_number_with_afip(self):
        """ In order to generate invoices and report them to AFIP they need to match with the AFIP number: if not the
        invoices will be rejected by AFIP.

        This method avoid the user to manually set all the next numbers of the documents they use in the journal and
        also avoid the error message given to the user that is trying to inform to AFIP an invoice that does not have
        the proper number """
        self.ensure_one()
        if not self.l10n_ar_afip_ws:
            return True
        for sequence in self.l10n_ar_sequence_ids:
            last = self._l10n_ar_get_afip_last_invoice_number(sequence.l10n_latam_document_type_id)
            sequence.sudo().number_next_actual = last + 1

    def l10n_ar_check_afip_pos_number(self):
        """ Return information about the AFIP POS numbers related to the given AFIP WS """
        self.ensure_one()
        connection = self.company_id._l10n_ar_get_connection(self.l10n_ar_afip_ws)
        client, auth = connection._get_client()
        if self.company_id._get_environment_type() == 'testing':
            raise UserError(_('"Check Available AFIP PoS" is not implemented in testing mode for webservice %s') % self.l10n_ar_afip_ws)
        if self.l10n_ar_afip_ws == 'wsfe':
            response = client.service.FEParamGetPtosVenta(auth)
        elif self.l10n_ar_afip_ws == 'wsfex':
            response = client.service.FEXGetPARAM_PtoVenta(auth)
        else:
            raise UserError(_('"Check Available AFIP PoS" is not implemented for webservice %s') % self.l10n_ar_afip_ws)
        raise UserError(response)

    def _l10n_ar_get_afip_last_invoice_number(self, document_type):
        """ Consult via webservice the number of the last invoice register
        :return: integer with the last number register in AFIP for the given document type in this journals AFIP POS
        """
        self.ensure_one()
        pos_number = self.l10n_ar_afip_pos_number
        afip_ws = self.l10n_ar_afip_ws
        connection = self.company_id._l10n_ar_get_connection(afip_ws)
        client, auth = connection._get_client()
        last = errors = False

        # We need to call a different method for every webservice type and assemble the returned errors if they exist
        if afip_ws == 'wsfe':
            response = client.service.FECompUltimoAutorizado(auth, pos_number, document_type.code)
            if response.CbteNro:
                last = response.CbteNro
            if response.Errors:
                errors = response.Errors
        elif afip_ws == 'wsfex':
            data = auth.copy()
            data.update({'Cbte_Tipo': document_type.code, 'Pto_venta': pos_number})
            response = client.service.FEXGetLast_CMP(Auth=data)
            if response.FEXResult_LastCMP.Cbte_nro:
                last = response.FEXResult_LastCMP.Cbte_nro
            if response.FEXErr.ErrCode != 0 or response.FEXErr.ErrMsg != 'OK':
                errors = response.FEXErr
        elif afip_ws == 'wsbfe':
            data = auth.copy()
            data.update({'Tipo_cbte': document_type.code, 'Pto_venta': pos_number})
            response = client.service.BFEGetLast_CMP(Auth=data)
            if response.BFEResult_LastCMP.Cbte_nro:
                last = response.BFEResult_LastCMP.Cbte_nro
            if response.BFEErr.ErrCode != 0 or response.BFEErr.ErrMsg != 'OK':
                errors = response.BFEErr
        else:
            return(_('AFIP WS %s not implemented') % afip_ws)

        if errors:
            raise UserError(_('We receive this error trying to consult the last invoice number to AFIP:\n%s') % str(errors))
        return last
