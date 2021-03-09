odoo.define('documents.DocumentsKanbanControllerMobile', function (require) {
"use strict";

var config = require('web.config');
if (!config.device.isMobile) {
    return;
}

var core = require('web.core');
var DocumentsKanbanController = require('documents.DocumentsKanbanController');

var qweb = core.qweb;

DocumentsKanbanController.include({
    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Group ControlPanel's buttons into a dropdown.
     *
     * @override
     */
    renderButtons: function () {
        this._super.apply(this, arguments);
        var $buttons = this.$buttons.find('button');
        var $dropdownButton = $(qweb.render('documents.ControlPanelButtonsMobile'));
        $buttons.addClass('dropdown-item').appendTo($dropdownButton.find('.dropdown-menu'));
        $dropdownButton.replaceAll(this.$buttons);
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Opens the DocumentsInspector when a record is directly selected.
     *
     * @override
     * @private
     * @param {OdooEvent} ev
     * @param {boolean} ev.data.clear if true, unselect other records
     * @param {string} ev.data.resID the resID of the record updating its status
     */
    _onRecordSelected: function (ev) {
        // don't update the selection if the record is currently the only selected one
        if (!ev.data.clear || this.selectedRecordIDs.length !== 1 || this.selectedRecordIDs[0] !== ev.data.resID) {
            this._super.apply(this, arguments);
        }
        if (ev.data.clear && this.selectedRecordIDs.length === 1) {
            this.documentsInspector.open();
        }
    },
});

});
