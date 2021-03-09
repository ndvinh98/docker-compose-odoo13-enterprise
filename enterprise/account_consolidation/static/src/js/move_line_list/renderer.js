odoo.define('account_consolidation.MLListRenderer', function (require) {
    "use strict";

    var ParentListRenderer = require('account_accountant.MoveLineListView').AccountMoveListRenderer;
    var _t = require('web.core')._t;

    return ParentListRenderer.extend({
        init: function (parent, action) {
            this._super.apply(this, arguments);
            this.currencies_are_different = !!action.context.currencies_are_different;
            this.currencies = action.context.currencies || null;
            this.consolidation_rate = action.context.consolidation_rate || 100.0;
            this.warning_messages = {
                'currencies': _t('Take into account that the consolidation (%s) and the consolidated company (%s) have different currencies.'),
                'rate': _t('Take into account that this company is consolidated at %s%%.'),
                'both': _t('Take into account that the consolidation (%s) and the consolidated company (%s) have different currencies and the company is consolidated at %s%%.')
            }
        },
        _renderView: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                self._renderWarnings();
            });
        },
        _renderWarnings: function () {
            var warning_message;
            if (this.currencies_are_different && this.consolidation_rate < 100.0)
            {
                warning_message = _.str.sprintf(this.warning_messages['both'], this.currencies.chart, this.currencies.company, this.consolidation_rate);
            }
            else if (this.currencies_are_different)
            {
                warning_message = _.str.sprintf(this.warning_messages['currencies'], this.currencies.chart, this.currencies.company);
            }
            else if (this.consolidation_rate < 100.0)
            {
                warning_message = _.str.sprintf(this.warning_messages['rate'], this.consolidation_rate);
            }
            if (!!warning_message) {
                var $alert = $('<div class="alert alert-info text-center" role="status"></div>');
                $alert.text(warning_message);
                this.$el.prepend($alert);
            }
        }
    });
});
