odoo.define('documents.DocumentsKanbanRecord', function (require) {
"use strict";

/**
 * This file defines the KanbanRecord for the Documents Kanban view.
 */

var KanbanRecord = require('web.KanbanRecord');

var DocumentsKanbanRecord = KanbanRecord.extend({
    events: _.extend({}, KanbanRecord.prototype.events, {
        'click': '_onSelectRecord',
        'click .o_record_selector': '_onAddRecordToSelection',
        'click .oe_kanban_previewer': '_onImageClicked',
        'click .o_request_image': '_onRequestImage',
    }),

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @returns {integer} resID of the record
     */
    getResID: function () {
        return this.id;
    },
    /**
     * When the record is updated and re-rendered, it loses its 'selected'
     * status (when a button in the kanban record is clicked, for example), so
     * here we ensure that it is kept if necessary.
     *
     * @override
     */
    update: function () {
        var self = this;
        var isSelected = this.$el.hasClass('o_record_selected');
        return this._super.apply(this, arguments).then(function () {
            if (isSelected) {
                self.$el.addClass('o_record_selected');
            }
        });
    },
    /**
     * @param {boolean} selected
     */
    updateSelection: function (selected) {
        this.$el.toggleClass('o_record_selected', selected);
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {boolean} clear if true, will ask to unselect other records
     * @param {jQueryEvent} ev
     */
    _toggleSelect: function (clear, ev) {
        this.trigger_up('select_record', {
            clear: clear,
            originalEvent: ev,
            resID: this.getResID(),
            selected: !this.$el.hasClass('o_record_selected'),
        });
    },
    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Toggle the selected status of the record
     *
     * @private
     * @param {MouseEvent} ev
     */
    _onAddRecordToSelection: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this._toggleSelect(false, ev);
    },
    /**
     * @private
     * @param {MouseEvent} ev
     */
    _onImageClicked: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this.trigger_up('kanban_image_clicked', {
            recordList: [this.recordData],
            recordID: this.recordData.id
        });
    },
    /**
     * Overrides to force the select/unselect as default action (instead of
     * opening the first link of the record)
     *
     * @override
     * @private
     */
    _onKeyDownOpenFirstLink: function (ev) {
        switch (ev.keyCode) {
            case $.ui.keyCode.ENTER:
                this._toggleSelect(true, ev);
                break;
        }
    },
    /**
     * @private
     *
     */
    _onRequestImage: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this.trigger_up('replace_file', {id: this.id});
    },
    /**
     * Toggle the selected status of the record (and unselect all other records)
     *
     * @private
     * @param {MouseEvent} ev
     */
    _onSelectRecord: function (ev) {
        ev.preventDefault();
        // ignore clicks on oe_kanban_action elements
        if (!$(ev.target).hasClass('oe_kanban_action')) {
            this._toggleSelect(true, ev);
        }
    },
});

return DocumentsKanbanRecord;

});
