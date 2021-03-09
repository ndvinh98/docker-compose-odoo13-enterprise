odoo.define('projcet_timesheet_synchro.app', function (require) {
'use strict';

    var AbstractAction = require('web.AbstractAction');
    var config = require('web.config');
    var core = require('web.core');
    var IFrameWidget = require('web.IFrameWidget');

    var project_timesheet_synchro_demo = AbstractAction.extend({
        contentTemplate: 'project_timesheet_synchro.demo',
        start: function () {
            var def;
            if (config.device.size_class >= config.device.SIZES.MD) {
                var app = new project_timesheet_synchro_app();
                def = app.appendTo(this.$('.o_project_timesheet_app'));
            }
            return Promise.all([def, this._super.apply(this, arguments)]);
        },
    });

    var project_timesheet_synchro_app = IFrameWidget.extend({
        init: function (parent) {
            this._super(parent, '/project_timesheet_synchro/timesheet_app');
        },
        start: function () {
            var res = this._super.apply(this, arguments);
            this.$el.css({height: '582px', width: '330px', border: 0});
            return res;
        },
    });

    core.action_registry.add('project_timesheet_synchro_app_action', project_timesheet_synchro_demo);

});