# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import odoo.tests


@odoo.tests.tagged('post_install', '-at_install')
class TestUi(odoo.tests.HttpCase):

    def test_01_pos_iot_payment_terminal(self):
        env = self.env(user=self.env.ref('base.user_admin'))

        self.env['ir.config_parameter'].sudo().set_param('pos_iot.six_payment_terminal', True)

        # Create IoT Box
        iotbox_id = env['iot.box'].sudo().create({
            'name': 'iotbox-test',
            'identifier': '01:01:01:01:01:01',
            'ip': '1.1.1.1',
        })

        # Create IoT device
        payment_terminal_device = env['iot.device'].sudo().create({
            'iot_id': iotbox_id.id,
            'name': 'Payment terminal',
            'identifier': 'test_payment_terminal',
            'type': 'payment',
            'connection': 'network',
        })

        # Select IoT Box, tick Payment terminal and set payment method in pos config
        main_pos_config = env.ref('point_of_sale.pos_config_main')
        main_pos_config.write({
            'payment_method_ids': [(0, 0, {
                'name': 'Terminal',
                'is_cash_count': False,
                'use_payment_terminal': 'six',
                'iot_device_id': payment_terminal_device.id,
            })],
        })

        self.start_tour("/web", 'payment_terminals_tour', login="admin")

        order = env['pos.order'].search([])
        self.assertEqual(len(order.ids), 1, "There should be only 1 order")
        self.assertEqual(order.state, 'paid', "Validated order has payment of " + str(order.amount_paid) + " and total of " + str(order.amount_total))

    def test_02_pos_iot_scale(self):
        env = self.env(user=self.env.ref('base.user_admin'))

        # Create IoT Box
        iotbox_id = env['iot.box'].sudo().create({
            'name': 'iotbox-test',
            'identifier': '01:01:01:01:01:01',
            'ip': '1.1.1.1',
        })

        # Create IoT device
        iot_device_id = env['iot.device'].sudo().create({
            'iot_id': iotbox_id.id,
            'name': 'Scale',
            'identifier': 'test_scale',
            'type': 'scale',
            'connection': 'direct',
        })

        # Select IoT Box, tick electronic scale
        main_pos_config = env.ref('point_of_sale.pos_config_main')
        main_pos_config.write({
            'iface_scale_id': iot_device_id.id,
        })

        self.start_tour("/web", 'pos_iot_scale_tour', login="admin")
