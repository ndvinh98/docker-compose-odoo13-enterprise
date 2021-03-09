# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests.common import SavepointCase
from odoo.tools import mute_logger


class TestStudioIrModel(SavepointCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # The test mode is necessary in this case.  After each test, we call
        # registry.reset_changes(), which opens a new cursor to retrieve custom
        # models and fields.  A regular cursor would correspond to the state of
        # the database before setUpClass(), which is not correct.  Instead, a
        # test cursor will correspond to the state of the database of cls.cr at
        # that point, i.e., before the call to setUp().
        cls.registry.enter_test_mode(cls.cr)

        # custom m2m field between two models which don't have one yet
        cls.source_model = cls.env["ir.model"].search([("model", "=", "res.currency")])
        cls.destination_model = cls.env["ir.model"].search(
            [("model", "=", "res.country.state")]
        )
        cls.m2m = cls.env["ir.model.fields"].create(
            {
                "ttype": "many2many",
                "model_id": cls.source_model.id,
                "relation": cls.destination_model.model,
                "name": "x_state_ids",
            }
        )

    @classmethod
    def tearDownClass(cls):
        cls.registry.leave_test_mode()
        super().tearDownClass()

    def setUp(self):
        # this cleanup is necessary after each test, and must be done last
        self.addCleanup(self.registry.reset_changes)
        super().setUp()

    def test_next_relation(self):
        """Check that creating the same m2m will result in a new relation table."""
        IrModelFields = self.env["ir.model.fields"].with_context(studio=True)
        current_table = IrModelFields._custom_many2many_names(
            "res.currency", "res.country.state"
        )[0]
        new_m2m = IrModelFields.create(
            {
                "ttype": "many2many",
                "model_id": self.source_model.id,
                "relation": self.destination_model.model,
                "name": "x_state_ids_2",
                "relation_table": IrModelFields._get_next_relation(
                    self.source_model.model, self.destination_model.model
                ),
            }
        )
        self.assertNotEqual(
            new_m2m.relation_table,
            current_table,
            "the second m2m should have its own relation table",
        )

    def test_reverse_relation(self):
        IrModelFields = self.env["ir.model.fields"].with_context(studio=True)
        reverse_m2m = IrModelFields.create(
            {
                "ttype": "many2many",
                "model_id": self.destination_model.id,
                "relation": self.source_model.model,
                "name": "x_currency_ids",
                "relation_table": IrModelFields._get_next_relation(
                    self.destination_model.model, self.source_model.model
                ),
            }
        )
        self.assertEqual(
            self.m2m.relation_table,
            reverse_m2m.relation_table,
            "the second m2m should have the same relation table as the first m2m of the source model",
        )
        new_m2m = IrModelFields.create(
            {
                "ttype": "many2many",
                "model_id": self.source_model.id,
                "relation": self.destination_model.model,
                "name": "x_state_ids_2",
                "relation_table": IrModelFields._get_next_relation(
                    self.source_model.model, self.destination_model.model
                ),
            }
        )
        reverse_new_m2m = IrModelFields.create(
            {
                "ttype": "many2many",
                "model_id": self.destination_model.id,
                "relation": self.source_model.model,
                "name": "x_currency_ids_2",
                "relation_table": IrModelFields._get_next_relation(
                    self.destination_model.model, self.source_model.model
                ),
            }
        )
        self.assertEqual(
            new_m2m.relation_table,
            reverse_new_m2m.relation_table,
            "the second reverse m2m should have the same relation table as the second m2m of the source model",
        )

    def test_lots_of_relations(self):
        IrModelFields = self.env["ir.model.fields"].with_context(studio=True)
        NUM_TEST = 10  # because some people are just that stupid
        attempt = 0
        while attempt < NUM_TEST:
            attempt += 1
            IrModelFields.create(
                {
                    "ttype": "many2many",
                    "model_id": self.source_model.id,
                    "relation": self.destination_model.model,
                    "name": "x_currency_ids_%s" % attempt,
                    "relation_table": IrModelFields._get_next_relation(
                        self.source_model.model, self.destination_model.model
                    ),
                }
            )
        latest_relation = IrModelFields.search_read(
            [
                ("ttype", "=", "many2many"),
                ("model_id", "=", self.source_model.id),
                ("relation", "=", self.destination_model.model),
            ],
            fields=["relation_table"],
            order="id desc",
            limit=1,
        )
        default = IrModelFields._custom_many2many_names(
            self.source_model.model, self.destination_model.model
        )[0]
        self.assertEqual(
            latest_relation[0]["relation_table"], "%s_%s" % (default, NUM_TEST)
        )
