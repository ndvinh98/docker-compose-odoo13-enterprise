# -*- coding: utf-8 -*-
import base64
import requests
import json
import logging
import datetime
import time
import dateutil.parser

from odoo import models, api, fields
from odoo.tools.translate import _
from odoo.exceptions import UserError
from odoo.addons.base.models.res_bank import sanitize_account_number
from pytz import timezone

GMT_BELGIUM = timezone('Europe/Brussels')

_logger = logging.getLogger(__name__)

class ProviderAccount(models.Model):
    _inherit = ['account.online.provider']

    provider_type = fields.Selection(selection_add=[('ponto', 'Ponto')])
    ponto_token = fields.Char(readonly=True, help='Technical field that contains the ponto token')

    def _get_available_providers(self):
        ret = super(ProviderAccount, self)._get_available_providers()
        ret.append('ponto')
        return ret

    def _build_ponto_headers(self):
        try:
            credentials = json.loads(self.ponto_token)
            if credentials.get('access_token'):
                access_token = credentials.get('access_token')
            else:
                self._generate_access_token()
                return self._build_ponto_headers()
            authorization = "Bearer " + access_token
            return {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": authorization
            }
        except ValueError:
            self.log_ponto_message(_('Access to ponto using token is being deprecated. Please follow migration process on https://docs.google.com/document/d/1apzAtCgZl5mfEz5-Z8iETqd6WXGbV0R2KuAvEL87rBI'))

    def _ponto_fetch(self, method, url, params, data):
        base_url = 'https://api.myponto.com'
        parsed_data = ""
        if not url.startswith(base_url):
            url = base_url + url
        try:
            if self._context.get('get_token'):
                headers = {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                    "Authorization": "Basic " + data.pop('encoded_credentials'),
                }
            else:
                headers = self._build_ponto_headers()

            if data:
                parsed_data = json.dumps(data)

            resp = requests.request(method=method, url=url, params=params, data=parsed_data, headers=headers, timeout=60)
            resp_json = resp.json()
            if resp_json.get('errors') or resp.status_code >= 400:
                if resp_json.get('errors', [{}])[0].get('code', '') == 'credentialsInvalid':
                    self._generate_access_token()
                    return self._ponto_fetch(method, url, params, data)
                # If the error is because we recently synchronized the resource, just return the error as it
                # will be handled in the _ponto_synchronize method
                if resp_json.get('errors', [{}])[0].get('code', '') == 'accountRecentlySynchronized':
                   return resp_json
                message = ('%s for route %s') % (json.dumps(resp_json.get('errors')), url)
                if resp_json.get('errors', [{}])[0].get('code', '') in ('authorizationCodeInvalid', 'clientIdInvalid'):
                    message = _('Invalid access keys')
                self.log_ponto_message(message)
            return resp_json
        except requests.exceptions.Timeout as e:
            _logger.exception(e)
            raise UserError(_('Timeout: the server did not reply within 60s'))
        except requests.exceptions.ConnectionError as e:
            _logger.exception(e)
            raise UserError(_('Server not reachable, please try again later'))
        except ValueError as e:
            _logger.exception(e)
            self.log_ponto_message('%s for route %s' % (resp.text, url))

    def _generate_access_token(self):
        credentials = json.loads(self.ponto_token)
        if credentials.get('encoded_credentials'):
            params = {'grant_type':'client_credentials'}
            url = "/oauth2/token"
            resp_json = self.with_context(get_token=True)._ponto_fetch(method='POST', url=url, params=params, data={'encoded_credentials': credentials.get('encoded_credentials')})
            if resp_json.get('access_token'):
                credentials.update({'access_token': resp_json.get('access_token')})
                self.ponto_token = json.dumps(credentials)
        else:
            self.log_ponto_message('Credentials missing! Please, be sure to set your client id and secret id.')

    def get_login_form(self, site_id, provider, beta=False):
        if provider != 'ponto':
            return super(ProviderAccount, self).get_login_form(site_id, provider, beta)
        return {
            'type': 'ir.actions.client',
            'tag': 'ponto_online_sync_widget',
            'name': _('Link your Ponto account'),
            'target': 'new',
            'context': self._context,
        }

    def log_ponto_message(self, message):
        # We need a context check because upon first synchronization the account_online_provider record is created and just after
        # we call api to get accounts but this call can result on an error (token not correct or else) and the transaction
        # would be rollbacked causing an error if we try to post a message on the deleted record with a new cursor. Solution
        # is to not try to log message in that case.
        if not self._context.get('no_post_message'):
            subject = _("An error occurred during online synchronization")
            message = _('The following error happened during the synchronization: %s' % (message,))
            # We have to call rollback manually here because if we don't do so we risk a deadlock in some case
            # Deadlock could appear in the following case: call to _ponto_fetch that will result in an error
            # because access token has expired, in that case we generate a new access token (which will write the
            # new access token to the record) and then we call back the original route again to retry. This new
            # call can result in en error which we have to log to the record as well as raise it for the user to see
            # (we log it to the record because it can happen in a cron as well).
            # Therefore we have a conflict as we already wrote some value on the record for the new access token and 
            # we try to write on the same record within a new cursor to say that its status should be changed to FAILED
            # hence a deadlock. Solution is to rollback the transaction just before writing the FAILED status to the 
            # record as it would be rollbacked anyway due to the raise UserError at the end.
            self.env.cr.rollback()
            with self.pool.cursor() as cr:
                self.with_env(self.env(cr=cr)).message_post(body=message, subject=subject)
                self.with_env(self.env(cr=cr)).write({'status': 'FAILED', 'action_required': True})
        raise UserError('An error has occurred: %s' % (message,))


    def _update_ponto_accounts(self, method='add'):
        resp_json = self._ponto_fetch('GET', '/accounts', {}, {})
        res = {'added': self.env['account.online.journal']}
        # When we are trying to add a new institution, add all existing account_online_journal that are not currently linked
        # The reason is that a user can first synchronize for journal A and receive 3 bank accounts, he only link one bank account
        # and does nothing with the 2 others, then later he create a new journal and synchronize again with the same ponto token
        # because he would like to link one of the two remaining account to his journal. Since the accounts were already fetched in
        # Odoo, we have to show it to him so that he can link them.
        if method == 'add':
            res['added'] = self.account_online_journal_ids.filtered(lambda j: len(j.journal_ids) == 0)
        for account in resp_json.get('data', {}):
            # Fetch accounts
            vals = {
                'balance': account.get('attributes', {}).get('currentBalance', 0)
            }
            account_search = self.env['account.online.journal'].search([('account_online_provider_id', '=', self.id), ('online_identifier', '=', account.get('id'))], limit=1)
            if len(account_search) == 0:
                # Since we just create account, set last sync to 15 days in the past to retrieve transaction from latest 15 days
                last_sync = self.last_refresh - datetime.timedelta(days=15)
                vals.update({
                    'name': account.get('attributes', {}).get('description', False) or _('Account'),
                    'online_identifier': account.get('id'),
                    'account_online_provider_id': self.id,
                    'account_number': account.get('attributes', {}).get('reference', {}),
                    'last_sync': last_sync,
                })
                acc = self.env['account.online.journal'].create(vals)
                res['added'] += acc
        self.write({'status': 'SUCCESS', 'action_required': False})
        res.update({'status': 'SUCCESS',
            'message': '',
            'method': method,
            'number_added': len(res['added']),
            'journal_id': self.env.context.get('journal_id', False)})
        return self.show_result(res)

    def success_callback(self, token):
        # Create account.provider and fetch account
        encoded_token = str(base64.b64encode(bytes(token, 'utf-8')), 'utf-8')
        ponto_token = '{"encoded_credentials": "%s"}' % encoded_token
        method = self._context.get('method', 'add')

        if self.id:
            self.write({'ponto_token': ponto_token})
            provider_account = self
        else:
            # Search for already existing ponto provider and if found update that one, otherwise create a new one
            provider_accounts = self.search([('provider_identifier', '=', 'ponto')])
            provider_account = False
            for provider in provider_accounts:
                try:
                    credentials = json.loads(provider.ponto_token)
                    if credentials.get('encoded_credentials') == encoded_token:
                        provider_account = provider
                        break
                except ValueError as e:
                    # ignore error as it is possible that it is due to an old encoding of ponto_token
                    continue
            if not provider_account:
                vals = {
                    'name': _('Ponto'),
                    'ponto_token': ponto_token,
                    'provider_identifier': 'ponto',
                    'status': 'SUCCESS',
                    'status_code': 0,
                    'message': '',
                    'last_refresh': fields.Datetime.now(),
                    'action_required': False,
                    'provider_type': 'ponto',
                }
                provider_account = self.create(vals)
        return provider_account.with_context(no_post_message=True)._update_ponto_accounts(method)

    def manual_sync(self):
        if self.provider_type != 'ponto':
            return super(ProviderAccount, self).manual_sync()
        transactions = []
        for account in self.account_online_journal_ids:
            if account.journal_ids:
                tr = account.retrieve_transactions()
                transactions.append({'journal': account.journal_ids[0].name, 'count': tr})
        self.write({'status': 'SUCCESS', 'action_required': False, 'last_refresh': fields.Datetime.now()})
        result = {'status': 'SUCCESS', 'transactions': transactions, 'method': 'refresh', 'added': self.env['account.online.journal']}
        return self.show_result(result)

    def update_credentials(self):
        if self.provider_type != 'ponto':
            return super(ProviderAccount, self).update_credentials()
        # Fetch new accounts if needed
        action = self.with_context(method='edit').get_login_form(self.provider_identifier, 'ponto')
        action.update({'record_id': self.id})
        return action

    @api.model
    def cron_fetch_online_transactions(self):
        if self.provider_type != 'ponto':
            return super(ProviderAccount, self).cron_fetch_online_transactions()
        self.manual_sync()


class OnlineAccount(models.Model):
    _inherit = 'account.online.journal'

    ponto_last_synchronization_identifier = fields.Char(readonly=True, help='id of ponto synchronization')

    def _ponto_synchronize(self, subtype):
        data = {
            'data': {
                'type': 'synchronization',
                'attributes': {
                    'resourceType': 'account',
                    'resourceId': self.online_identifier,
                    'subtype': subtype
                }
            }
        }
        # Synchronization ressource for account
        resp_json = self.account_online_provider_id._ponto_fetch('POST', '/synchronizations', {}, data)
        if resp_json.get('errors', [{}])[0].get('code', '') == 'accountRecentlySynchronized':
            _logger.info('Skip refresh of ponto %s as last refresh was too recent' % (subtype,))
            return
        # Get id of synchronization ressources
        sync_id = resp_json.get('data', {}).get('id')
        sync_ressource = resp_json.get('data', {}).get('attributes', {})
        # Fetch synchronization ressources until it has been updated
        count = 0
        while True:
            if count == 180:
                raise UserError(_('Fetching transactions took too much time.'))
            if sync_ressource.get('status') not in ('success', 'error'):
                resp_json = self.account_online_provider_id._ponto_fetch('GET', '/synchronizations/' + sync_id, {}, {})
            sync_ressource = resp_json.get('data', {}).get('attributes', {})
            if sync_ressource.get('status') in ('success', 'error'):
                # If we are in error, log the error and stop
                if sync_ressource.get('status') == 'error':
                    self.account_online_provider_id.log_ponto_message(json.dumps(sync_ressource.get('errors')))
                break
            count += 1
            time.sleep(2)
        return

    def retrieve_transactions(self):
        if (self.account_online_provider_id.provider_type != 'ponto'):
            return super(OnlineAccount, self).retrieve_transactions()
        # actualize the data in ponto
        # For some reason, ponto has 2 different routes to update the account balance and transactions
        # however if we try to refresh both one after another or at the same time, an error is received
        # An error is also received if we call their synchronization route too quickly. Therefore we
        # only refresh the transactions of the account and don't update the account which means that the
        # balance of the account won't be up-to-date. However this is not a big problem as the record that
        # store the balance is hidden for most user.
        self._ponto_synchronize('accountTransactions')
        self._ponto_synchronize('accountDetails')
        transactions = []
        # Update account balance
        url = '/accounts/%s' % (self.online_identifier,)
        resp_json = self.account_online_provider_id._ponto_fetch('GET', url, {}, {})
        end_amount = resp_json.get('data', {}).get('attributes', {}).get('currentBalance', 0)
        self.balance = end_amount
        # Fetch transactions.
        # Transactions are paginated so we need to loop to ensure we have every transactions, we keep
        # in memory the id of the last transaction fetched in order to start over from there.
        url = url + '/transactions'
        paging_forward = True
        if self.ponto_last_synchronization_identifier:
            paging_forward = False
            url = url + '?before=' + self.ponto_last_synchronization_identifier
        last_sync = fields.Date.to_date((self.last_sync or fields.Datetime.now() - datetime.timedelta(days=15)))
        latest_transaction_identifier = False
        while url:
            resp_json = self.account_online_provider_id._ponto_fetch('GET', url, {}, {})
            # 'prev' page contains newer transactions, 'next' page contains older ones.
            # we read from last known transaction to newer ones when we know such a transaction
            # else we read from the newest transaction back to our date limit
            url = resp_json.get('links', {}).get('next' if paging_forward else 'prev', False)
            data_lines = resp_json.get('data', [])
            if data_lines:
                # latest transaction will be in the last page in backward direction, or in the first one in forward direction
                if ((not paging_forward and not url) or (paging_forward and not latest_transaction_identifier)):
                    # a chunk sent by Ponto always has its most recent transaction first
                    latest_transaction_identifier = data_lines[0].get('id')
            for transaction in data_lines:
                # Convert received transaction datetime into Brussel timezone as we receive transaction date in an UTC
                # format but we store a date (which will loose information about the time) and some banks don't provide
                # the time of the transactions hence what we receive is a datetime in the form 2019-01-01T23:00:00.000z for a
                # transaction where the correct date should be of 2019-01-02
                # This is not the best fix as we should instead convert to the time of the country where the bank is located
                # but since ponto only support bank in belgium/france/nl for now this is acceptable.
                tr_date = dateutil.parser.parse(transaction.get('attributes', {}).get('executionDate'))
                tr_date = tr_date.astimezone(GMT_BELGIUM)
                tr_date = fields.Date.to_date(tr_date)
                if paging_forward and tr_date < last_sync:
                    # Stop fetching transactions because we are paging forward
                    # and the following transactions are older than specified last_sync date.
                    url = False
                    break
                attributes = transaction.get('attributes', {})
                description = attributes.get('description') or ''
                counterpart = attributes.get('counterpartName') or ''
                remittanceinfo = attributes.get('remittanceInformation') or ''
                remittanceinfoType = attributes.get('remittanceInformationType') or ''
                name = ''
                if remittanceinfoType == 'structured':
                    name = remittanceinfo
                if not name:
                    name = ' '.join([description, counterpart, remittanceinfo]) or '/'
                account_number = transaction.get('attributes', {}).get('counterpartReference')
                trans = {
                    'online_identifier': transaction.get('id'),
                    'date': tr_date,
                    'name': name,
                    'amount': transaction.get('attributes', {}).get('amount'),
                    'account_number': account_number,
                    'end_amount': end_amount
                }
                if account_number:
                    partner_bank = self.env['res.partner.bank'].search([('sanitized_acc_number', '=', sanitize_account_number(account_number))], limit=1)
                    if partner_bank:
                        trans['bank_account_id'] = partner_bank.id
                        trans['partner_id'] = partner_bank.partner_id.id
                if not trans.get('partner_id') and transaction.get('attributes', {}).get('counterpartName'):
                    trans['online_partner_vendor_name'] = transaction['attributes']['counterpartName']
                    trans['partner_id'] = self._find_partner([('online_partner_vendor_name', '=', transaction['attributes']['counterpartName'])])
                transactions.append(trans)
        if latest_transaction_identifier:
            self.ponto_last_synchronization_identifier = latest_transaction_identifier
        # Create the bank statement with the transactions
        return self.env['account.bank.statement'].online_sync_bank_statement(transactions, self.journal_ids[0])


class OnlineAccountWizard(models.TransientModel):
    _inherit = 'account.online.wizard'

    def _get_journal_values(self, account, create=False):
        vals = super(OnlineAccountWizard, self)._get_journal_values(account=account, create=create)
        if account.online_account_id.account_online_provider_id.provider_type == 'ponto':
            vals['post_at'] = 'bank_rec'
            vals['name'] = account.account_number
            # create bank account in Odoo if not already exists
            company = account.journal_id and account.journal_id.company_id or self.env.company
            res_bank_id = self.env['res.partner.bank'].search([('acc_number', '=', account.account_number), ('company_id', '=', company.id)])
            if not len(res_bank_id):
                res_bank_id = self.env['res.partner.bank'].create({
                    'acc_number': account.account_number,
                    'company_id': company.id,
                    'currency_id': company.currency_id.id,
                    'partner_id': company.partner_id.id,
                })
            vals['bank_account_id'] = res_bank_id.id
        return vals
