"use strict";
odoo.define('timesheet.tour', function(require) {

var core = require('web.core');
var tour = require('web_tour.tour');

var _t = core._t;

tour.register('timesheet_tour', {
    url: "/web",
}, [tour.STEPS.SHOW_APPS_MENU_ITEM, {
    trigger: '.o_app[data-menu-xmlid="hr_timesheet.timesheet_menu_root"]',
    content: _t('Track the time spent on your projects. <i>It starts here.</i>'),
    position: 'bottom',
}, {
    trigger: '.o_grid_button_add',
    content: _t('Timesheets are done on tasks, click here to create your first one.'),
    position: 'bottom',
}, {
    trigger: ".modal-body .o_timesheet_tour_project_name",
    content: _t('Choose a <b>project name</b>. (e.g. name of a customer, or product)'),
    position: "right",
    run: function (actions) {
        actions.auto();
    },
}, {
    trigger: ".modal-body .o_timesheet_tour_task_name",
    content: _t('Use tasks to track the different type of activities. (e.g. Graphic Design, Programming, Project Management)'),
    position: "right",
    run: function (actions) {
        actions.auto(".modal-footer .btn-secondary");
    },
}, {
    trigger: '.o_grid_input',
    content: _t('Set the number of hours done on this task, for every day of the week. (e.g. 1.5 or 1:30)'),
    position: 'top',
    run: function (actions) {
        actions.text("4", this.$anchor);
    },
}]);

});
