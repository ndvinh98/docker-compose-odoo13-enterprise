# -*- coding: utf-8 -*-

import base64
import io
import os
from odoo import models, fields, api, modules, exceptions, _
from PyPDF2 import PdfFileWriter, PdfFileReader


class IrAttachment(models.Model):
    _inherit = ['ir.attachment']

    def _make_pdf(self, output, name_ext):
        """
        :param output: PdfFileWriter object.
        :param name_ext: the additional name of the new attachment (page count).
        :return: the id of the attachment.
        """
        self.ensure_one()
        try:
            stream = io.BytesIO()
            output.write(stream)
            return self.with_context(no_document=True).copy({
                'name': os.path.splitext(self.name)[0]+'-'+name_ext+".pdf",
                'datas': base64.b64encode(stream.getvalue()),
            })
        except Exception:
            raise Exception

    def _split_pdf_groups(self, pdf_groups=None, remainder=False):
        """
        calls _make_pdf to create the a new attachment for each page section.
        :param pdf_groups: a list of lists representing the pages to split:  pages = [[1,1], [4,5], [7,7]]
        :returns the list of the ID's of the new PDF attachments.

        """
        self.ensure_one()
        with io.BytesIO(base64.b64decode(self.datas)) as stream:
            try:
                input_pdf = PdfFileReader(stream)
                max_page = input_pdf.getNumPages()
            except Exception:
                raise exceptions.ValidationError(_(
                    "The PDF file could not be parsed. Fix the PDF with an external tool then try again."
                ))
            remainder_set = set(range(0, max_page))
            new_pdf_ids = []
            if not pdf_groups:
                pdf_groups = []
            for pages in pdf_groups:
                pages[1] = min(max_page, pages[1])
                pages[0] = min(max_page, pages[0])
                if pages[0] == pages[1]:
                    name_ext = "%s" % (pages[0],)
                else:
                    name_ext = "%s-%s" % (pages[0], pages[1])
                output = PdfFileWriter()
                for i in range(pages[0]-1, pages[1]):
                    output.addPage(input_pdf.getPage(i))
                new_pdf_id = self._make_pdf(output, name_ext)
                new_pdf_ids.append(new_pdf_id)
                remainder_set = remainder_set.difference(set(range(pages[0] - 1, pages[1])))
            if remainder:
                for i in remainder_set:
                    output_page = PdfFileWriter()
                    name_ext = "%s" % (i + 1,)
                    output_page.addPage(input_pdf.getPage(i))
                    new_pdf_id = self._make_pdf(output_page, name_ext)
                    new_pdf_ids.append(new_pdf_id)
            return new_pdf_ids

    def split_pdf(self, indices=None, remainder=False):
        """
        called by the Document Viewer's Split PDF button.
        evaluates the input string and turns it into a list of lists to be processed by _split_pdf_groups

        :param indices: the formatted string of pdf split (e.g. 1,5-10, 8-22, 29-34) o_page_number_input
        :param remainder: bool, if true splits the non specified pages, one by one. form checkbox o_remainder_input
        :returns the list of the ID's of the newly created pdf attachments.
        """
        self.ensure_one()
        if 'pdf' not in self.mimetype:
            raise exceptions.ValidationError(_("ERROR: the file must be a PDF"))
        if indices:
            try:
                pages = [[int(x) for x in x.split('-')] for x in indices.split(',')]
            except ValueError:
                raise exceptions.ValidationError(_("ERROR: Invalid list of pages to split. Example: 1,5-9,10"))
            return self._split_pdf_groups(pdf_groups=[[min(x), max(x)] for x in pages], remainder=remainder)
        return self._split_pdf_groups(remainder=remainder)

    def _create_document(self, vals):
        """
        Implemented by bridge modules that create new documents if attachments are linked to
        their business models.

        :param vals: the create/write dictionary of ir attachment
        :return True if new documents are created
        """
        # Special case for documents
        if vals.get('res_model') == 'documents.document' and vals.get('res_id'):
            document = self.env['documents.document'].browse(vals['res_id'])
            if document.exists() and not document.attachment_id:
                document.attachment_id = self[0].id
            return False

        # Generic case for all other models
        res_model = vals.get('res_model')
        res_id = vals.get('res_id')
        model = self.env.get(res_model)
        if model is not None and res_id and issubclass(type(model), self.pool['documents.mixin']):
            vals_list = [
                model.browse(res_id)._get_document_vals(attachment)
                for attachment in self
                if not attachment.res_field
            ]
            vals_list = [vals for vals in vals_list if vals]  # Remove empty values
            self.env['documents.document'].create(vals_list)
            return True
        return False

    @api.model
    def create(self, vals):
        attachment = super(IrAttachment, self).create(vals)
        # the context can indicate that this new attachment is created from documents, and therefore
        # doesn't need a new document to contain it.
        if not self._context.get('no_document') and not attachment.res_field:
            attachment._create_document(dict(vals, res_model=attachment.res_model, res_id=attachment.res_id))
        return attachment

    def write(self, vals):
        if not self._context.get('no_document'):
            self.filtered(lambda a: not (vals.get('res_field') or a.res_field))._create_document(vals)
        return super(IrAttachment, self).write(vals)


