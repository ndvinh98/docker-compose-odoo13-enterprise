odoo.define('account_consolidation.FieldJson', function (require) {
    "use strict";
    var AbstractField = require('web.AbstractField');
    var fieldRegistry = require('web.field_registry');
    var core = require('web.core');
    var QWeb = core.qweb;

    var FieldJson = AbstractField.extend({
        className: 'o_field_json',
        supportedFieldTypes: ['char'],

        events: {
            'click .js_unmapped_account': '_executeAction',
        },

        /**
         * @override
         */
        init: function () {
            this._super.apply(this, arguments);
            this.row_classes = this.nodeOptions.row_classes || '';
            this.container_classes = this.attrs && this.attrs.class || '';
            this.field_template = this.nodeOptions.template || 'JsonKeyValueField';
        },
        /**
         * @override
         */
        willStart: function () {
            var superDef = this._super.apply(this, arguments);
            this._parseJSON();
            return superDef;
        },
        /**
         * Parse the JSON field value and store it in this.parsed_data.
         * @private
         */
        _parseJSON: function () {
            var record_field_value = this.recordData[this.name];
            if (!!record_field_value) {
                this.parsed_data = JSON.parse(record_field_value);
            }
        },
        /**
         * @override
         */
        _render: function () {
            var render_context = {
                classes: this.row_classes,
                field_values: this.parsed_data
            };
            this.$el.addClass(this.container_classes);
            this.$el.html($(QWeb.render(this.field_template, render_context)));
        },

        _executeAction: function (e) {
            e.preventDefault();
            var self = this;
            var $target = $(e.currentTarget);
            if ($target.attr('data-type') === 'object') {
                var rpc_config = {
                    model: self.model,
                    method: $target.data('name'),
                    args: [[self.res_id]],
                    context: {company_id: parseInt($target.attr('data-company-id'), 10)}
                };
                this._rpc(rpc_config).then(function (result) {
                    return self.do_action(result);
                });
            }
        }
    });

    fieldRegistry.add('json', FieldJson);


    return FieldJson;
});
