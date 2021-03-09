odoo.define('mrp.embed_viewer_no_reload', function (require) {
"use strict";

var fieldRegistry = require('web.field_registry');
var mrpViewerCommon = require('mrp.viewer_common');


var FieldEmbedURLViewer = require('mrp.mrp_state');

/**
 * /!\/!\/!\ WARNING /!\/!\/!\
 * Do not use this widget else where
 * Due to limitation of the framework, a lot of hacks have been used
 *
 * Override of the default Embed URL Viewer Widget to prevent reload of the iFrame content
 * on any action (typically, click on a button)
 */

var FieldEmbedURLViewerNoReload = FieldEmbedURLViewer.extend(mrpViewerCommon, {
    /**
     * Do not start the widget in the normal lifecycle
     * The first start will be called in the on_attach_callback
     * After that, this start will just update the active page
     *
     * @override
     */
    start: function () {
        this._superStart = this._super;
        var $existing = $('#' + this.iFrameId);
        if ($existing.length) {
            var src = this._getEmbedSrc();
            var $iframe = $existing.find('iframe');
            // To manage page url
            if (!this.invisible && $iframe.attr('src') !== src) {
                $existing.find('iframe').attr('src', src);
            }
            $existing.toggleClass('o_invisible_modifier', this.invisible);
        }

        this._fixFormHeight();

        return Promise.resolve();
    }
});
fieldRegistry.add('mrp_embed_viewer_no_reload', FieldEmbedURLViewerNoReload);

return FieldEmbedURLViewerNoReload;
});
