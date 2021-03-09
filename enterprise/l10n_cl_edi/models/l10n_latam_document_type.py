from odoo import models


class L10nLatamDocumentType(models.Model):

    _inherit = 'l10n_latam.document.type'

    def _is_doc_type_ticket(self):
        return self.code in ['35', '38', '39', '41', '70', '71']

    def _is_doc_type_voucher(self):
        return self.code in ['35', '39', '906', '45', '46', '70', '71']

    def _is_doc_type_exempt(self):
        return self.code in ['34', '110', '111', '112']

    def _is_doc_type_export(self):
        return self.code in ['110', '111', '112']

    def _is_doc_type_acceptance(self):
        """
        Check if the document type can be accepted or claimed
        """
        return self.code in ['33', '34', '56', '61', '43']

