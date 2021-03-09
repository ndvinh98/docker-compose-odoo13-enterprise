odoo.define('planning.PlanningGanttController', function (require) {
'use strict';

var GanttController = require('web_gantt.GanttController');
var core = require('web.core');
var _t = core._t;
var confirmDialog = require('web.Dialog').confirm;
var dialogs = require('web.view_dialogs');

var QWeb = core.qweb;
var PlanningGanttController = GanttController.extend({
    events: _.extend({}, GanttController.prototype.events, {
        'click .o_gantt_button_copy_previous_week': '_onCopyWeekClicked',
        'click .o_gantt_button_send_all': '_onSendAllClicked',
    }),

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @override
     * @param {jQueryElement} $node to which the buttons will be appended
     */
    renderButtons: function ($node) {
        if ($node) {
            var state = this.model.get();
            this.$buttons = $(QWeb.render('PlanningGanttView.buttons', {
                groupedBy: state.groupedBy,
                widget: this,
                SCALES: this.SCALES,
                activateScale: state.scale,
                allowedScales: this.allowedScales,
                activeActions: this.activeActions,
            }));
            this.$buttons.appendTo($node);
        }
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Opens dialog to add/edit/view a record
     * Override required to execute the reload of the gantt view when an action is performed on a
     * single record.
     *
     * @private
     * @param {integer|undefined} resID
     * @param {Object|undefined} context
     */
    _openDialog: function (resID, context) {
        var self = this;
        var record = resID ? _.findWhere(this.model.get().records, {id: resID,}) : {};
        var title = resID ? record.display_name : _t("Open");

        var dialog = new dialogs.FormViewDialog(this, {
            title: _.str.sprintf(title),
            res_model: this.modelName,
            view_id: this.dialogViews[0][0],
            res_id: resID,
            readonly: !this.is_action_enabled('edit'),
            deletable: this.is_action_enabled('edit') && resID,
            context: _.extend({}, this.context, context),
            on_saved: this.reload.bind(this, {}),
            on_remove: this._onDialogRemove.bind(this, resID),
        });
        dialog.on('closed', this, function(ev){
            // we reload as record can be created or modified (sent, unpublished, ...)
            self.reload();
        });

        return dialog.open();
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {MouseEvent} ev
     */
    _onCopyWeekClicked: function (ev) {
        ev.preventDefault();
        var state = this.model.get();
        var self = this;
        self._rpc({
            model: self.modelName,
            method: 'action_copy_previous_week',
            args: [
                self.model.convertToServerTime(state.startDate),
            ],
            context: _.extend({}, self.context || {}),
        })
        .then(function(){
            self.reload();
        });
    },
    /**
     * @private
     * @param {MouseEvent} ev
     */
    _onSendAllClicked: function (ev) {
        ev.preventDefault();
        var self = this;
        var state = this.model.get();
        var additional_context = _.extend({}, this.context, {
           'default_start_datetime': this.model.convertToServerTime(state.startDate),
           'default_end_datetime': this.model.convertToServerTime(state.stopDate),
           'scale': state.scale,
           'active_domain': this.model.domain,
           'active_ids': this.model.get().records
        });
        return this.do_action('planning.planning_send_action', {
            additional_context: additional_context,
            on_close: function () {
                self.reload();
            }
        });
    },
    /**
     * @private
     * @override
     * @param {MouseEvent} ev
     */
    _onScaleClicked: function (ev) {
        this._super.apply(this, arguments);
        var $button = $(ev.currentTarget);
        var scale = $button.data('value');
        if (scale !== 'week') {
            this.$('.o_gantt_button_copy_previous_week').hide();
        } else {
            this.$('.o_gantt_button_copy_previous_week').show();
        }
    },
});

return PlanningGanttController;

});
