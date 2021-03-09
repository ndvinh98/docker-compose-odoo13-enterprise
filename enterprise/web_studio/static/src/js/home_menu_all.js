odoo.define('web_studio.HomeMenuAll', function (require) {
"use strict";

var session = require('web.session');
var WebClient = require('web.WebClient');
var HomeMenu = require('web_enterprise.HomeMenu');

/*
 * Notice:
 *  some features (like seeing the home menu background) are available
 *  even the user is not a system user, this is why there are two different
 *  includes in Studio for this module.
 */

HomeMenu.include({
    /**
     * @override
     */
    start: function () {
        this._setBackgroundImage();
        return this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @override
     * @param {Object} menuData
     * @param {boolean} [menuData.background_image]
     */
    _processMenuData: function (menuData) {
        this._hasCustomBackground = menuData.background_image;
        return this._super.apply(this, arguments);
    },
    /**
     * Put the home menu background as the cover of current `$el`.
     *
     * @private
     */
    _setBackgroundImage: function () {
        if (this._hasCustomBackground) {
            var url = session.url('/web/image', {
                model: 'res.company',
                id: session.user_context.allowed_company_ids[0],
                field: 'background_image',
            });
            this.$el.css({
                "background-image": "url(" + url + ")",
                "background-size": "cover",
            });
        }
    },
});

WebClient.include({
    /**
     * Adds a class on the webclient on top of the o_home_menu_background
     * class to inform that the home menu is customized.
     *
     * @override
     */
    toggle_home_menu: function (display) {
        this._super.apply(this, arguments);
        this.$el.toggleClass('o_home_menu_background_custom', display && !!this.menu_data.background_image);
    },
});

});
