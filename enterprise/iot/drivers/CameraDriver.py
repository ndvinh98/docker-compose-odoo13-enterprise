# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import tempfile
import subprocess

from odoo.addons.hw_drivers.controllers.driver import event_manager, Driver


class CameraDriver(Driver):
    connection_type = 'video'

    def __init__(self, device):
        super(CameraDriver, self).__init__(device)
        self._device_type = 'camera'
        self._device_connection = 'direct'
        self._device_name = self.dev.card.decode('utf-8')

    @classmethod
    def supported(cls, device):
        return device.driver.decode('utf-8') == 'uvcvideo'

    def action(self, data):
        try:
            """
            Check the max resolution for webcam.
            Take picture, output it on stdout and convert it in base 64.
            Release Event with picture in data.
            """
            v4l2 = subprocess.Popen(['v4l2-ctl', '--list-formats-ext'], stdout=subprocess.PIPE)
            all_sizes = subprocess.Popen(['grep', 'Size'], stdin=v4l2.stdout, stdout=subprocess.PIPE)
            all_resolutions = subprocess.Popen(['awk', '{print $3}'], stdin=all_sizes.stdout, stdout=subprocess.PIPE)
            sorted_resolutions = subprocess.Popen(['sort', '-rn'], stdin=all_resolutions.stdout, stdout=subprocess.PIPE)
            resolution = subprocess.check_output(['awk', 'NR==1'], stdin=sorted_resolutions.stdout).decode('utf-8')
            self.data['image'] = base64.b64encode(subprocess.check_output(["fswebcam", "-d", self.dev.interface, "-", "-r", resolution]))
            self.data['message'] = 'Image captured'
        except subprocess.CalledProcessError as e:
            self.data['message'] = e.output
        event_manager.device_changed(self)
