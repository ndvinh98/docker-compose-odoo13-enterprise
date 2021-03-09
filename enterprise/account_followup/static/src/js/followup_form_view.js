odoo.define('accountReports.FollowupFormView', function (require) {
"use strict";

/**
 * FollowupFormView
 *
 * The FollowupFormView is a sub-view of FormView. It's used to display
 * the Follow-up reports, and manage the complete flow (send by mail, send
 * letter, ...).
 */

var FollowupFormController = require('account_followup.FollowupFormController');
var FollowupFormModel = require('account_followup.FollowupFormModel');
var FollowupFormRenderer = require('account_followup.FollowupFormRenderer');
var FormView = require('web.FormView');
var viewRegistry = require('web.view_registry');

var FollowupFormView = FormView.extend({
    config: _.extend({}, FormView.prototype.config, {
        Controller: FollowupFormController,
        Model: FollowupFormModel,
        Renderer: FollowupFormRenderer,
    }),
});

viewRegistry.add('followup_form', FollowupFormView);

return FollowupFormView;
});
