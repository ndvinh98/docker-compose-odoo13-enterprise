odoo.define('approvals_tour', function(require) {
    "use strict";

    var core = require('web.core');
    var tour = require('web_tour.tour');

    var _t = core._t;

    tour.register('approvals_tour', {
        test: true,
        url: "/web",
    },[
        {
            trigger: '.o_app[data-menu-xmlid="approvals.approvals_menu_root"]',
            content: 'open approvals app',
            run: 'click',
        },
        {
            trigger: '.oe_kanban_action_button:first',
            content: 'create new request',
            run: 'click',
        },
        {
            trigger: 'input[name="name"]',
            content: 'give name',
            run: 'text Business Trip To Berlin',
        },
        {
            trigger: 'input[name="date_start"]',
            content: 'give start date',
            run: 'text 12/13/2018 13:00:00',
        },
        {
            trigger: 'input[name="date_end"]',
            content: 'give end date',
            run: 'text 12/20/2018 13:00:00',
        },
        {
            trigger: 'input[name="location"]',
            content: 'give location',
            run: 'text Berlin, Schulz Hotel',
        },
        {
            trigger: 'textarea[name="reason"]',
            content: 'give description',
            run: 'text We need to go, because reason (and also for beer))',
        },
        {
            trigger: 'a:contains("Approver(s)"):first',
            content: 'open approvers page',
            run: 'click',
        },
        {
            trigger: ".o_field_x2many_list_row_add > a",
            content: 'add an approver',
            run: 'click',
        },
        {
            content: "select an approver",
            trigger: '.o_selected_row .o_input_dropdown',
            run: function (actions) {
                actions.text("Marc", this.$anchor.find("input"));
            },
        },
        {
            trigger: ".ui-autocomplete > li > a:contains(Marc)",
            auto: true,
        },
        {
            trigger: '.o_form_button_save',
            content: 'save the request',
            run: 'click',
        },
        {
            trigger: '.o_form_button_edit',
            content: 'wait the save',
            run: function(){},
        },
        {
            trigger: 'button[name="action_confirm"]',
            content: 'confirm the request',
            run: 'click',
        },
        {
            trigger: '.o_activity_action_approve',
            content: 'approve the request via activity',
            run: 'click',
        },
        {
            trigger: 'button[name="action_withdraw"]',
            content: 'withdraw approver',
            run: 'click',
        },
        {
            trigger: 'button[name="action_refuse"]',
            content: 'refuse request',
            run: 'click',
        },
        {
            trigger: 'button[title="Current state"][data-value="refused"]',
            content: 'wait the request status compute',
            run: function(){},
        },
        {
            trigger: 'button[name="action_cancel"]',
            content: 'cancel request',
            run: 'click',
        },
        {
            trigger: 'button[name="action_draft"]',
            content: 'back the request to draft',
            run: 'click',
        },
        {
            trigger: 'button[name="action_confirm"]',
            content: 'confirm the request again',
            run: 'click',
        },
        {
            trigger: 'button[name="action_approve"]',
            content: 'approve request',
            run: 'click',
        },
    ]);

});
