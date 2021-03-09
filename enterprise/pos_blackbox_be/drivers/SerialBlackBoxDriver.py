# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import serial
import os

from odoo.addons.hw_drivers.controllers.driver import event_manager
from odoo.addons.hw_drivers.drivers.SerialBaseDriver import SerialDriver, SerialProtocol, serial_connection

_logger = logging.getLogger(__name__)

BlackboxProtocol = SerialProtocol(
    name='Retail Innovation Cleancash',
    baudrate=19200,
    bytesize=serial.EIGHTBITS,
    stopbits=serial.STOPBITS_ONE,
    parity=serial.PARITY_NONE,
    timeout=3,
    writeTimeout=0.2,
    measureRegexp=None,
    statusRegexp=None,
    commandTerminator=b'',
    commandDelay=0.2,
    measureDelay=0.2,
    newMeasureDelay=0.2,
    measureCommand=b'',
    emptyAnswerValid=False,
)

STX = b'\x02'
ETX = b'\x03'
ACK = b'\x06'
NACK = b'\x15'


class BlackBoxDriver(SerialDriver):
    """Driver for the blackbox fiscal data module."""

    _protocol = BlackboxProtocol

    def __init__(self, device):
        self._device_type = 'fiscal_data_module'

        super().__init__(device)
        self._set_actions()

    def _set_actions(self):
        """Initializes `self._actions`, a map of action keys sent by the frontend to backend action methods."""

        self._actions.update({
            'request': self._request_action,
            'request_serial': self._request_serial_action,
        })

    def _request_action(self, data):
        self._connection.reset_output_buffer()
        self._connection.reset_input_buffer()
        packet = self._wrap_low_level_message_around(data['high_level_message'])
        self.data['value'] = self._send_to_blackbox(packet, data['response_size'], self._connection)
        event_manager.device_changed(self)

    def _request_serial_action(self, data):
        with open('/sys/class/net/eth0/address', 'rb') as f:
            self.data['value'] = f.read().rstrip().replace(b':', b'')[-7:]
            event_manager.device_changed(self)

    @classmethod
    def supported(cls, device):
        """Checks whether the device at path `device` is supported by the driver.
        :param device: path to the device
        :type device: str
        :return: whether the device is supported by the driver
        :rtype: bool
        """

        try:
            protocol = cls._protocol
            probe_message = cls._wrap_low_level_message_around("S000")
            with serial_connection(device['identifier'], protocol) as connection:
                return cls._send_and_wait_for_ack(probe_message, connection)
        except serial.serialutil.SerialTimeoutException:
            pass
        except Exception:
            _logger.exception('Error while probing %s with protocol %s' % (device, protocol.name))

    @staticmethod
    def _lrc(msg):
        """"Compute a message's longitudinal redundancy check value.
        :param msg: the message the LRC is computed for
        :type msg: byte
        :return: the message LRC
        :rtype: int
        """
        lrc = 0

        for character in msg:
            byte = ord(character)
            lrc = (lrc + byte) & 0xFF

        lrc = ((lrc ^ 0xFF) + 1) & 0xFF

        return lrc

    @classmethod
    def _wrap_low_level_message_around(cls, high_level_message):
        """Builds a low level message to be sent the blackbox.
        :param high_level_message: The message to be transmitted to the blackbox
        :type high_level_message: str
        :return: The modified message as it is transmitted to the blackbox
        :rtype: bytearray
        """

        bcc = cls._lrc(high_level_message)
        high_level_message_bytes = (ord(b) for b in high_level_message)

        low_level_message = bytearray()
        low_level_message.append(0x02)
        low_level_message.extend(high_level_message_bytes)
        low_level_message.append(0x03)
        low_level_message.append(bcc)

        return low_level_message

    @staticmethod
    def _send_and_wait_for_ack(packet, connection):
        """Sends a message to and wait for acknoledgement from the blackbox.
        :param packet: the message sent to the blackbox
        :type packet: bytearray
        :param connection: serial connection to the blackbox
        :type connection: serial.Serial
        :return: wether the blackbox acknowledged the message it received
        :rtype: bool
        """

        connection.write(packet)
        ack = connection.read(1)

        # This violates the principle that we do high level
        # client-side and low level posbox-side but the retry
        # counter is always in a fixed position in the high level
        # message so it's safe to do it. Also it would be a pain
        # to have to throw this all the way back to js just so it
        # can increment the retry counter and then try again.
        packet[4] += 1

        if ack == ACK:
            return True
        else:
            return False

    def _send_to_blackbox(self, packet, response_size, connection):
        """Sends a message to and wait for a response from the blackbox.
        :param packet: the message to be sent to the blackbox
        :type packet: bytearray
        :param response_size: number of bytes of the expected response
        :type response_size: int
        :param connection: serial connection to the blackbox
        :type connection: serial.Serial
        :return: the response to the sent message
        :rtype: bytearray
        """

        got_response = False

        if self._send_and_wait_for_ack(packet, connection):
            stx = connection.read(1)
            response = connection.read(response_size).decode()
            etx = connection.read(1)
            bcc = connection.read(1)

            if stx == STX and etx == ETX and bcc and self._lrc(response) == ord(bcc):
                got_response = True
                connection.write(ACK)
            else:
                _logger.warning("received ACK but not a valid response, sending NACK...")
                connection.write(NACK)

        if not got_response:
            _logger.error("sent 1 NACKS without receiving response, giving up.")
        else:
            _logger.error(type(response))
            return response
