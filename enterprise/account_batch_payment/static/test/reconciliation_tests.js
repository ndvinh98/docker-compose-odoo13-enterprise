odoo.define('account_batch_payment.reconciliation_tests.data', function (require) {
"use strict";

var data = require('account.reconciliation_tests.data');

data.params.data["account.reconciliation.widget"].get_batch_payments_data = function (args) {
    return Promise.resolve();
};

data.params.data["account.reconciliation.widget"].get_move_lines_by_batch_payment = function (args) {
    return Promise.resolve(data.params.mv_lines['[5,"b",0]']);
};

data.params.data_preprocess.batch_payments = [{
    'amount_currency_str': false,
    'journal_id': 84,
    'id': 1,
    'amount_str': "$ 10,980.00",
    'name': "BATCH/IN/2017/0001"
}];

});

odoo.define('account_batch_payment.reconciliation_tests', function (require) {
"use strict";

var ReconciliationClientAction = require('account.ReconciliationClientAction');
var demoData = require('account.reconciliation_tests.data');
var testUtils = require('web.test_utils');

QUnit.module('account', {
    beforeEach: function () {
        this.params = demoData.getParams();
    }
}, function () {
    QUnit.module('Reconciliation');

    QUnit.test('Reconciliation basic rendering with account_batch_payment', async function (assert) {
        assert.expect(4);

        var clientAction = new ReconciliationClientAction.StatementAction(null, this.params.options);
        testUtils.mock.addMockEnvironment(clientAction, {
            data: this.params.data,
            archs: {
                'account.bank.statement.line,false,search': '<search string="Statement Line"><field name="display_name"/></search>',
            },
        });
        await clientAction.appendTo($('#qunit-fixture'));

        assert.containsNone(clientAction.widgets[0], '.batch_payment',
            "should not have 'Select a Batch Payment' button");

        var widget = clientAction.widgets[1];
        await testUtils.dom.click(widget.$('.accounting_view thead td:first'));
        assert.containsOnce(widget, '.batch_payment',
            "should display 'Select a Batch Payment' button");

        assert.containsNone(widget, '.accounting_view tbody tr',
            "should have not reconciliation propositions");
        await testUtils.dom.click(widget.$('.nav-item.batch_payments_selector a:first'));
        await testUtils.dom.click(widget.$('.batch_payment'));

        assert.containsN(widget, '.accounting_view tbody tr', 2,
            "should have 2 reconciliation propositions");

        clientAction.destroy();
    });

});
});
