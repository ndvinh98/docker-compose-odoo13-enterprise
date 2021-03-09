# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    def _modify_and_validate_xsd_content(self, module_name, content):
        xsd_object = super()._modify_and_validate_xsd_content(module_name, content)
        if not len(xsd_object) or module_name != 'l10n_lu_saft':
            return xsd_object
        # Luxembourge government does not accept FAIA files without `xmlns` attribute for
        # it's root element, which is, `xs:schema`. And the XSD file available on their
        # portal itself does not have this attribute. Furthermore, they refused to update
        # the file with the said attribute on their portal. So, we are using below hack to
        # set `xmlns` attribute in the XSD file after we downloaded from their portal. This
        # will ensure `xmlns` attribute's presense by validating FAIA XML with XSD using
        # tools.xml_utils._check_with_xsd() call.
        [tree] = xsd_object.xpath('//xs:schema', namespaces={'xs': 'http://www.w3.org/2001/XMLSchema'})
        if 'xmlns' not in tree.attrib:
            tree.attrib['xmlns'] = "urn:OECD:StandardAuditFile-Taxation/2.00"
        if 'targetNamespace' not in tree.attrib:
            tree.attrib['targetNamespace'] = "urn:OECD:StandardAuditFile-Taxation/2.00"
        return xsd_object
