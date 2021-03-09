# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.tests import common


class TestMrpPlm(common.TransactionCase):

    def _create_eco(self, name, bom, type_id):
        return self.env['mrp.eco'].create({
            'name': name,
            'bom_id': bom.id,
            'product_tmpl_id': bom.product_tmpl_id.id,
            'type_id': type_id,
            'type': 'bom'})

    def setUp(self):
        super(TestMrpPlm, self).setUp()
        self.Bom = self.env['mrp.bom']
        self.table = self.env.ref("mrp.product_product_computer_desk")
        self.table_sheet = self.env.ref('mrp.product_product_computer_desk_head')
        self.table_leg = self.env.ref('mrp.product_product_computer_desk_leg')
        self.table_bolt = self.env.ref('mrp.product_product_computer_desk_bolt')

        # ------------------------------------------------------
        # Create bill of material for table
        # Computer Table
        #       Table Sheet 1 Unit
        #       Table Lag 3 Unit
        # -------------------------------------------------------

        self.bom_table = self.Bom.create({
            'product_id': self.table.id,
            'product_tmpl_id': self.table.product_tmpl_id.id,
            'product_uom_id': self.table.uom_id.id,
            'product_qty': 1.0,
            'type': 'normal',
            'bom_line_ids': [
                (0, 0, {'product_id': self.table_sheet.id, 'product_qty': 1}),
                (0, 0, {'product_id': self.table_leg.id, 'product_qty': 3})
            ]})
        type_id = self.env['mrp.eco.type'].search([], limit=1).id

        # --------------------------------
        # Create ecos for bill of material.
        # ---------------------------------

        self.eco1 = self._create_eco('ECO1', self.bom_table, type_id)
        self.eco2 = self._create_eco('ECO2', self.bom_table, type_id)
        self.eco3 = self._create_eco('ECO3', self.bom_table, type_id)

    def test_rebase_with_old_bom_change(self):
        "Test eco rebase with old bom changes."

        # Start new revision of eco1.
        self.eco1.action_new_revision()

        # Eco should be in progress and new revision of BoM should be created.
        self.assertTrue(self.eco1.new_bom_id, "New revision of bill of material should be created.")
        self.assertEqual(self.eco1.state, 'progress', "Wrong state on eco")

        # Change old bom lines
        old_bom_leg = self.bom_table.bom_line_ids.filtered(lambda x: x.product_id == self.table_leg)
        new_bom_leg = self.eco1.new_bom_id.bom_line_ids.filtered(lambda x: x.product_id == self.table_leg)

        # Update quantity current bill of materials.
        old_bom_leg.product_qty = 8

        # Check status of eco
        self.assertEqual(self.eco1.state, 'rebase', "Wrong state on eco.")
        self.assertEqual(new_bom_leg.product_qty, 3, "Wrong table leg quantity on new revision of BoM.")

        # Rebase eco1 with current BoM changes ( 3 + 5 ( New added product )).
        self.eco1.apply_rebase()

        # Check quantity of table lag on new revision of BoM.
        self.assertEqual(new_bom_leg.product_qty, 8, "Wrong table leg quantity on new revision of bom.")

        # Add new bom line with product bolt in old BoM.
        self.env['mrp.bom.line'].create({'product_id': self.table_bolt.id, 'bom_id': self.bom_table.id, 'product_qty': 3})

        # Check status of eco and rebase line after adding new product on current BoM.
        self.assertEqual(self.eco1.state, 'rebase', "Wrong state on eco.")
        self.assertEqual(len(self.eco1.bom_rebase_ids), 1, "Wrong rebase line on eco.")
        self.assertEqual(self.eco1.bom_rebase_ids.change_type, 'add', "Wrong type on rebase line.")

        # Rebase eco1 with BoM changes.
        self.eco1.apply_rebase()

        new_bom_bolt = self.eco1.new_bom_id.bom_line_ids.filtered(lambda x: x.product_id == self.table_bolt)

        # Check eco status and bom line should be added on new bom revision.
        self.assertTrue(new_bom_bolt, "BoM line should be added for bolt on new revision of BoM.")
        self.assertEqual(self.eco1.state, 'progress', "Wrong state on eco.")

        # Remove line form current BoM
        self.eco1.bom_id.bom_line_ids.filtered(lambda x: x.product_id == self.table_bolt).unlink()

        # Check status of eco with rebase lines.
        self.assertEqual(self.eco1.state, 'rebase', "Wrong state on eco.")
        self.assertEqual(len(self.eco1.bom_rebase_ids), 1, "Wrong BoM rebase line on eco.")
        self.assertEqual(self.eco1.bom_rebase_ids.change_type, 'update', "Wrong type on rebase line.")
        self.assertEqual(self.eco1.bom_rebase_ids.upd_product_qty, -3, "Wrong quantity on rebase line.")

        # Rebase eco
        self.eco1.apply_rebase()
        self.assertFalse(self.eco1.new_bom_id.bom_line_ids.filtered(lambda x: x.product_id == self.table_bolt), "BoM line should be unlink from new revision of BoM.")

        # Change old BoM leg and new revision BoM leg quantity.
        old_bom_leg.product_qty = 10
        new_bom_leg.product_qty = 12
        self.assertEqual(self.eco1.bom_rebase_ids.change_type, 'update', "Wrong type on rebase line.")
        self.assertEqual(self.eco1.bom_rebase_ids.upd_product_qty, 2, "Wrong quantity on rebase line.")

        # Rebase ecos with changes of old bill of material.
        self.eco1.apply_rebase()
        self.assertEqual(self.eco1.state, 'conflict', "Wrong state on eco.")

        # Manually resolve conflict.
        self.eco1.conflict_resolve()
        self.assertEqual(self.eco1.state, 'progress', "Wrong state on eco.")

    def test_rebase_with_previous_eco_change(self):
        "Test eco rebase with previous eco changes."

        # Start new revision of eco1, eco2, eco3
        self.eco1.action_new_revision()
        self.eco2.action_new_revision()
        self.eco3.action_new_revision()

        # -----------------------------------------
        # Check eco status after start new revision.
        # ------------------------------------------

        self.assertEqual(self.eco1.state, 'progress', "Wrong state on eco1.")
        self.assertEqual(self.eco2.state, 'progress', "Wrong state on eco2.")
        self.assertEqual(self.eco3.state, 'progress', "Wrong state on eco2.")

        # ---------------------------------------------------------------
        # ECO 1 : Update Table Leg quantity in new BoM revision.
        # ---------------------------------------------------------------

        eco1_new_table_leg = self.eco1.new_bom_id.bom_line_ids.filtered(lambda x: x.product_id == self.table_leg)
        eco1_new_table_leg.product_qty = 6

        # -------------------------------------------------------------------------------
        # ECO 1 : Check status of ecos after apply changes and activate new bom revision.
        # -------------------------------------------------------------------------------

        self.eco1.action_apply()
        self.assertFalse(self.eco1.bom_id.active, "Old BoM of eco1 should be deactivated.")
        self.assertTrue(self.eco1.new_bom_id.active, "New BoM revision of ECO 1 should be activated.")
        # Check eco status after activate new bom revision of eco.
        self.assertEqual(self.eco1.state, 'done', "Wrong state on eco1.")
        self.assertEqual(self.eco2.state, 'rebase', "Wrong state on eco2.")
        self.assertEqual(self.eco3.state, 'rebase', "Wrong state on eco3.")

        # ------------------------------
        # ECO 2 : Rebase with ECO 1 changes.
        # ------------------------------

        self.eco2.apply_rebase()
        self.assertEqual(self.eco2.state, 'progress', "Wrong state on eco2.")
        self.assertEqual(self.eco1.new_bom_id.id, self.eco2.bom_id.id, "Eco2 BoM should replace with new activated BoM revision of Eco1.")

        # ----------------------------------------------------------------------
        # ECO 2 : Add new product 'Table Bolt'
        # ----------------------------------------------------------------------

        self.eco2.new_bom_id.bom_line_ids.create({'product_id': self.table_bolt.id, 'bom_id': self.eco2.new_bom_id.id, 'product_qty': 3})
        self.assertTrue(self.eco2.bom_change_ids, "Eco 2 should have BoM change lines.")

        # -------------------------------------------------------------------------------
        # ECO 2 : Check status of after apply changes and activate new bom revision.
        # -------------------------------------------------------------------------------

        self.eco2.action_apply()

        self.assertFalse(self.eco1.bom_id.active, "BoM of ECO 1 should be deactivated")
        self.assertFalse(self.eco1.new_bom_id.active, "BoM revision of ECO 1 should be deactivated")
        self.assertTrue(self.eco2.new_bom_id.active, "BoM revision of ECO 2 should be activated")

        # -----------------------------------------------------
        # ECO3 : Change same line in eco3 as changes in eco1.
        # ----------------------------------------------------

        eco3_new_table_leg = self.eco3.new_bom_id.bom_line_ids.filtered(lambda x: x.product_id == self.table_leg)
        eco3_new_table_leg.product_qty = 4

        # -----------------------------------
        # Rebase eco3 with eco1 BoM changes.
        # -----------------------------------

        self.eco3.apply_rebase()

        # Check status of eco3 after rebase.
        self.assertEqual(self.eco3.state, 'conflict', "Wrong state on eco.")

        # Resolve conflict manually.
        self.assertTrue(self.eco3.previous_change_ids.ids, "Wrong previous bom change on bom lines.")
        self.eco3.conflict_resolve()
        self.assertEqual(self.eco3.state, 'progress', "Wrong state on eco.")
        self.eco3.action_apply()
        self.assertFalse(self.eco2.new_bom_id.active, "BoM revision of ECO 2 should be deactivated")
        self.assertTrue(self.eco3.new_bom_id.active, "BoM revision of ECO 3 should be activated")
        self.assertFalse(self.eco3.previous_change_ids.ids)
        self.assertFalse(self.eco3.bom_rebase_ids.ids)
