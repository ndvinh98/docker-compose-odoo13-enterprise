odoo.define('account_followup.FollowupFormController', function (require) {
"use strict";

var FormController = require('web.FormController');
var core = require('web.core');
var QWeb = core.qweb;
var _t = core._t;

var FollowupFormController = FormController.extend({
    events: _.extend({}, FormController.prototype.events, {
        'click .o_account_followup_manual_action_button': '_onManualAction',
        'click .o_account_followup_print_letter_button': '_onPrintLetter',
        'click .o_account_followup_send_mail_button': '_onSendMail',
        'click .o_account_followup_send_sms_button': '_onSendSMS',
        'click .o_account_followup_do_it_later_button': '_onDoItLater',
        'click .o_account_followup_done_button': '_onDone',
        'click .o_account_followup_reconcile': '_onReconcile',
    }),
    custom_events: _.extend({}, FormController.prototype.custom_events, {
        expected_date_changed: '_onExpectedDateChanged',
        next_action_date_changed: '_onChangeReminderDate',
        on_change_block: '_onChangeBlocked',
        on_change_trust: '_onChangeTrust',
        on_save_summary: '_onSaveSummary',
        on_trigger_action: '_onTriggerAction'
    }),
    /**
     * @override
     */
    init: function () {
        this._super.apply(this, arguments);
        // force refresh search view on subsequent navigation
        delete this.searchView;
        this.hasSidebar = false;
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------
    /**
     * @override
     */
    renderButtons: function ($node) {
        this.$buttons = $(QWeb.render("CustomerStatements.buttons", {
            widget: this
        }));
        this.$buttons.appendTo($node);
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Check if the follow-up flow is complete (all the follow-up reports are done
     * or skipped). If the flow is complete, display a rainbow man.
     *
     * @private
     */
    _checkDone: function () {
        if (this.model.isJobComplete()){
            var message = _.str.sprintf(_t('You are done with the follow-ups!<br/>You have skipped %s partner(s).'),
                this.model.getSkippedPartners());
            this.trigger_up('show_effect', {
                type: 'rainbow_man',
                fadeout: 'no',
                message: message,
            });
        }
    },
    /**
     * Display the done button in the header and remove any mail alert.
     *
     * @private
     */
    _displayDone: function () {
        this.$buttons.find('button.o_account_followup_done_button').show();
        this.renderer.removeMailAlert();
    },
    /**
     * Display the next follow-up.
     *
     * @private
     */
    _displayNextFollowup: function () {
        var currentIndex = this.model.removeCurrentRecord(this.handle);
        var params = {
            limit: 1,
            offset: currentIndex,
        };
        this.update(params);
        this.$buttons.find('button.o_account_followup_done_button').hide();
        this._checkDone();
    },
    /**
     * Remove the highlight on Send Email button.
     *
     * @private
     */
    _removeHighlightEmail: function () {
        this.$buttons.find('button.o_account_followup_send_mail_button')
            .removeClass('btn-primary').addClass('btn-secondary');
    },
    /**
     * Remove the highlight on Send SMS button.
     *
     * @private
     */
    _removeHighlightSMS: function () {
        this.$buttons.find('button.o_account_followup_send_sms_button')
            .removeClass('btn-primary').addClass('btn-secondary');
    },
    /**
     * Remove the highlight on Print Letter button.
     *
     * @private
     */
    _removeHighlightPrint: function () {
        this.$buttons.find('button.o_account_followup_print_letter_button')
            .removeClass('btn-primary').addClass('btn-secondary');
    },
    /**
     * @override
     * @private
     */
    _update: function () {
        var self = this;
        return this._super.apply(this, arguments).then(function () {
            self._updateSearchView();
            self._updateButtons();
        });
    },
    /**
     * Update the pager with the progress of the follow-ups.
     *
     * @private
     * @override
     */
    _updatePager: function () {
        if (this.pager) {
            var progressInfo = this.model.getProgressInfos();
            this.pager.updateState({
                current_min: progressInfo.currentElementIndex + 1,
                size: progressInfo.numberTodo,
            });
            this.pager.do_toggle(true);
        }
    },
    /**
     * Replace the search view with a progress bar.
     *
     * @private
     */
    _updateSearchView: function () {
        var progressInfo = this.model.getProgressInfos();
        var total = progressInfo.numberDone + progressInfo.numberTodo;
        this.$searchview = $(QWeb.render("CustomerStatements.followupProgressbar", {
            current: progressInfo.numberDone,
            max: progressInfo.numberDone + progressInfo.numberTodo,
            percent: (progressInfo.numberDone / total * 100),
        }));
        this.updateControlPanel({
            cp_content: {
                $searchview: this.$searchview,
            }}, {
            clear: false,
        });
    },
    /**
     * Update the buttons according to followup_level.
     *
     * @private
     */
    _updateButtons: function () {
        let setButtonClass = (button, primary) => {
            /* Set class 'btn-primary' if parameter `primary` is true
             * 'btn-secondary' otherwise
             */
            let addedClass = primary ? 'btn-primary' : 'btn-secondary'
            let removedClass = !primary ? 'btn-secondary' : 'btn-primary'
            this.$buttons.find(`button.${button}`)
                .removeClass(removedClass).addClass(addedClass);
        }
        if (!this.$buttons) {
            return;
        }
        var followupLevel = this.model.localData[this.handle].data.followup_level;
        setButtonClass('o_account_followup_print_letter_button', followupLevel.print_letter)
        setButtonClass('o_account_followup_send_mail_button', followupLevel.send_email)
        setButtonClass('o_account_followup_send_sms_button', followupLevel.send_sms)
        if (followupLevel.manual_action) {
            this.$buttons.find('button.o_account_followup_manual_action_button')
                .html(followupLevel.manual_action_note);
            setButtonClass('o_account_followup_manual_action_button', !followupLevel.manual_action_done)
        } else {
            this.$buttons.find('button.o_account_followup_manual_action_button').hide();
        }
    },

    _getPartner() {
        return this.model.get(this.handle, {raw: true}).res_id;
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * When a move line is blocked or unblocked, we have to write it in DB
     * and reload the HTML to update the total due and total overdue.
     *
     * @private
     * @param {OdooEvent} event
     */
    _onChangeBlocked: function (event) {
        var self = this;
        var checkbox = event.data.checkbox;
        var targetID = event.data.targetID;
        this.model.changeBlockedMoveLine(parseInt(targetID), checkbox).then(function () {
            self.reload();
        });
    },
    /**
     * When the trust of a partner is changed, we have to write it in DB.
     *
     * @private
     * @param {OdooEvent} event
     */
    _onChangeTrust: function (event) {
        var self = this;
        var newTrust = event.data.newTrust;
        this.model.changeTrust(this.handle, newTrust).then(function () {
            self.renderer.renderTrust(newTrust);
        });
    },
    /**
     * Update the next reminder date
     *
     * @private
     */
     _onChangeReminderDate: function(ev) {
         ev.stopPropagation();
         this.model.setNextActionDate(this.handle, ev.data.newDate);
         this.model.updateNextAction(this.handle, 'change_date')
     },
    /**
     * When the user skip the partner, we have to update the next action
     * date and update the progress and increase the number of
     * follow-ups SKIPPED.
     *
     * @private
     */
    _onDoItLater: function () {
        var self = this;
        this.model.updateNextAction(this.handle, 'later').then(function () {
            self.model.increaseNumberSkipped();
            self._displayNextFollowup();
        });
    },
    /**
     * When the user mark as done a customer statement, we have to
     * update the next action date and update the progress,
     * and increase the number of follow-ups DONE.
     *
     * @private
     */
    _onDone: function () {
        var self = this;
        this.model.updateNextAction(this.handle, 'done').then(function () {
            self.model.increaseNumberDone();
            self._displayNextFollowup();
        });
    },
    /**
     * Change the payment expected date of an account.move.line.
     *
     * @private
     * @param {OdooEvent} event
     */
    _onExpectedDateChanged: function (event) {
        event.stopPropagation();
        var self = this;
        this.model.changeExpectedDate(this.handle, event.data.moveLineID, event.data.newDate).then(function () {
            self.reload();
        });
    },
    /**
     * When click on 'Reconcile' it will redirect on reconciliation.
     *
     * @private
     */
    _onReconcile: function () {
        var context = {
            'mode': 'customers',
            'partner_ids': [this._getPartner()],
            'all_entries': true,
        }
        this.do_action({
            type: 'ir.actions.client',
            tag: 'manual_reconciliation_view',
            views: [[false, 'form']],
            target: 'current',
            context: context,
        });
    },
    /**
     * Print the customer statement.
     *
     * @private
     */
    _onPrintLetter: function () {
        var self = this;
        this.model.doPrintLetter(this.handle);
        var records = {
            ids: [this._getPartner()],
        };
        this._rpc({
            model: 'account.followup.report',
            method: 'print_followups',
            args: [records],
        })
        .then(function (result) {
            self.do_action(result);
            self._removeHighlightPrint();
            self._displayDone();
        });
    },
    /**
     * When the user click on the manual action button, we need to update it
     * in the backend.
     *
     * @private
     */
    _onManualAction: function () {
        var self = this;
        var partnerID = this.model.localData[this.handle].res_id;
        var followupLevel = this.model.localData[this.handle].data.followup_level.id;
        var options = {
            partner_id: partnerID
        };
        this.model.doManualAction(this.handle);
        if (followupLevel) {
            options['followup_level'] = followupLevel;
        }
        this._rpc({
            model: 'account.followup.report',
            method: 'do_manual_action',
            args: [options]
        })
        .then(function () {
            self.renderer.chatter.trigger_up('reload_mail_fields', {
                activity: true,
                thread: true,
                followers: true
            });
            self._displayDone();
        });
    },
    /**
     * When the user save the summary, we have to write it in DB.
     *
     * @private
     * @param {OdooEvent} event
     */
    _onSaveSummary: function (event) {
        var self = this;
        var text = event.data.text;
        this.model.saveSummary(this.handle, text).then(function (){
            self.renderer.renderSavedSummary(text);
        });
    },
    /**
     * Send the mail server-side.
     *
     * @private
     */
    _onSendMail: function () {
        var self = this;
        this.model.doSendMail(this.handle);
        this.options = {
            partner_id: this._getPartner(),
        };
        this._rpc({
            model: 'account.followup.report',
            method: 'send_email',
            args: [this.options],
        })
        .then(function () {
            self._removeHighlightEmail();
            self._displayDone();
            self.renderer.renderMailAlert();
        });
    },
    /**
     * Send the sms server-side.
     *
     * @override
     * @private
     */
    async _onSendSMS() {
        this.model.doSendSMS(this.handle);
        this.options = {
            partner_id: this._getPartner()
        };
        let action = await this._rpc({
            model: 'account.followup.report',
            method: 'send_sms',
            args: [this.options],
        })
        this.do_action(action, {
            on_close: (infos) => {
                if (!infos) {
                    this._removeHighlightSMS()
                    this._displayDone();
                    this.renderer.renderSMSAlert();
                }
            },
        })
    },
    /**
     * This method creates an action depending on the name and then executes
     * this action.
     *
     * @private
     * @param {OdooEvent} event
     */
    _onTriggerAction: function (event) {
        event.stopPropagation();
        var actionName = event.data.actionName;
        var action = {
            type: 'ir.actions.act_window',
            views: [[false, 'form']],
            target: 'current',
        };
        switch (actionName) {
            case "open_partner_form":
                _.extend(action, {
                    res_model: 'res.partner',
                    res_id: this.model.localData[this.handle].res_id,
                });
                break;
            case "open_invoice":
                _.extend(action, {
                    res_model: 'account.move',
                    res_id: event.data.resId,
                });
                break;
            default:
                action = undefined;
        }
        if (action) {
            this.do_action(action);
        }
    },
});
return FollowupFormController;
});
