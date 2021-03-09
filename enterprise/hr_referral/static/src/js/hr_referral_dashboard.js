odoo.define('hr.referral.dashboard', function (require) {
"use strict";

var core = require('web.core');
var KanbanController = require('web.KanbanController');
var KanbanView = require('web.KanbanView');
var view_registry = require('web.view_registry');

var _lt = core._lt;

var HrReferralDashboardController = KanbanController.extend({
    start: function () {
        this.$('.o_content').addClass('o_referral_kanban');
        this.$('.o_content').append('<div class="o_referral_kanban_background"/>');
        this.$('.o_referral_kanban_background').append('<div class="hr_referral_bg_city"/>');
        this.$('.o_referral_kanban_background').append('<div class="hr_referral_bg_grass"/>');
        return this._super.apply(this, arguments);
    }
});

var HrReferralDashboardView = KanbanView.extend({
    config: _.extend({}, KanbanView.prototype.config, {
        Controller: HrReferralDashboardController,
    }),
    display_name: _lt('Dashboard'),
    icon: 'fa-dashboard',
});

view_registry.add('employee_referral_dashboard', HrReferralDashboardView);

return {
    Controller: HrReferralDashboardController,
};

});
