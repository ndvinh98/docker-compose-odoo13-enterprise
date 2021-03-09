odoo.define('documents.ProgressCard', function (require) {
"use strict";

const core = require('web.core');
const Widget = require('web.Widget');

const _t = core._t;

const ProgressCard = Widget.extend({
    template: 'documents.ProgressCard',

    /**
     * @override
     * @param {Object} params
     * @param {String} params.title
     * @param {String} params.type file mimetype
     */
    init(parent, params) {
        this._super.apply(this, arguments);
        this.title = params.title;
        this.type = params.type;
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
        const $textDivLeft = this.$('.o_documents_progress_text_left');
        const $textDivRight = this.$('.o_documents_progress_text_right');
        if (percent === 100) {
            $textDivLeft.text(_t('Processing...'));
        } else {
            const mbLoaded = Math.round(loaded/1000000);
            const mbTotal = Math.round(total/1000000);
            $textDivLeft.text(_.str.sprintf(_t("Uploading... (%s%%)"), percent));
            $textDivRight.text(_.str.sprintf(_t("(%s/%sMb)"), mbLoaded, mbTotal));
        }
    },
});
return ProgressCard;

});
