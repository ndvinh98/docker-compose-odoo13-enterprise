odoo.define('account_consolidation.GridController', function (require) {
    "use strict";

    var WebGridController = require('web_grid.GridController');
    var dialogs = require('web.view_dialogs');
    var core = require('web.core');
    var _t = core._t;


    return WebGridController.extend({
        init: function (parent, action) {
            this._super.apply(this, arguments);
            self.add_column_label = _t('Add a column');
            self.view_report_label = _t('Consolidated balance');
        },
        renderButtons: function ($node) {
            this._super.apply(this, arguments);
            if (!!this.context.default_period_id) {
                this.view_report_btn = $('<button class="btn btn-secondary o_grid_button_view_report" type="button" role="button"/>');
                this.view_report_btn.text(self.view_report_label);
                this.view_report_btn.on('click', this._onViewReport.bind(this));
                $node.prepend(this.view_report_btn);
                this.add_col_btn = $('<button class="btn btn-primary o_grid_button_add" type="button" role="button"/>');
                this.add_col_btn.text(self.add_column_label);
                this.add_col_btn.on('click', this._onAddColumn.bind(this));
                $node.prepend(this.add_col_btn);
            }
        },
        _onAddColumn: function (e) {
            event.preventDefault();
            var self = this;
            new dialogs.FormViewDialog(this, {
                res_model: 'consolidation.journal',
                res_id: false,
                context: {'default_period_id': self.context.default_period_id},
                title: self.add_column_label,
                disable_multiple_selection: true,
                on_saved: this.reload.bind(this, {})
            }).open();
        },
        _onViewReport: function (e) {
            event.preventDefault();
            var self = this;
            this.do_action('account_consolidation.trial_balance_report_action', {
                additional_context:{
                    default_period_id: self.context.default_period_id
                }
            });
        }
    });
});
