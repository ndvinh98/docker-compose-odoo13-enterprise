odoo.define('website_studio.SubMenu', function (require) {
"use strict";

var SubMenu = require('web_studio.SubMenu');

var WebsiteSubMenu = SubMenu.include({
    template: 'website_studio.SubMenu',

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Add the event when clicking on the website form menu added in the submenu
     *
     * @override
     * @private
     */
    _onMenu: function (ev) {
        this._super.apply(this, arguments);

        var $menu = $(ev.currentTarget);
        var title = $menu.text();
        if ($menu.data('name') === 'website') {
            this._replaceAction('action_web_studio_form', title, {
                action: this.action,
                replace_last_action: true,
            });
        }
    },
});

return WebsiteSubMenu;

});
