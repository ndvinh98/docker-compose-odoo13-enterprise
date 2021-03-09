odoo.define('planning.tour', function (require) {
    "use strict";

    var core = require('web.core');
    var tour = require('web_tour.tour');

    var _t = core._t;

    tour.register('planning_tour', {
        'skip_enabled': true,
    }, [{
        trigger: '.o_app[data-menu-xmlid="planning.planning_menu_root"]',
        content: _t("Let's start managing your employees' schedule!"),
        position: 'bottom',
    }, {
        trigger: ".o_menu_header_lvl_1[data-menu-xmlid='planning.planning_menu_schedule']",
        content: _t("Use this menu to visualize and schedule shifts"),
        position: "bottom"
    }, {
        trigger: ".o_menu_entry_lvl_2[data-menu-xmlid='planning.planning_menu_schedule_by_employee']",
        content: _t("Use this menu to visualize and schedule shifts"),
        position: "bottom"
    }, {
        trigger: ".o_gantt_button_add",
        content: _t("Create your first shift by clicking on Add. Alternatively, you can use the (+) on the Gantt view."),
        position: "bottom",
    }, {
        trigger: "button[special='save']",
        content: _t("Save this shift as a template to reuse it, or make it recurrent. This will greatly ease your encoding process."),
        position: "bottom",
    }, {
        trigger: ".o_gantt_button_send_all",
        content: _t("Send the schedule to your employees once it is ready."),
        position: "right",
    },{
        trigger: "button[name='action_send']",
        content: _t("Send the schedule and mark the shifts as published. Congratulations!"),
        position: "right",
    },
    ]);
});
