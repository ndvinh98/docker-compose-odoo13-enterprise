# -*- coding: utf-8 -*-
import requests
import json
import datetime
import logging
import uuid
import re

from odoo import models, api, fields, SUPERUSER_ID
from odoo.exceptions import AccessError, UserError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class YodleeProviderAccount(models.Model):
    _inherit = ['account.online.provider']

    provider_type = fields.Selection(selection_add=[('yodlee', 'Yodlee')])

    def _get_available_providers(self):
        ret = super(YodleeProviderAccount, self)._get_available_providers()
        ret.append('yodlee')
        return ret

    @api.model
    def _get_yodlee_credentials(self):
        ICP_obj = self.env['ir.config_parameter'].sudo()
        login = self._cr.dbname
        secret = ICP_obj.get_param('database.uuid')
        base_url = self.sudo().env['ir.config_parameter'].get_param('odoo.online_sync_proxy') or 'https://onlinesync.odoo.com'
        url = base_url + '/yodlee/api/2'
        fastlink_url = 'https://usyirestmasternode.yodleeinteractive.com/authenticate/odooinc/?channelAppName=usyirestmaster'
        return {'login': login, 'secret': secret, 'url': url, 'fastlink_url': fastlink_url}

    def register_new_user(self):
        company_id = self.env.company
        username = self.env.registry.db_name + '_' + str(uuid.uuid4())

        # Implement funky password policy from Yodlee's REST API
        password = str(uuid.uuid4()).upper().replace('-','#')
        while re.search(r'(.)\1\1', password):
            password = str(uuid.uuid4()).upper().replace('-','#')

        email = company_id.partner_id.email
        if not email:
            raise UserError(_('Please configure an email in the company settings.'))
        credentials = self._get_yodlee_credentials()
        self.do_cobrand_login()
        headerVal = {'Authorization': '{cobSession=' + company_id.yodlee_access_token + '}'}
        requestBody = json.dumps(
            {'user': {'loginName': username,
                      'password': password,
                      'email': email}}
        )
        try:
            resp = requests.post(url=credentials['url'] + '/user/register', data=requestBody, headers=headerVal, timeout=30)
        except requests.exceptions.Timeout:
            raise UserError(_('Timeout: the server did not reply within 30s'))
        self.check_yodlee_error(resp)
        company_id.yodlee_user_access_token = resp.json().get('user').get('session').get('userSession')
        company_id.yodlee_user_login = username
        company_id.yodlee_user_password = password

    def do_cobrand_login(self):
        credentials = self._get_yodlee_credentials()
        requestBody = json.dumps({'cobrand': {'cobrandLogin': credentials['login'], 'cobrandPassword': credentials['secret']}})
        try:
            resp = requests.post(url=credentials['url'] + '/cobrand/login', data=requestBody, timeout=30)
        except requests.exceptions.Timeout:
            raise UserError(_('Timeout: the server did not reply within 30s'))
        self.check_yodlee_error(resp)
        company_id = self.company_id or self.env.company
        company_id.yodlee_access_token = resp.json().get('session').get('cobSession')

    def do_user_login(self):
        credentials = self._get_yodlee_credentials()
        company_id = self.company_id or self.env.company
        headerVal = {'Authorization': '{cobSession=' + company_id.yodlee_access_token + '}'}
        requestBody = json.dumps({'user': {'loginName': company_id.yodlee_user_login, 'password': company_id.yodlee_user_password}})
        try:
            resp = requests.post(url=credentials['url'] + '/user/login', data=requestBody, headers=headerVal, timeout=30)
        except requests.exceptions.Timeout:
            raise UserError(_('Timeout: the server did not reply within 30s'))
        self.check_yodlee_error(resp)
        company_id.yodlee_user_access_token = resp.json().get('user').get('session').get('userSession')

    def get_auth_tokens(self):
        self.do_cobrand_login()
        self.do_user_login()

    def check_yodlee_error(self, resp):
        try:
            resp_json = resp.json()
            if resp_json.get('errorCode'):
                if resp.json().get('errorCode') in ('Y007', 'Y008', 'Y009', 'Y010'):
                    return 'invalid_auth'
                message = _('Error %s, message: %s, reference code: %s' % (resp_json.get('errorCode'), resp_json.get('errorMessage'), resp_json.get('referenceCode')))
                message = ("%s\n\n" + _('(Diagnostic: %r for URL %s)')) % (message, resp.status_code, resp.url)
                if self and self.id:
                    self._update_status('FAILED', resp_json)
                    self.log_message(message)
                raise UserError(message)
            resp.raise_for_status()
        except (requests.HTTPError, ValueError):
            message = ('%s\n\n' + _('(Diagnostic: %r for URL %s)')) % (resp.text.strip(), resp.status_code, resp.url)
            if self and self.id:
                self.log_message(message)
            raise UserError(message)

    def yodlee_fetch(self, url, params, data, type_request='POST'):
        credentials = self._get_yodlee_credentials()
        company_id = self.company_id or self.env.company
        service_url = url
        url = credentials['url'] + url
        if not company_id.yodlee_user_login:
            self.register_new_user()
        if not company_id.yodlee_access_token or not company_id.yodlee_user_access_token:
            self.get_auth_tokens()
        headerVal = {'Authorization': '{cobSession=%s, userSession=%s}' % (company_id.yodlee_access_token, company_id.yodlee_user_access_token)}
        try:
            if type_request == 'POST':
                resp = requests.post(url=url, params=params, data=data, headers=headerVal, timeout=60)
            elif type_request == 'GET':
                resp = requests.get(url=url, params=params, data=data, headers=headerVal, timeout=60)
            elif type_request == 'PUT':
                resp = requests.put(url=url, params=params, data=data, headers=headerVal, timeout=60)
            elif type_request == 'DELETE':
                resp = requests.delete(url=url, params=params, data=data, headers=headerVal, timeout=60)
        except requests.exceptions.Timeout:
            raise UserError(_('Timeout: the server did not reply within 30s'))
        except requests.exceptions.ConnectionError:
            raise UserError(_('Server not reachable, please try again later'))
        # Manage errors and get new token if needed
        if self.check_yodlee_error(resp) == 'invalid_auth':
            self.get_auth_tokens()
            return self.yodlee_fetch(service_url, params, data, type_request=type_request)
        return resp.json()

    def get_login_form(self, site_id, provider, beta=False):
        if provider != 'yodlee':
            return super(YodleeProviderAccount, self).get_login_form(site_id, provider, beta)
        return self.open_yodlee_action(site_id, 'add', beta)

    def update_credentials(self):
        if self.provider_type != 'yodlee':
            return super(YodleeProviderAccount, self).update_credentials()
        self.ensure_one()
        return self.open_yodlee_action(self.provider_account_identifier, 'edit')

    def manual_sync(self, return_action=True):
        if self.provider_type != 'yodlee':
            return super(YodleeProviderAccount, self).manual_sync()
        self.ensure_one()
        return self.open_yodlee_action(self.provider_account_identifier, 'refresh')

    def open_yodlee_action(self, identifier, state, beta=False):
        resp_json = self.yodlee_fetch('/user/accessTokens', {'appIds': '10003600'}, {}, 'GET')
        callbackUrl = '/sync_status/' + str(self.env.context.get('journal_id', 0)) + '/' + state
        paramsUrl = 'flow=%s&siteId=%s&callback=' if state == 'add' else 'flow=%s&siteAccountId=%s&callback='
        paramsUrl = paramsUrl % (state, identifier)
        return {
                'type': 'ir.actions.client',
                'tag': 'yodlee_online_sync_widget',
                'target': 'new',
                'fastlinkUrl': self._get_yodlee_credentials()['fastlink_url'],
                'paramsUrl': paramsUrl,
                'callbackUrl': callbackUrl,
                'userToken': self.env.company.yodlee_user_access_token,
                'beta': beta,
                'state': state,
                'accessTokens': resp_json.get('user').get('accessTokens')[0],
                'context': self.env.context,
                }

    def _getStatus(self, status):
        if status == 1:
            return 'ACTION_ABANDONED'
        if status == 2:
            return 'SUCCESS'
        if status == 3:
            return 'FAILED'
        else:
            return status

    def callback_institution(self, informations, state, journal_id):
        action = self.env.ref('account.open_account_journal_dashboard_kanban').id
        try:
            resp_json = json.loads(informations)
        except ValueError:
            raise UserError(_('Could not make sense of parameters: %s') % (informations,))
        element = type(resp_json) is list and len(resp_json) > 0 and resp_json[0] or {}
        if element.get('providerAccountId'):
            new_provider_account = self.search([('provider_account_identifier', '=', element.get('providerAccountId')),
                ('company_id', '=', self.env.company.id)], limit=1)
            if len(new_provider_account) == 0:
                vals = {
                    'name': element.get('bankName') or _('Online institution'),
                    'provider_account_identifier': element.get('providerAccountId'),
                    'provider_identifier': element.get('providerId'),
                    'status': self._getStatus(element.get('status')),
                    'status_code': element.get('code'),
                    'message': element.get('reason'),
                    'last_refresh': fields.Datetime.now(),
                    'action_required': False,
                    'provider_type': 'yodlee',
                }
                new_provider_account = self.create(vals)
                if element.get('status') == 'SUCCESS':
                    self.yodlee_fetch('/add_institution', {}, {'providerId': element.get('providerId')}, 'POST')
            else:
                new_provider_account.write({
                    'status': self._getStatus(element.get('status')),
                    'status_code': element.get('code'),
                    'message': element.get('reason'),
                    'last_refresh': fields.Datetime.now(),
                    'action_required': False if element.get('status') == 'SUCCESS' else True,
                })
                if self._getStatus(element.get('status')) == 'FAILED':
                    message = _('Error %s, message: %s') % (element.get('code'), element.get('reason'))
                    new_provider_account.log_message(message)
            # Fetch accounts
            res = new_provider_account.add_update_accounts()
            res.update({'status': self._getStatus(element.get('status')),
                'message': element.get('reason'),
                'method': state,
                'journal_id': journal_id})
            return self.show_result(res)
        else:
            return action

    def add_update_accounts(self):
        params = {'providerAccountId': self.provider_account_identifier}
        resp_json = self.yodlee_fetch('/accounts', params, {}, 'GET')
        accounts = resp_json.get('account', [])
        account_added = self.env['account.online.journal']
        transactions = []
        for account in accounts:
            if account.get('CONTAINER') in ('bank', 'creditCard'):
                vals = {
                    'yodlee_account_status': account.get('accountStatus'),
                    'yodlee_status_code': account.get('refreshinfo', {}).get('statusCode'),
                    'balance': account.get('currentBalance', account.get('balance', {})).get('amount', 0) if account.get('CONTAINER') == 'bank' else account.get('runningBalance', {}).get('amount', 0)
                }
                account_search = self.env['account.online.journal'].search([('account_online_provider_id', '=', self.id), ('online_identifier', '=', account.get('id'))], limit=1)
                if len(account_search) == 0:
                    # Since we just create account, set last sync to 15 days in the past to retrieve transaction from latest 15 days
                    last_sync = self.last_refresh - datetime.timedelta(days=15)
                    vals.update({
                        'name': account.get('accountName', _('Account')),
                        'online_identifier': account.get('id'),
                        'account_online_provider_id': self.id,
                        'account_number': account.get('accountNumber'),
                        'last_sync': last_sync,
                    })
                    account_added += self.env['account.online.journal'].create(vals)
                else:
                    account_search.env['account.online.journal'].write(vals)
                    # Also retrieve transaction if status is SUCCESS
                    if vals.get('yodlee_status_code') == 0 and account_search.journal_ids:
                        transactions_count = account_search.retrieve_transactions()
                        transactions.append({'journal': account_search.journal_ids[0].name, 'count': transactions_count})
        return {'added': account_added, 'transactions': transactions}

    def _update_status(self, status, info):
        self.write({
            'status': status,
            'status_code': info.get('errorCode', '-1'),
            'message': info.get('errorMessage', ''),
            'action_required': False if status == 'SUCCESS' else True
            })

    def get_provider_status(self):
        self.ensure_one()
        resp_json = self.yodlee_fetch('/providerAccounts/' + self.provider_account_identifier, {}, {}, 'GET')
        info = resp_json.get('providerAccount', {}).get('refreshInfo', {})
        if info:
            # Update status of record
            self.write({
                'status': info.get('status'),
                'status_code': info.get('statusCode'),
                'message': info.get('statusMessage'),
                'last_refresh': info.get('lastRefreshed', '').replace('T', ' ').replace('Z', ''),
                'action_required': False if info.get('status') == 'SUCCESS' else True,
                })
            if info.get('status') == 'FAILED':
                message = _('message: %s') % (self.get_error_from_code(info.get('statusCode')),)
                self.log_message(message)
        return True

    @api.model
    def cron_fetch_online_transactions(self):
        if self.provider_type != 'yodlee':
            return super(YodleeProviderAccount, self).cron_fetch_online_transactions()
        self.get_provider_status()
        for account in self.account_online_journal_ids:
            if account.journal_ids and self.status == 'SUCCESS':
                account.retrieve_transactions()

    def unlink(self):
        for provider in self:
            if provider.provider_type == 'yodlee':
                # call yodlee to ask to remove link between user and provider_account_identifier
                try:
                    ctx = self._context.copy()
                    ctx['no_post_message'] = True
                    provider.with_context(ctx).yodlee_fetch('/providerAccounts/' + provider.provider_account_identifier, {}, {}, 'DELETE')
                except UserError:
                    # If call to yodlee fails, don't prevent user to delete record
                    pass
        super(YodleeProviderAccount, self).unlink()

    def get_error_from_code(self, code):
        return {
            '409': _("Problem Updating Account(409): We could not update your account because the end site is experiencing technical difficulties."),
            '411': _("Site No Longer Available (411):The site no longer provides online services to its customers.  Please delete this account."),
            '412': _("Problem Updating Account(412): We could not update your account because the site is experiencing technical difficulties."),
            '415': _("Problem Updating Account(415): We could not update your account because the site is experiencing technical difficulties."),
            '416': _("Multiple User Logins(416): We attempted to update your account, but another session was already established at the same time.  If you are currently logged on to this account directly, please log off and try after some time"),
            '418': _("Problem Updating Account(418): We could not update your account because the site is experiencing technical difficulties. Please try later."),
            '423': _("No Account Found (423): We were unable to detect an account. Please verify that you account information is available at this time and If the problem persists, please contact customer support at online@odoo.com for further assistance."),
            '424': _("Site Down for Maintenance(424):We were unable to update your account as the site is temporarily down for maintenance. We apologize for the inconvenience.  This problem is typically resolved in a few hours. Please try later."),
            '425': _("Problem Updating Account(425): We could not update your account because the site is experiencing technical difficulties. Please try later."),
            '426': _("Problem Updating Account(426): We could not update your account for technical reasons. This type of error is usually resolved in a few days. We apologize for the inconvenience."),
            '505': _("Site Not Supported (505): We currently does not support the security system used by this site. We apologize for any inconvenience. Check back periodically if this situation has changed."),
            '510': _("Property Record Not Found (510): The site is unable to find any property information for your address. Please verify if the property address you have provided is correct."),
            '511': _("Home Value Not Found (511): The site is unable to provide home value for your property. We suggest you to delete this site."),
            '402': _("Credential Re-Verification Required (402): We could not update your account because your username and/or password were reported to be incorrect.  Please re-verify your username and password."),
            '405': _("Update Request Canceled(405):Your account was not updated because you canceled the request."),
            '406': _("Problem Updating Account (406): We could not update your account because the site requires you to perform some additional action. Please visit the site or contact its customer support to resolve this issue. Once done, please update your account credentials in case they are changed else try again."),
            '407': _("Account Locked (407): We could not update your account because it appears your account has been locked. This usually results from too many unsuccessful login attempts in a short period of time. Please visit the site or contact its customer support to resolve this issue.  Once done, please update your account credentials in case they are changed."),
            '414': _("Requested Account Type Not Found (414): We could not find your requested account. You may have selected a similar site under a different category by accident in which case you should select the correct site."),
            '417': _("Account Type Not Supported(417):The type of account we found is not currently supported.  Please remove this site and add as a  manual account."),
            '420': _("Credential Re-Verification Required (420):The site has merged with another. Please re-verify your credentials at the site and update the same."),
            '421': _("Invalid Language Setting (421): The language setting for your site account is not English. Please visit the site and change the language setting to English."),
            '422': _("Account Reported Closed (422): We were unable to update your account information because it appears one or more of your related accounts have been closed.  Please deactivate or delete the relevant account and try again."),
            '427': _("Re-verification Required (427): We could not update your account due to the site requiring you to view a new promotion. Please log in to the site and click through to your account overview page to update the account.  We apologize for the inconvenience."),
            '428': _("Re-verification Required (428): We could not update your account due to the site requiring you to accept a new Terms & Conditions. Please log in to the site and read and accept the T&C."),
            '429': _("Re-Verification Required (429): We could not update your account due to the site requiring you to verify your personal information. Please log in to the site and update the fields required."),
            '430': _("Site No Longer Supported (430):This site is no longer supported for data updates. Please deactivate or delete your account. We apologize for the inconvenience."),
            '433': _("Registration Requires Attention (433): Auto registration is not complete. Please complete your registration at the end site. Once completed, please complete adding this account."),
            '434': _("Registration Requires Attention (434): Your Auto-Registration could not be completed and requires further input from you.  Please re-verify your registration information to complete the process."),
            '435': _("Registration Requires Attention (435): Your Auto-Registration could not be completed and requires further input from you.  Please re-verify your registration information to complete the process."),
            '436': _("Account Already Registered (436):Your Auto-Registration could not be completed because the site reports that your account is already registered.  Please log in to the site to confirm and then complete the site addition process with the correct login information."),
            '506': _("New Login Information Required(506):We're sorry, to log in to this site, you need to provide additional information. Please update your account and try again."),
            '512': _("No Payees Found(512):Your request cannot be completed as no payees were found in your account."),
            '518': _("MFA error: Authentication Information Unavailable (518):Your account was not updated as the required additional authentication information was unavailable. Please try now."),
            '519': _("MFA error: Authentication Information Required (519): Your account was not updated as your authentication information like security question and answer was unavailable or incomplete. Please update your account settings."),
            '520': _("MFA error: Authentication Information Incorrect (520):We're sorry, the site indicates that the additional authentication information you provided is incorrect. Please try updating your account again."),
            '521': _("MFA error: Additional Authentication Enrollment Required (521) : Please enroll in the new security authentication system, <Account Name> has introduced. Ensure your account settings in <Cobrand> are updated with this information."),
            '522': _("MFA error: Request Timed Out (522) :Your request has timed out as the required security information was unavailable or was not provided within the expected time. Please try again."),
            '523': _("MFA error: Authentication Information Incorrect (523):We're sorry, the authentication information you  provided is incorrect. Please try again."),
            '524': _("MFA error: Authentication Information Expired (524):We're sorry, the authentication information you provided has expired. Please try again."),
            '526': _("MFA error: Credential Re-Verification Required (526): We could not update your account because your username/password or additional security credentials are incorrect. Please try again."),
            '401': _("Problem Updating Account(401):We're sorry, your request timed out. Please try again."),
            '403': _("Problem Updating Account(403):We're sorry, there was a technical problem updating your account. This kind of error is usually resolved in a few days. Please try again later."),
            '404': _("Problem Updating Account(404):We're sorry, there was a technical problem updating your account. Please try again later."),
            '408': _("Account Not Found(408): We're sorry, we couldn't find any accounts for you at the site. Please log in at the site and confirm that your account is set up, then try again."),
            '413': _("Problem Updating Account(413):We're sorry, we couldn't update your account at the site because of a technical issue. This type of problem is usually resolved in a few days. Please try again later."),
            '419': _("Problem Updating Account(419):We're sorry, we couldn't update your account because of unexpected variations at the site. This kind of problem is usually resolved in a few days. Please try again later."),
            '507': _("Problem Updating Account(507):We're sorry, Yodlee has just started providing data updates for this site, and it may take a few days to be successful as we get started. Please try again later."),
            '508': _("Request Timed Out (508): We are sorry, your request timed out due to technical reasons. Please try again."),
            '509': _("MFA error: Site Device Information Expired(509): We're sorry, we can't update your account because your token is no longer valid at the site. Please update your information and try again, or contact customer support."),
            '517': _("Problem Updating Account (517): We are sorry, there was a technical problem updating your account. Please try again."),
            '525': _("MFA error: Problem Updating Account (525): We could not update your account for technical reasons. This type of error is usually resolved in a few days. We apologize for the inconvenience. Please try again later."),
        }.get(str(code), _('An Error has occurred (code %s)' % code))


class ResCompany(models.Model):
    _inherit = 'res.company'

    yodlee_access_token = fields.Char("access_token")
    yodlee_user_login = fields.Char("Yodlee login")
    yodlee_user_password = fields.Char("Yodlee password")
    yodlee_user_access_token = fields.Char("Yodlee access token")


class YodleeAccount(models.Model):
    _inherit = 'account.online.journal'
    '''
    The yodlee account that is saved in Odoo.
    It knows how to fetch Yodlee to get the new bank statements
    '''

    yodlee_account_status = fields.Char(help='Active/Inactive on Yodlee system', readonly=True)
    yodlee_status_code = fields.Integer(readonly=True)

    def retrieve_transactions(self):
        if (self.account_online_provider_id.provider_type != 'yodlee'):
            return super(YodleeAccount, self).retrieve_transactions()
        if not self.journal_ids:
            return 0
        params = {
            'accountId': self.online_identifier,
            'fromDate': min(self.last_sync, self.account_online_provider_id.last_refresh.date()),
            'toDate': fields.Date.today(),
            'top': 500,
        }
        offset = 0
        transactions = []
        while True:
            if offset > 0:
                params['skip'] = offset
            resp_json = self.account_online_provider_id.yodlee_fetch('/transactions', params, {}, 'GET')
            for tr in resp_json.get('transaction', []):
                # We only take posted transaction into account
                if tr.get('status') == 'POSTED':
                    date = tr.get('date') or tr.get('postDate') or tr.get('transactionDate')
                    date = fields.Date.from_string(date)
                    amount = tr.get('amount', {}).get('amount')
                    # ignore transaction with 0
                    if amount == 0:
                        continue
                    vals = {
                        'online_identifier': str(tr.get('id')) + ':' + tr.get('CONTAINER'),
                        'date': date,
                        'name': tr.get('description',{}).get('original', 'No description'),
                        'amount': amount * -1 if tr.get('baseType') == 'DEBIT' else amount,
                        'end_amount': self.balance,
                    }
                    if tr.get('accountId'):
                        vals['partner_id'] = self._find_partner([('online_partner_bank_account', '=', tr.get('accountId'))])
                        vals['online_partner_bank_account'] = tr.get('accountId')
                    if tr.get('merchant') and tr.get('merchant', {}).get('id', False) and vals['amount'] < 0:
                        vals['online_partner_vendor_name'] = tr['merchant']['id']
                        if not vals.get('partner_id'):
                            vals['partner_id'] = self._find_partner([('online_partner_vendor_name', '=', tr['merchant']['id'])])

                    transactions.append(vals)
            if len(resp_json.get('transaction', [])) < 500:
                break
            else:
                offset += 500
        return self.env['account.bank.statement'].online_sync_bank_statement(transactions, self.journal_ids[0])
