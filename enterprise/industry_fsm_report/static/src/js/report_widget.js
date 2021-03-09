odoo.define('industry_fsm_report.report_button', function (require) {
"use strict";


var widget_registry = require('web.widget_registry');
var Widget = require('web.Widget');


var OpenStudioButton = Widget.extend({
    tagName: 'button',
    className: 'o_fsm_report_button btn btn-primary',
    events: {
        'click': '_onButtonClick',
    },

    /**
     * @override
     */
    init: function(parent, record) {
        this.record = record;
        this._super.apply(this, arguments);
    },

    /**
     * @override
     */
    start: function () {
        this._super.apply(this, arguments);
        this.$el.text(_('Design Worksheet Template'));
    },

    /**
     * @override
     * @private
     */
    _onButtonClick: function (event) {
        var self = this;
        this._rpc({
            'model': 'project.worksheet.template',
            'method': 'get_x_model_form_action',
            'args': [this.record.res_id]
        })
        .then(function (act) {
            return self.do_action(act);
        })
        .then(function () {
            self.trigger_up('studio_icon_clicked');
        });
    }
});

widget_registry.add('open_studio_button', OpenStudioButton);

});
