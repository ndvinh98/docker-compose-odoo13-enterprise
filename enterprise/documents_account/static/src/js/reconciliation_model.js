odoo.define('documents_account.StatementModel', function (require) {
"use strict";

var reconciliationModel = require('account.ReconciliationModel');

reconciliationModel.StatementModel.include({

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Recursively executes the actions of the list.
     *
     * @private
     * @param {Object[]} list list of actions to perform
     * @returns {Deferred}
     */
    _executeActionList: function(list) {
        var self = this;
        if (list.length === 0) {
           return Promise.resolve();
        }
        var action = list.pop();
        return this.do_action(action, {
            on_close: function () {
                return self._executeActionList(list);
            }
        });
    },
    /**
     * handles the return values of the process line method
     *
     * @override
     * @private
     * @param {Object} data
     * @param {Object[]} data.moves list of processed account.move
     * @param {Object[]} data.document_actions list of actions
     * @returns {Deferred}
     */
   _validatePostProcess: function (data) {
        if (data.documents_actions) {
            return this._executeActionList(data.documents_actions);
        }
        return this._super.apply(this, arguments);
    },
});
});
