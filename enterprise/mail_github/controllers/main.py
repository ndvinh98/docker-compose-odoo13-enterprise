# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import logging

from werkzeug import urls

from odoo import _
from odoo import http
from odoo.tools.misc import _consteq
from odoo.http import request

from odoo.addons.mail_github.models.mail_channel_github import github_tokenize

_logger = logging.getLogger(__name__)


MAP_GITHUB_EVENT_ACTION = {
    'created': 'create',
    'deleted': 'delete',
    'edited': 'update',
    'opened': 'create',
    'assigned': 'update',
    'unassigned': 'update',
    'closed': 'delete',
    'milestoned': 'update',
    'demilestoned': 'update',
    'labeled': 'update',
    'unlabeled': 'update',
    'reopened': 'create',
}


class GithubController(http.Controller):
    """ Get the payload from the Github webhook. The following method parse request, and process it according
        to its 'event_type'. All event_type are not supported (implemented). We only cover 'push' (default),
        'commit_comment', 'issue', 'issue_comment', 'pull_request', 'pull_request_review', 'pull_request_review',
        and 'gollum' (because the name is fun).

        Documentation :
            - https://developer.github.com/webhooks/
            - https://developer.github.com/v3/activity/events/types/
    """

    @http.route('/mail_github/payload/<token>', methods=['POST'], type='http', auth='public', csrf=False)
    def payload(self, payload, token):
        """ Webhook from Github: this is the server endpoint that will receive the webhook payload. """
        db_secret = request.env['ir.config_parameter'].sudo().get_param('database.secret')
        db_uuid = request.env['ir.config_parameter'].sudo().get_param('database.uuid')

        computed_token = github_tokenize(db_secret, db_uuid)
        if not _consteq(str(token), str(computed_token)):
            return request.not_found()

        headers = request.httprequest.headers
        headers_data = {
            'event_type': headers.get('X-GitHub-Event'),
            'signature': headers.get('X-Hub-Signature'),
            'delivery_id': headers.get('X-GitHub-Delivery')
        }
        payload_data = json.loads(payload)

        formated_payload = self._parse_github_payload(headers_data, payload_data)
        # Do nothing if the initial payload is not implemented
        if not formated_payload.get('payload'):
            return 'NO'

        # Do nothing when testing Webhook with a simple ping
        if headers_data.get('event_type') == 'ping':
            return 'TEST OK'

        # Get target repository
        repository_name = formated_payload['repository']['full_name']
        repository_github_id = formated_payload['repository']['github_id']
        repository_target = request.env['mail.channel.github'].sudo().search(['|', ("name", "=", repository_name), ('github_repository_id', '=', repository_github_id)])

        # Check the signature of the incoming callback
        # Github apparently computes the body as URL-Escaped string (sweet !!)
        raw_body = "payload=" + urls.url_quote_plus(request.httprequest.form['payload'].encode("UTF-8"))
        if headers_data.get('signature'):
            repo_sign = "sha1=" + github_tokenize(repository_target.secret, raw_body)
            if not _consteq(repo_sign, str(headers_data.get('signature'))):
                _logger.info("Gihbub webhook callback recieved request with invalid signature. (GH delivery_id = %s)", headers_data.get('delivery_id'))
                return False

        # Create or update target repository
        if not repository_target:
            repository_target = request.env['mail.channel.github'].sudo().create({
                'name': repository_name,
                'github_repository_id': repository_github_id,
            })
        if not repository_target.github_repository_id:
            repository_target.write({'github_repository_id': repository_github_id})

        # Search the partner author, corresponding to the gihhub login of the payload sender
        partner = request.env['res.users'].sudo().search([("github_login", "=", formated_payload['sender']['login'])], limit=1).partner_id
        partner_email = partner.email
        if not partner:
            partner = request.env.ref('mail_github.res_partner_githbub_bot')
            partner_email = formated_payload['sender']['login'] + '@github.com'

        # If no channel on target repo, then do nothing
        channel_ids = repository_target.channel_ids.filtered(lambda channel: channel.github_enabled)
        if not channel_ids:
            _logger.warning('No channel is listening the github repository %s', repository_name)
            return 'NO'

        # Post the message with the template
        template_values = dict(formated_payload)
        template_values['repository_id'] = repository_target
        template_values['partner_id'] = partner
        rendered_template = request.env.ref('mail_github.message_github_notification').render(template_values)

        channels = repository_target.channel_ids.filtered(lambda channel: channel.github_enabled)
        repository_target.message_post(
            body=rendered_template,
            subtype="mail.mt_comment",  # correct?
            author_id=partner.id,
            email_from=partner_email,
            channel_ids=channels.ids
        )

        return 'OK'

    def _parse_github_payload(self, headers_data, payload_data):
        payload = {
            'event_type': headers_data.get('event_type', '_unknown_event'),
            'repository': self._parse_github_repository(payload_data),
            'sender': self._parse_github_sender(payload_data),
        }
        try:
            payload['payload'] = self._parse_github_payload_event(headers_data, payload_data)
        except Exception as err:
            _logger.warning('Error when parsing Github payload for event %s : %s', headers_data.get('event_type', '_unknown_event'), str(err))
            payload['payload'] = False
        return payload

    def _parse_github_repository(self, payload_data):
        repository_data = payload_data['repository']
        return {
            'github_id': repository_data['id'],
            'name': repository_data['name'],
            'full_name': repository_data['full_name'],
            'private': repository_data['private'],
            'url': repository_data['html_url'],
            'owner': repository_data['owner'].get('name') or repository_data['owner'].get('login'),
        }

    def _parse_github_sender(self, payload_data):
        sender_data = payload_data['sender']
        return {
            'login': sender_data['login'],
            'avatar_url': sender_data['avatar_url'],
            'url': sender_data['html_url'],
            'github_id': sender_data['id'],
        }

    def _parse_github_payload_event(self, headers_data, payload_data):
        """ Format the event payload into a dict understandable by the template, to execute the message_post
            The dict keys are:
                - 'action': (required) performed action. Either 'create', 'delete', 'update', 'comment', or 'edit_wiki'.
                - 'object_type': Type of the object the action was performed. Either 'commit', 'pull_request' or 'issue'
                - 'object': the values of the object type
                - 'message': an additionnal string explaining the payload (Generally the body of the comment).
            Some event are particular and have their own format, such as 'gollum' and 'push'.
        """
        event_type = headers_data.get('event_type')
        if event_type == 'commit_comment':
            comment = payload_data['comment']
            return {
                'action': 'comment',
                'object_type': 'commit',
                'object_label': _('commit'),
                'object': {
                    'commit_hash': comment.get('commit_id'),
                    'url': comment['html_url'],
                },
                'message': payload_data['comment'].get('body'),
            }
        if event_type == 'gollum':
            pages = []
            for page in payload_data['pages']:
                pages.append({
                    'title': page['title'],
                    'name': page['page_name'],
                    'url': page['html_url'],
                })
            return {
                'action': 'edit_wiki',
                'pages': pages
            }
        if event_type == 'issue_comment':
            return {
                'action': 'comment',
                'object_type': 'issue',
                'object_label': _('issue'),
                'object': self._parse_github_payload_event_issue(payload_data['issue']),
                'message': payload_data['comment'].get('body'),
            }
        if event_type == 'issues':
            return {
                'action': MAP_GITHUB_EVENT_ACTION.get(payload_data['action'], payload_data['action']),
                'object_type': 'issue',
                'object_label': _('issue'),
                'object': self._parse_github_payload_event_issue(payload_data['issue']),
            }
        if event_type == 'pull_request':
            return {
                'action': MAP_GITHUB_EVENT_ACTION.get(payload_data['action'], payload_data['action']),
                'object_type': 'pull_request',
                'object_label': _('pull request'),
                'object': self._parse_github_payload_event_pull_request(payload_data['pull_request']),
            }
        if event_type in ['pull_request_review', 'pull_request_review_comment']:
            return {
                'action': 'comment',
                'object_type': 'pull_request',
                'object_label': _('pull request'),
                'object': self._parse_github_payload_event_pull_request(payload_data['pull_request']),
                'message': payload_data['pull_request'].get('body')
            }
        if event_type == 'push':  # default github event
            commits = []
            for commit in payload_data['commits']:
                commits.append({
                    'id': commit['id'],
                    'url': commit['url'],
                    'author': commit['author'].get('username', commit['author']['name']),
                    'author_email': commit['author']['email'],
                    'committer': commit['committer'].get('username', commit['committer']['name']),
                    'committer_email': commit['committer']['email'],
                    'message': commit['message'].split('\n')[0], # only the first line of the commit message
                    'message_long': commit['message'],
                })
            return {
                'action': 'push',
                'commits': commits,
                'ref': payload_data['ref'],
            }

        # All events are not supported : create, delete, deployment, deployment_status, follow,
        # fork_apply, gist, label, member, milestone, organization, page_build, public, ...
        # are not implemented.
        # returning False as payload will not execute 'message_post'.
        return False

    def _parse_github_payload_event_issue(self, issue):
        return {
            'id': issue['id'],
            'url': issue['html_url'],
            'name': issue['title'],
            'body': issue['body'],
            'create_date': issue['created_at'],
            'number': issue['number'],
            'state': issue['state'],
        }

    def _parse_github_payload_event_pull_request(self, pull_request):
        return {
            'id': pull_request['id'],
            'url': pull_request['html_url'],
            'name': pull_request['title'],
            'body': pull_request['body'],
            'create_date': pull_request['created_at'],
            'number': pull_request['number'],
        }
