# -*- coding: utf-8 -*-

import base64
import zipfile
import io
import json
import logging
import os

from odoo import http
from odoo.exceptions import AccessError
from odoo.http import request, content_disposition
from odoo.tools.translate import _
from odoo.tools import image_process
from odoo.addons.web.controllers.main import Binary

logger = logging.getLogger(__name__)


class ShareRoute(http.Controller):

    # util methods #################################################################################

    def _neuter_mimetype(self, mimetype, user):
        wrong_type = 'ht' in mimetype or 'xml' in mimetype or 'svg' in mimetype
        if wrong_type and not user._is_system():
            return 'text/plain'
        return mimetype

    def binary_content(self, id, env=None, field='datas', share_id=None, share_token=None,
                       download=False, unique=False, filename_field='name'):
        env = env or request.env
        record = env['documents.document'].browse(int(id))
        filehash = None

        if share_id:
            share = env['documents.share'].sudo().browse(int(share_id))
            record = share._get_documents_and_check_access(share_token, [int(id)], operation='read')
        if not record:
            return (404, [], None)

        #check access right
        try:
            last_update = record['__last_update']
        except AccessError:
            return (404, [], None)

        mimetype = False
        if record.type == 'url' and record.url:
            module_resource_path = record.url
            filename = os.path.basename(module_resource_path)
            status = 301
            content = module_resource_path
        else:
            status, content, filename, mimetype, filehash = env['ir.http']._binary_record_content(
                record, field=field, filename=None, filename_field=filename_field,
                default_mimetype='application/octet-stream')
        status, headers, content = env['ir.http']._binary_set_headers(
            status, content, filename, mimetype, unique, filehash=filehash, download=download)

        return status, headers, content

    def _get_file_response(self, id, field='datas', share_id=None, share_token=None):
        """
        returns the http response to download one file.

        """

        status, headers, content = self.binary_content(
            id, field=field, share_id=share_id, share_token=share_token, download=True)

        if status != 200:
            return request.env['ir.http']._response_by_status(status, headers, content)
        else:
            content_base64 = base64.b64decode(content)
            headers.append(('Content-Length', len(content_base64)))
            response = request.make_response(content_base64, headers)

        return response

    def _make_zip(self, name, documents):
        """returns zip files for the Document Inspector and the portal.

        :param name: the name to give to the zip file.
        :param documents: files (documents.document) to be zipped.
        :return: a http response to download a zip file.
        """
        stream = io.BytesIO()
        try:
            with zipfile.ZipFile(stream, 'w') as doc_zip:
                for document in documents:
                    if document.type != 'binary':
                        continue
                    status, content, filename, mimetype, filehash = request.env['ir.http']._binary_record_content(
                        document, field='datas', filename=None, filename_field='name',
                        default_mimetype='application/octet-stream')
                    doc_zip.writestr(filename, base64.b64decode(content),
                                     compress_type=zipfile.ZIP_DEFLATED)
        except zipfile.BadZipfile:
            logger.exception("BadZipfile exception")

        content = stream.getvalue()
        headers = [
            ('Content-Type', 'zip'),
            ('X-Content-Type-Options', 'nosniff'),
            ('Content-Length', len(content)),
            ('Content-Disposition', content_disposition(name))
        ]
        return request.make_response(content, headers)

    # Download & upload routes #####################################################################

    @http.route('/documents/upload_attachment', type='http', methods=['POST'], auth="user")
    def upload_document(self, folder_id, ufile, document_id=False, partner_id=False, owner_id=False):
        files = request.httprequest.files.getlist('ufile')
        result = {'success': _("All files uploaded")}
        if document_id:
            document = request.env['documents.document'].browse(int(document_id))
            ufile = files[0]
            try:
                data = base64.encodestring(ufile.read())
                mimetype = self._neuter_mimetype(ufile.content_type, http.request.env.user)
                document.write({
                    'name': ufile.filename,
                    'datas': data,
                    'mimetype': mimetype,
                })
            except Exception as e:
                logger.exception("Fail to upload document %s" % ufile.filename)
                result = {'error': str(e)}
        else:
            vals_list = []
            for ufile in files:
                try:
                    mimetype = self._neuter_mimetype(ufile.content_type, http.request.env.user)
                    datas = base64.encodebytes(ufile.read())
                    vals = {
                        'name': ufile.filename,
                        'mimetype': mimetype,
                        'datas': datas,
                        'folder_id': int(folder_id),
                        'partner_id': int(partner_id)
                    }
                    if owner_id:
                        vals['owner_id'] = int(owner_id)
                    vals_list.append(vals)
                except Exception as e:
                    logger.exception("Fail to upload document %s" % ufile.filename)
                    result = {'error': str(e)}
            request.env['documents.document'].create(vals_list)

        return json.dumps(result)

    @http.route(['/documents/content/<int:id>'], type='http', auth='user')
    def documents_content(self, id):
        return self._get_file_response(id)

    @http.route(['/documents/image/<int:id>',
                 '/documents/image/<int:id>/<int:width>x<int:height>',
                 ], type='http', auth="public")
    def content_image(self, id=None, field='datas', share_id=None, width=0, height=0, crop=False, share_token=None, **kwargs):
        status, headers, image_base64 = self.binary_content(
            id=id, field=field, share_id=share_id, share_token=share_token)
        if status != 200:
            return request.env['ir.http']._response_by_status(status, headers, image_base64)

        image_base64 = image_process(image_base64, size=(int(width), int(height)), crop=crop)

        if not image_base64:
            return request.not_found()

        content = base64.b64decode(image_base64)
        headers = http.set_safe_image_headers(headers, content)
        response = request.make_response(content, headers)
        response.status_code = status
        return response

    @http.route(['/document/zip'], type='http', auth='user')
    def get_zip(self, file_ids, zip_name, token=None):
        """route to get the zip file of the selection in the document's Kanban view (Document inspector).
        :param file_ids: if of the files to zip.
        :param zip_name: name of the zip file.
        """
        ids_list = [int(x) for x in file_ids.split(',')]
        env = request.env
        response = self._make_zip(zip_name, env['documents.document'].browse(ids_list))
        if token:
            response.set_cookie('fileToken', token)
        return response

    @http.route(["/document/download/all/<int:share_id>/<access_token>"], type='http', auth='public')
    def share_download_all(self, access_token=None, share_id=None):
        """
        :param share_id: id of the share, the name of the share will be the name of the zip file share.
        :param access_token: share access token
        :returns the http response for a zip file if the token and the ID are valid.
        """
        env = request.env
        try:
            share = env['documents.share'].sudo().browse(share_id)
            documents = share._get_documents_and_check_access(access_token, operation='read')
            if documents:
                return self._make_zip((share.name or 'unnamed-link') + '.zip', documents)
            else:
                return request.not_found()
        except Exception:
            logger.exception("Failed to zip share link id: %s" % share_id)
        return request.not_found()

    @http.route(["/document/avatar/<int:share_id>/<access_token>"], type='http', auth='public')
    def get_avatar(self, access_token=None, share_id=None):
        """
        :param share_id: id of the share.
        :param access_token: share access token
        :returns the picture of the share author for the front-end view.
        """
        try:
            env = request.env
            share = env['documents.share'].sudo().browse(share_id)
            if share._get_documents_and_check_access(access_token, document_ids=[], operation='read') is not False:
                image = env['res.users'].sudo().browse(share.create_uid.id).image_128

                if not image:
                    binary = Binary()
                    return binary.placeholder()

                return base64.b64decode(image)
            else:
                return request.not_found()
        except Exception:
            logger.exception("Failed to download portrait")
        return request.not_found()

    @http.route(["/document/thumbnail/<int:share_id>/<access_token>/<int:id>"],
                type='http', auth='public')
    def get_thumbnail(self, id=None, access_token=None, share_id=None):
        """
        :param id:  id of the document
        :param access_token: token of the share link
        :param share_id: id of the share link
        :return: the thumbnail of the document for the portal view.
        """
        try:
            thumbnail = self._get_file_response(id, share_id=share_id, share_token=access_token, field='thumbnail')
            return thumbnail
        except Exception:
            logger.exception("Failed to download thumbnail id: %s" % id)
        return request.not_found()

    # single file download route.
    @http.route(["/document/download/<int:share_id>/<access_token>/<int:id>"],
                type='http', auth='public')
    def download_one(self, id=None, access_token=None, share_id=None, **kwargs):
        """
        used to download a single file from the portal multi-file page.

        :param id: id of the file
        :param access_token:  token of the share link
        :param share_id: id of the share link
        :return: a portal page to preview and download a single file.
        """
        try:
            document = self._get_file_response(id, share_id=share_id, share_token=access_token, field='datas')
            return document or request.not_found()
        except Exception:
            logger.exception("Failed to download document %s" % id)

        return request.not_found()

    # Upload file(s) route.
    @http.route(["/document/upload/<int:share_id>/<token>/",
                 "/document/upload/<int:share_id>/<token>/<int:document_id>"],
                type='http', auth='public', methods=['POST'], csrf=False)
    def upload_attachment(self, share_id, token, document_id=None, **kwargs):
        """
        Allows public upload if provided with the right token and share_Link.

        :param share_id: id of the share.
        :param token: share access token.
        :param document_id: id of a document request to directly upload its content
        :return if files are uploaded, recalls the share portal with the updated content.
        """
        share = http.request.env['documents.share'].sudo().browse(share_id)
        if not share.can_upload or (not document_id and share.action != 'downloadupload'):
            return http.request.not_found()

        available_documents = share._get_documents_and_check_access(
            token, [document_id] if document_id else [], operation='write')
        folder = share.folder_id
        folder_id = folder.id or False
        button_text = share.name or _('Share link')
        chatter_message = _('''<b> File uploaded by: </b> %s <br/>
                               <b> Link created by: </b> %s <br/>
                               <a class="btn btn-primary" href="/web#id=%s&model=documents.share&view_type=form" target="_blank">
                                  <b>%s</b>
                               </a>
                             ''') % (
                http.request.env.user.name,
                share.create_uid.name,
                share_id,
                button_text,
            )
        if document_id and available_documents:
            if available_documents.type != 'empty':
                return http.request.not_found()
            try:
                file = request.httprequest.files.getlist('requestFile')[0]
                data = file.read()
                mimetype = self._neuter_mimetype(file.content_type, http.request.env.user)
                write_vals = {
                    'mimetype': mimetype,
                    'name': file.filename,
                    'type': 'binary',
                    'datas': base64.b64encode(data),
                }
            except Exception:
                logger.exception("Failed to read uploaded file")
            else:
                available_documents.with_context(binary_field_real_user=http.request.env.user).write(write_vals)
                available_documents.message_post(body=chatter_message)
        elif not document_id and available_documents is not False:
            try:
                for file in request.httprequest.files.getlist('files'):
                    data = file.read()
                    mimetype = self._neuter_mimetype(file.content_type, http.request.env.user)
                    document_dict = {
                        'mimetype': mimetype,
                        'name': file.filename,
                        'datas': base64.b64encode(data),
                        'tag_ids': [(6, 0, share.tag_ids.ids)],
                        'partner_id': share.partner_id.id,
                        'owner_id': share.owner_id.id,
                        'folder_id': folder_id,
                    }
                    document = request.env['documents.document'].with_user(share.create_uid).with_context(binary_field_real_user=http.request.env.user).create(document_dict)
                    document.message_post(body=chatter_message)
                    if share.activity_option:
                        document.documents_set_activity(settings_record=share)

            except Exception:
                logger.exception("Failed to upload document")
        else:
            return http.request.not_found()
        return """<script type='text/javascript'>
                    window.open("/document/share/%s/%s", "_self");
                </script>""" % (share_id, token)

    # Frontend portals #############################################################################

    # share portals route.
    @http.route(['/document/share/<int:share_id>/<token>'], type='http', auth='public')
    def share_portal(self, share_id=None, token=None):
        """
        Leads to a public portal displaying downloadable files for anyone with the token.

        :param share_id: id of the share link
        :param token: share access token
        """
        try:
            share = http.request.env['documents.share'].sudo().browse(share_id)
            available_documents = share._get_documents_and_check_access(token, operation='read')
            if available_documents is False:
                if share._check_token(token):
                    options = {
                        'expiration_date': share.date_deadline,
                        'author': share.create_uid.name,
                    }
                    return request.render('documents.not_available', options)
                else:
                    return request.not_found()

            options = {
                'base_url': http.request.env["ir.config_parameter"].sudo().get_param("web.base.url"),
                'token': str(token),
                'upload': share.action == 'downloadupload',
                'share_id': str(share.id),
                'author': share.create_uid.name,
            }
            if share.type == 'ids' and len(available_documents) == 1:
                options.update(document=available_documents[0], request_upload=True)
                return request.render('documents.share_single', options)
            else:
                options.update(all_button='binary' in [document.type for document in available_documents],
                               document_ids=available_documents,
                               request_upload=share.action == 'downloadupload' or share.type == 'ids')
                return request.render('documents.share_page', options)
        except Exception:
            logger.exception("Failed to generate the multi file share portal")
        return request.not_found()
