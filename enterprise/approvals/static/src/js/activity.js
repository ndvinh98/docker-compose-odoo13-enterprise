odoo.define('approvals.Activity', function (require) {
    "use strict";

var field_registry = require('web.field_registry');

require('mail.Activity');

var KanbanActivity = field_registry.get('kanban_activity');
var MailActivity = field_registry.get('mail_activity');

/**
 * Monkey-patch all activity widgets with approval feature
 *
 * @param {mail.Activity} Activity either KanbanActivity or MailActivity
 */
function applyInclude(Activity) {
    Activity.include({
        events: _.extend({}, Activity.prototype.events, {
            'click .o_activity_action_approve': '_onValidateApproval',
            'click .o_activity_action_refuse': '_onRefuseApproval',
        }),
        //--------------------------------------------------------------------------
        // Handlers
        //--------------------------------------------------------------------------
        /**
         * @private
         * @param  {Event} event
         */
        _onValidateApproval: function (event) {
            var self = this;
            var approverID = $(event.currentTarget).data('approver-id');
            this._rpc({
                model: 'approval.approver',
                method: 'action_approve',
                args: [[approverID]],
            }).then(function(result) {
                self.trigger_up('reload');
            });
        },
        /**
         * @private
         * @param  {Event} event
         */
        _onRefuseApproval: function (event) {
            var self = this;
            var approverID = $(event.currentTarget).data('approver-id');
            this._rpc({
                model: 'approval.approver',
                method: 'action_refuse',
                args: [[approverID]],
            }).then(function(result) {
                self.trigger_up('reload');
            });
        },
    });
}

applyInclude(KanbanActivity);
applyInclude(MailActivity);

});