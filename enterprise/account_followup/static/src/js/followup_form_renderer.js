odoo.define('account_followup.FollowupFormRenderer', function (require) {
"use strict";

var core = require('web.core');
var datepicker = require('web.datepicker');
var Dialog = require('web.Dialog');
var dom = require('web.dom');
var FormRenderer = require('web.FormRenderer');
var SystrayMenu = require('web.SystrayMenu');

var QWeb = core.qweb;
var _t = core._t;

var FollowupFormRenderer = FormRenderer.extend({
    events: _.extend({}, FormRenderer.prototype.events, {
        'input .o_account_reports_next_action_date_picker input': '_onReminderDate',
        'change *[name="blocked"]': '_onChangeBlocked',
        'click .o_change_expected_date': '_onChangeExpectedDate',
        'click .o_change_trust': '_onChangeTrust',
        'click .o_account_reports_no_print .o_account_reports_summary': '_onEditSummary',
        'click .js_account_report_save_summary': '_onSaveSummary',
        'click [action]': '_onTriggerAction',
        'click .o_account_reports_contact_info_call': '_onClickCall',
    }),
    /**
     * @override
     */
    init: function () {
        this._super.apply(this, arguments);
        this.nextActionDatePicker = new datepicker.DateWidget(this);
        this.nextActionDatePicker.on('datetime_changed', this, function (){
            this.trigger_up('next_action_date_changed', {
                newDate: this.nextActionDatePicker.getValue()
            });
        });
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Remove the mail alert above the report.
     */
    removeMailAlert: function () {
        if (this.chatter) {
            this.chatter.trigger_up('reload_mail_fields', {
                activity: true,
                thread: true,
                followers: true
            });
        }
        this.$('div.alert.alert-info.alert-dismissible').remove();
    },
    /**
     * Render the summary in 'edit' mode.
     */
    renderEditSummary: function () {
        dom.autoresize(this.$('textarea[name="summary"]'));
        this.$('.o_account_reports_summary_edit').show();
        this.$('.o_account_reports_no_print .o_account_reports_summary').hide();
        this.$('textarea[name="summary"]').focus();
    },
    /**
     * Render an alert to indicate that an email has been sent.
     */
    renderMailAlert: function () {
        this.$('.o_form_sheet_bg div.o_account_reports_page').prepend(QWeb.render("CustomerStatements.send_mail"));
    },
    /**
     * Render an alert to indicate that an sms has been sent.
     */
    renderSMSAlert: function () {
        this.$('div.o_account_reports_page').prepend(QWeb.render("CustomerStatements.send_sms"));
    },
    /**
     * Render the summary in 'non-edit' mode.
     *
     * @param {string} text Summary content
     */
    renderSavedSummary: function (text) {
        this.$('.o_account_reports_summary_edit').hide();
        this.$('.o_account_reports_no_print .o_account_reports_summary').show();
        if (!text) {
            text = "<input type='text' class='o_input o_field_widget' name='summary' />";
        } else {
            text = text.replace(/\n/g, '<br>');
        }
        this.$('.o_account_reports_no_print .o_account_report_summary').html('<span>'+text+'</span');
    },
    /**
     * Render the bullet next to the name of customer according to the trust.
     *
     * @param {string} newTrust The new trust to assign to the partner.
     */
    renderTrust: function (newTrust) {
        var colorMap = {
            good: 'green',
            normal: 'grey',
            bad: 'red',

        };
        var color = colorMap[newTrust];
        this.$('i.oe-account_followup-trust').attr('style', 'color: ' + color + '; font-size: 0.8em;');
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Create JQueryElement which contains the customer statement.
     *
     * @private
     * @returns {jQueryElement} Element rendered
     */
    _renderTagFollowup: function () {
        var self = this;
        var $element = $('<div>');
        $element.html(this.state.data.followup_html);
        $element.find('.o_account_reports_summary_edit').hide();
        this.nextActionDatePicker.appendTo($element.find('div.o_account_reports_next_action_date_picker')).then(function() {
            self.nextActionDatePicker.setValue(new moment(self.state.data.next_action_date));
        });

        return $element;
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * When a move line is blocked or unblocked, trigger an event to the
     * controller to write it in DB and reload the HTML to update the total
     * due and total overdue.
     *
     * @private
     * @param {MouseEvent} event
     */
    _onChangeBlocked: function (event) {
        var checkbox = $(event.target).is(":checked");
        var targetID = $(event.target).parents('tr').find('td[data-id]').data('id');
        this.trigger_up('on_change_block', {
            checkbox: checkbox,
            targetID: targetID
        });
    },
    /**
     * When the user click on 'Change expected date', it opens a dialog
     * to allow the user to choose a new date for an account.move.line.
     *
     * @private
     * @param {MouseEvent} event
     */
    _onChangeExpectedDate: function (event) {
        var self = this;
        var targetID = parseInt($(event.target).attr('data-id'));
        var $content = $(QWeb.render("paymentDateForm", {target_id: targetID}));
        var paymentDatePicker = new datepicker.DateWidget(this);
        paymentDatePicker.appendTo($content.find('div.o_account_reports_payment_date_picker'));
        var save = function () {
            self.trigger_up('expected_date_changed', {
                newDate: paymentDatePicker.getValue(),
                moveLineID: parseInt($content.find("#target_id").val())
            });
        };
        new Dialog(this, {
            title: 'Odoo',
            size: 'medium',
            $content: $content,
            buttons: [{
                text: 'Save',
                classes: 'btn-primary',
                close: true,
                click: save
            },
            {
                text: 'Cancel',
                close: true
            }]
        }).open();
    },
    /**
     * When the trust of a partner is changed, trigger an event to write it in
     * DB.
     *
     * @private
     * @param {MouseEvent} event
     */
    _onChangeTrust: function (event) {
        var newTrust = $(event.target).data("new-trust");
        if (!newTrust) {
            newTrust = $(event.target).parents('a.o_change_trust').data("new-trust");
        }
        this.trigger_up('on_change_trust', {
            newTrust: newTrust
        });
    },
    /**
     * When the user click on phone, trigger an event to make voip call if voip installed.
     *
     * @private
     * @param {MouseEvent} event
     */
    _onClickCall: function (ev) {
        var hasVoip = _.find(SystrayMenu.Items, function (SystrayMenuItem) {
            return SystrayMenuItem.prototype.name === 'voip';
        });
        if (!hasVoip) {
            return;
        }
        ev.preventDefault();
        var $el = $(ev.currentTarget);
        this.do_notify(_t('Start Calling'), _t('Calling') + ' ' + $el.data('number'));
        this.trigger_up('voip_call', {
            resModel: $el.data('model'),
            resId: $el.data('id'),
            number: $el.data('number').toString(),
        });
    },
    /**
     * When the user click on the summary, he can edit it.
     *
     * @private
     */
    _onEditSummary: function () {
        this.renderEditSummary();
    },
    /**
     * When changing the reminder date, change it in db
     *
     * @private
     */
    _onReminderDate: function () {
        this.trigger_up('on_change_reminder_date');
    },
    /**
     * When the user save the summary, trigger an event to the controller to
     * save the new summary.
     *
     * @private
     * @param {MouseEvent} event
     */
    _onSaveSummary: function (event) {
        var text = $(event.target).siblings().val().replace(/[ \t]+/g, ' ');
        this.trigger_up('on_save_summary', {
            text: text
        });
    },
    /**
     * Trigger an event to the controller to execute an action.
     *
     * @private
     * @param {MouseEvent} event
     */
    _onTriggerAction: function (event) {
        event.stopPropagation();
        var actionName = $(event.target).attr('action');
        var resId = parseInt($(event.target).attr('data-id'));
        var view = parseInt($(event.target).attr('view-id'));
        this.trigger_up('on_trigger_action', {
            actionName: actionName,
            resId: resId,
            view: view
        });
    },
});
return FollowupFormRenderer;
});
