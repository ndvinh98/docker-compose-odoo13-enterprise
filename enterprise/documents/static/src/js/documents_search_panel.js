odoo.define('documents.DocumentsSearchPanel', function (require) {
"use strict";

/**
 * This file defines the DocumentsSearchPanel widget, an extension of the
 * SearchPanel to be used in the documents kanban view.
 */

const core = require('web.core');
const SearchPanel = require('web.SearchPanel');

const _t = core._t;

const DocumentsSearchPanel = SearchPanel.extend({

    events: Object.assign({}, SearchPanel.prototype.events, {
        'dragenter .o_search_panel_category_value, .o_search_panel_filter_value': '_onDragEnter',
        'dragleave .o_search_panel_category_value, .o_search_panel_filter_value': '_onDragLeave',
        'dragover .o_search_panel_category_value, .o_search_panel_filter_value': '_onDragOver',
        'drop .o_search_panel_category_value, .o_search_panel_filter_value': '_onRecordDrop',
    }),

    /**
     * @override
     */
    init: function () {
        this._super.apply(this, arguments);
        this.uploadingFolderIDs = [];
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Returns a description of each folder (record of documents.folder).
     *
     * @returns {Object[]}
     */
    getFolders: function () {
        var category = _.findWhere(this.categories, {fieldName: 'folder_id'});
        return Object.keys(category.values).map(function (folderId) {
            return category.values[folderId];
        });
    },
    /**
     * Returns the id of the current selected folder, if any, false otherwise.
     *
     * @returns {integer|false}
     */
    getSelectedFolderId: function () {
        var category = _.findWhere(this.categories, {fieldName: 'folder_id'});
        return category.activeValueId;
    },
    /**
     * Returns ids of selected tags.
     *
     * @returns {integer[]}
     */
    getSelectedTagIds: function () {
        var filter = _.findWhere(this.filters, {fieldName: 'tag_ids'});
        return Object.keys(filter.values).filter(function (tagId) {
            return filter.values[tagId].checked;
        });
    },
    /**
     * Returns a description of each tag (record of documents.tag).
     *
     * @returns {Object[]}
     */
    getTags: function () {
        var filter = _.findWhere(this.filters, {fieldName: 'tag_ids'});
        return Object.keys(filter.values).map(tagId => filter.values[tagId]).sort((a, b) => {
            if (a.group_sequence === b.group_sequence) {
                return a.sequence - b.sequence;
            } else {
                return a.group_sequence - b.group_sequence;
            }
        });
    },
    /**
     * set the list of currently uploading folders.
     *
     * @param {Array<integer>} uploadingFolderIDs the list of folders in which uploads are currently happening.
     */
    setUploadingFolderIDs: function (uploadingFolderIDs) {
        this.uploadingFolderIDs = uploadingFolderIDs;
        this._render();
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Adds a spinner next to the folders in which a file is being uploaded.
     *
     * @private
     */
    _renderLoadingSpinners: function () {
        const $folderSection = this.$('[data-field-name="folder_id"]');
        $folderSection.find('.o_search_panel_spinner').remove();
        $folderSection.find('.o_search_panel_category_value').each((i, el) => {
            if (this.uploadingFolderIDs.includes(+el.getAttribute("data-id"))) {
                const $spinner = $('<span>', {
                    class: 'fa fa-spinner fa-spin o_search_panel_spinner',
                });
                $spinner.appendTo($(el).find('> header > label'));
            }
        });
    },
    /**
     * Override to select the first value instead of 'All' by default.
     *
     * @override
     * @private
     */
    _getCategoryDefaultValue: function (category, validValues) {
        var value = this._super.apply(this, arguments);
        return _.contains(validValues, value) ? value : validValues[0];
    },
    /**
     * @private
     * @param {jQueryElement} $target
     * @returns {boolean}
     */
    _isValidDropZone($target) {
        const fieldName = $target.closest('.o_search_panel_field').data('field-name');
        const hasRightFieldName = ['folder_id', 'tag_ids'].includes(fieldName);
        const hasID = $target.data('id') || $target.data('value-id');
        return hasRightFieldName && hasID;
    },
    /**
     * @private
     * @override
     */
    _render: function () {
        this._super.apply(this, arguments);
        this._renderLoadingSpinners();
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {DragEvent} ev
     */
    _onDragEnter(ev) {
        if (
            !this._isValidDropZone($(ev.currentTarget)) ||
            !ev.originalEvent.dataTransfer.types.includes('o_documents_data')
        ) {
            return;
        }
        ev.stopPropagation();
        ev.preventDefault();
        const $item = $(ev.currentTarget).closest('.o_search_panel_category_value');
        const category = this.categories[$item.data('categoryId')];
        const valueId = $item.data('id');
        if (category && category.values[valueId].folded) {
            category.values[valueId].folded = false;
            // if the hovered folder has children, opens it and re renders the search panel
            // to allow drops in its children.
            this._render();
        }
        this.$('.o_drag_over_selector').removeClass('o_drag_over_selector');
        $(ev.currentTarget).addClass('o_drag_over_selector');
    },
    /**
     * @private
     * @param {DragEvent} ev
     */
    _onDragLeave(ev) {
        const target = document.elementFromPoint(ev.originalEvent.clientX, ev.originalEvent.clientY);
        if (
            !this._isValidDropZone($(ev.currentTarget)) ||
            $.contains(ev.currentTarget, target) || // prevents drag zone flickering.
            !ev.originalEvent.dataTransfer.types.includes('o_documents_data')
        ) {
            return;
        }
        ev.stopPropagation();
        ev.preventDefault();
        this.$('.o_drag_over_selector').removeClass('o_drag_over_selector');
    },
    /**
     * @private
     * @param {DragEvent} ev
     */
    _onDragOver(ev) {
        if (
            this._isValidDropZone($(ev.currentTarget)) &&
            ev.originalEvent.dataTransfer.types.includes('o_documents_data')
        ) {
            ev.preventDefault();
        }
    },
    /**
     * Allows the selected kanban cards to be dropped in folders (workspaces) or tags.
     *
     * @private
     * @param {DragEvent} ev
     */
    _onRecordDrop: function (ev) {
        ev.stopPropagation();
        ev.preventDefault();
        var $item = $(ev.currentTarget);
        $item.removeClass('o_drag_over_selector');
        const fieldName = $item.closest('.o_search_panel_field').data('field-name');
        const panelRecordID = $item.data('id') || $item.data('value-id');
        const dataTransfer = ev.originalEvent.dataTransfer;
        if (
            !this._isValidDropZone($item) ||
            !panelRecordID ||
            !dataTransfer ||
            !dataTransfer.types.includes('o_documents_data') ||
            $item.find('> .active').length // prevents dropping in the current folder
        ) {
            return;
        }

        const data = JSON.parse(dataTransfer.getData("o_documents_data"));
        if (data.lockedCount) {
            this.do_notify(
                "Partial transfer",
                _.str.sprintf(_t('%s file(s) not moved because they are locked by another user'), data.lockedCount)
            );
        }

        const vals = fieldName === 'tag_ids' ? { tag_ids: [[4, panelRecordID]] } : { folder_id: panelRecordID };

        this._rpc({
            model: 'documents.document',
            method: 'write',
            args: [data.recordIDs, vals],
        }).then(() => this._notifyDomainUpdated());
    },
});

return DocumentsSearchPanel;

});
