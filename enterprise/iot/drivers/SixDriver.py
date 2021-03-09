# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import ctypes
import logging
import time

try:
    from queue import Queue, Empty
except ImportError:
    from Queue import Queue, Empty  # pylint: disable=deprecated-module

from odoo import _
from odoo.addons.hw_drivers.controllers.driver import Driver, event_manager, mpdm

eftapi = ctypes.CDLL("eftapi.so")
EFT_BUSY_ERROR = 801

_logger = logging.getLogger(__name__)


class SixDriver(Driver):
    connection_type = 'mpd'

    def __init__(self, device):
        super(SixDriver, self).__init__(device)
        self._device_type = 'payment'
        self._device_connection = 'network'
        self._device_name = "Six Payment Terminal %s" % self.device_identifier
        self._device_manufacturer = 'Six'
        self.actions = Queue()
        self.last_transaction = {}
        self.cid = None
        self.processing = False

    @classmethod
    def supported(cls, device):
        return True  # All devices with connection_type == 'mpd' are supported

    @property
    def device_identifier(self):
        return self.dev

    def action(self, data):
        try:
            if data['messageType'] == 'Transaction':
                self.open_shift(data['language'].encode())
                self.actions.put({
                    'type': b'debit',
                    'amount': data['amount'],
                    'currency': data['currency'].encode(),
                    'id': data['cid'],
                    'owner': self.data['owner'],
                })
            elif data['messageType'] == 'Reversal' and self.check_reversal(data['cid']):
                self.actions.put({
                    'type': b'reversal',
                    'amount': data['amount'],
                    'currency': data['currency'].encode(),
                    'id': data['cid'],
                    'owner': self.data['owner'],
                })
            elif data['messageType'] == 'OpenShift':
                self.open_shift(data['language'].encode())
            elif data['messageType'] == 'CloseShift':
                self.close_shift()
            elif data['messageType'] == 'Balance':
                self.actions.put({
                    'type': 'balance',
                })
            elif data['messageType'] == 'Cancel':
                self.call_eftapi('EFT_Abort')
            elif data['messageType'] == 'QueryStatus':
                # Resends the last status if case one update got lost
                event_manager.device_changed(self)
        except:
            pass

    def open_shift(self, language):
        """Opens the shift and configures the language and receipt options"""

        self.call_eftapi('EFT_PutPrinterWidth', 45)
        self.call_eftapi('EFT_PutReceiptOptions', 1089)
        self.call_eftapi('EFT_PutLanguage', language)
        self.call_eftapi('EFT_Open')

    def close_shift(self):
        """Closes the shift"""

        self.last_transaction = {}
        self.call_eftapi('EFT_Close')

    def balance(self):
        """Sends a "Balance" operation then triggers an update with a the ticket
        for the merchant
        """

        self.call_eftapi('EFT_Balance')
        self.send_status(ticket_merchant=self.get_merchant_receipt())

    def check_reversal(self, id):
        """Checks if the transaction with the specified transaction ID can be
        reversed
        """

        self.call_eftapi('EFT_QueryStatus')
        self.call_eftapi('EFT_Complete', 1)  # Needed to read messages from driver
        reader_status = ctypes.c_long()
        self.call_eftapi('EFT_GetDeviceEventCode', ctypes.byref(reader_status))
        if reader_status.value != 0:
            self.send_status(error=_("A card is still inserted in the Payment Terminal, please remove it then try again."), cid=id)
        elif self.last_transaction.get('owner') != self.data['owner'] or self.last_transaction.get('id') != id:
            self.send_status(error=_("You cannot reverse this payment anymore."), cid=id)
        else:
            return True
        return False

    def run(self):
        """Transactions need to be processed in a different thread to be aborted.
        """

        while True:
            try:
                action = self.actions.get()
                if action['type'] == 'balance':
                    self.close_shift()  # Shift must be closed
                    self.balance()
                else:
                    self.process_transaction(action)
                time.sleep(2)  # If the delay between transactions is too small, the second one will fail
            except Exception:
                pass

    def process_transaction(self, transaction):
        """Processes a transaction on the terminal and triggers the required
        updates for the interface to work.

        :param transaction: The transaction to be executed
        :type transaction: dict
        """

        try:
            '''Since the status is queried regularly, we don't want to re-send
            an update for the previous transaction'''
            self.data = {
                'value': False,
            }

            self.processing = True
            self.cid = transaction['id']

            self.call_eftapi('EFT_PutCurrency', transaction['currency'])

            if transaction['type'] == b'debit':
                self.send_status(stage='WaitingForCard', owner=transaction['owner'], cid=transaction['id'])

            self.call_eftapi('EFT_Transaction', transaction['type'], transaction['amount'], 0)
            self.call_eftapi('EFT_Commit', 1)

            applicationName = ctypes.create_string_buffer(64)
            self.call_eftapi('EFT_GetApplicationName', ctypes.byref(applicationName), ctypes.sizeof(applicationName))
            refNumber = ctypes.create_string_buffer(11)
            self.call_eftapi('EFT_GetRefNumber', ctypes.byref(refNumber), ctypes.sizeof(refNumber))

            self.last_transaction = transaction
            self.processing = False
            
            self.send_status(
                response="Approved" if transaction['type'] == b'debit' else "Reversed",
                ticket=self.get_customer_receipt(),
                ticket_merchant=self.get_merchant_receipt(),
                owner=transaction['owner'],
                card=applicationName.value,
                payment_transaction_id=refNumber.value,
            )

        except:
            pass

    def get_customer_receipt(self):
        """Gets the transaction receipt destined to the cutomer."""

        receipt_count = ctypes.c_long()
        receipt_text = ctypes.create_string_buffer(4000)
        self.call_eftapi('EFT_GetReceiptCopyCount', ctypes.byref(receipt_count))
        if receipt_count.value:
            self.call_eftapi('EFT_GetReceiptText', ctypes.byref(receipt_text), ctypes.sizeof(receipt_text))
        return receipt_text.value.decode('latin-1')

    def get_merchant_receipt(self):
        """Gets the transaction receipt destined to the merchant."""

        receipt_merchant_count = ctypes.c_long()
        receipt_merchant_text = ctypes.create_string_buffer(4000)
        self.call_eftapi('EFT_GetReceiptMerchantCount', ctypes.byref(receipt_merchant_count))
        if receipt_merchant_count.value:
            self.call_eftapi('EFT_GetReceiptMerchantText', ctypes.byref(receipt_merchant_text), ctypes.sizeof(receipt_merchant_text))
        return receipt_merchant_text.value.decode('latin-1')

    def call_eftapi(self, function, *args):
        """Wrapper for the eftapi calls. If the terminal is busy, waits until
        it's not used anymore. Checks the return value for every call and
        triggers an error if it's different than 0.

        :param function: The name of the eftapi function to be called
        :type function: String
        """

        res = getattr(eftapi, function)(mpdm.mpd_session, *args)
        while res == EFT_BUSY_ERROR:
            res = getattr(eftapi, function)(mpdm.mpd_session, *args)
            time.sleep(1)
        if res != 0:
            self.send_error(res)

    def send_status(self, response=False, stage=False, ticket=False, ticket_merchant=False, error=False, owner=False, cid=False, card=False, payment_transaction_id=False):
        """Triggers a device_changed to notify all listeners of the new status.

        :param response: The result of a transaction
        :type response: String
        :param stage: The status of the transaction
        :type stage: String
        :param ticket: The transaction receipt destined to the merchant, if any
        :type ticket: String
        :param ticket_merchant: The transaction receipt destined to the merchant, if any
        :type ticket_merchant: String
        :param error: The error that happened, if any
        :type error: String
        :param owner: The session id of the POS that should process the update
        :type owner: String
        :param cid: The cid of payment line that is being processed
        :type cid: String
        :param card: The type of card that was used
        :type card: String
        :param payment_transaction_id: The transaction ID given by the terminal
        :type payment_transaction_id: Integer
        """

        self.data = {
            'value': '',
            'Stage': stage,
            'Response': response,
            'Ticket': ticket,
            'TicketMerchant': ticket_merchant,
            'Card': card,
            'PaymentTransactionID': payment_transaction_id,
            'Error': error,
            'Reversal': True,  # The payments can be reversed
            'owner': owner or self.data['owner'],
            'cid': cid or self.cid,
            'processing': self.processing,
        }
        event_manager.device_changed(self)

    def send_error(self, error_code):
        """Retrieves the last error message from the mpd server and sends it to
        all listeners. Throws an Exception to stop the function that was being
        processed.

        :param error_code: The error code that was returned by a call to eftapi
        :type error_code: String
        """

        self.processing = False
        msg = ctypes.create_string_buffer(1000)
        eftapi.EFT_GetExceptionMessage(mpdm.mpd_session, ctypes.byref(msg), ctypes.sizeof(msg))
        error_message = "[%s] %s" % (error_code, msg.value.decode('latin-1'))
        self.send_status(error=error_message)
        _logger.error(error_message)
        raise Exception()
