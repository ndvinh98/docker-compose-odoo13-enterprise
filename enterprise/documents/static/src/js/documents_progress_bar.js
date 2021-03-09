odoo.define('documents.ProgressBar', function (require) {
"use strict";

const Dialog = require('web.Dialog');
const core = require('web.core');
const Widget = require('web.Widget');

const _t = core._t;

const ProgressBar = Widget.extend({
    template: 'documents.ProgressBar',

    events: {
        'click .o_upload_cross': '_onCrossClick',
    },

    /**
     * @override
     * @param {Object} params
     * @param {String} params.title
     * @param {String} params.uploadID
     * @param {XMLHttpRequest} params.xhr
     */
    init(parent, params) {
        this._super.apply(this, arguments);
        this.title = params.title;
        this.uploadID = params.uploadID;
        this.xhr = params.xhr;
    },

    /**
     * @override
     * @return {Promise}
     */
    start() {
        this.xhr.onabort = () => {
            this.do_notify(_t("Upload cancelled"));
        };
        return this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @param {integer} loaded
     * @param {integer} total
     */
    update(loaded, total) {
        if (!this.$el) {
            return;
        }
        const percent = Math.round((loaded / total) * 100);
        this.$('.o_documents_progress_bar').css("width", percent + "%");
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {MouseEvent} ev
     */
    _onCrossClick(ev) {
        ev.stopPropagation();
        const promptText = _.str.sprintf(_t("Do you really want to cancel the upload of %s?"), _.escape(this.title));
        Dialog.confirm(this, promptText, {
            confirm_callback: () => {
                this.xhr.abort();
                this.trigger_up('progress_bar_abort', {uploadID: this.uploadID});
            }
        });
    },
});
return ProgressBar;

});
