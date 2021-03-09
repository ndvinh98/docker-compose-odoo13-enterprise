odoo.define('web_mobile.user_menu', function (require) {
"use strict";

var core = require('web.core');
var UserMenu = require('web.UserMenu');
var web_client = require('web.web_client');

var mobile = require('web_mobile.rpc');

var _t = core._t;

// Hide the logout link in mobile
UserMenu.include({
    /**
     * @override
     */
    start: function () {
        var self = this;
        return this._super.apply(this, arguments).then(function () {
            if (mobile.methods.switchAccount) {
                self.$('a[data-menu="logout"]').addClass('d-none');
                self.$('a[data-menu="account"]').addClass('d-none');
                self.$('a[data-menu="switch"]').removeClass('d-none');
            }
            if (mobile.methods.addHomeShortcut) {
                self.$('a[data-menu="shortcut"]').removeClass('d-none');
            }
        });
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     */
    _onMenuSwitch: function () {
        mobile.methods.switchAccount();
    },
    /**
     * @private
     */
    _onMenuShortcut: function () {
        var urlData = $.bbq.getState();
        if (urlData.menu_id) {
            var menus = web_client.menu_data;
            var menu = _.filter(menus.children, function (child) {
                return child.id === parseInt(urlData.menu_id);
            });
            mobile.methods.addHomeShortcut({
                'title': document.title,
                'shortcut_url': document.URL,
                'web_icon': menu && menu[0].web_icon_data
            });
         } else {
             mobile.methods.showToast({
                 "message": _t("No shortcut for Home Menu")
             });
         }
         },
});

});
