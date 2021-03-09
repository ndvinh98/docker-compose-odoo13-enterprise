odoo.define('documents.DocumentsKanbanRenderer', function (require) {
"use strict";

/**
 * This file defines the Renderer for the Documents Kanban view, which is an
 * override of the KanbanRenderer.
 */

var DocumentsKanbanRecord = require('documents.DocumentsKanbanRecord');

var KanbanRenderer = require('web.KanbanRenderer');

var DocumentsKanbanRenderer = KanbanRenderer.extend({
    config: _.extend({}, KanbanRenderer.prototype.config, {
        KanbanRecord: DocumentsKanbanRecord,
    }),

    /**
     * @override
     */
    start: function () {
        this.$el.addClass('o_documents_kanban_view position-relative align-content-start flex-grow-1 flex-shrink-1');
        return this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Marks records as selected
     *
     * @private
     * @param {integer[]} selectedRecordIDs
     */
    updateSelection: function (selectedRecordIDs) {
        _.each(this.widgets, function (widget) {
            var selected = _.contains(selectedRecordIDs, widget.getResID());
            widget.updateSelection(selected);
        });
    },
});

return DocumentsKanbanRenderer;

});
