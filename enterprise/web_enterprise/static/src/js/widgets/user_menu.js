odoo.define('web_enterprise.UserMenu', function (require) {
"use strict";

/**
 * This file includes the UserMenu widget defined in Community to add or
 * override actions only available in Enterprise.
 */

var config = require('web.config');
var core = require('web.core');
var Dialog = require('web.Dialog');
var UserMenu = require('web.UserMenu');

var _t = core._t;
var QWeb = core.qweb;

UserMenu.include({
    /**
     * @override
     */
    init: function () {
        this._super.apply(this, arguments);
        if (config.device.isMobile) {
            this.className = 'o_user_menu_mobile';
            this.tagName = 'ul';
            this.template = undefined;
        }
    },
    /**
     * @override
     */
    start: function () {
        if (config.device.isMobile) {
            this.$el.append(QWeb.render('UserMenu.Actions'));
        }
        return this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @override
     */
    do_action() {
        return this._super(...arguments)
            .then(resp => {
                core.bus.trigger('close_o_burger_menu');
                return resp;
            });
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @override
     * @private
     */
    _onMenuSupport: function () {
        window.open('https://www.odoo.com/help', '_blank');
    },
});

});
