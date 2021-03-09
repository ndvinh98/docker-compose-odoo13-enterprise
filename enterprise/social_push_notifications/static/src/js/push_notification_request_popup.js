odoo.define('social_push_notifications.NotificationRequestPopup', function (require) {
"use strict";

var Widget = require('web.Widget');

/**
 * Simple widget that shows a small popup to request the notifications permission.
 * We use a jQuery 'dropdown' menu so that it automatically closes when clicked outside.
 */
var NotificationRequestPopup = Widget.extend({
    template: 'social_push_notifications.NotificationRequestPopup',
    xmlDependencies: ['/social_push_notifications/static/src/xml/social_push_notifications_templates.xml'],
    events: {
        'click .o_social_push_notifications_permission_allow': '_onClickAllow',
        'click .o_social_push_notifications_permission_deny': '_onClickDeny'
    },

    init: function (parent, options) {
        this._super.apply(this, arguments);

        this.notificationTitle = options.title;
        this.notificationBody = options.body;
        this.notificationDelay = options.delay;
        this.notificationIcon = options.icon;
    },

    /**
     * Will start the timer to display the notification request popup.
     *
     * Also pushes down the notification window if the main menu nav bar is active.
     * (We want to avoid covering the nav bar with the notification window)
     *
     * @override
     */
    start: function () {
        var self = this;

        return this._super.apply().then(function () {
            var $mainNavBar = $('#oe_main_menu_navbar');
            if ($mainNavBar && $mainNavBar.length !== 0){
                self.$el.addClass('o_social_push_notifications_permission_with_menubar');
            }
            setTimeout(self._toggleDropdown.bind(self), self.notificationDelay * 1000);
        });
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    _onClickAllow: function () {
        this.trigger_up('allow');
    },

    _onClickDeny: function () {
        this.trigger_up('deny');
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Will display the notification window by toggling the popup.
     *
     * @private
     */
    _toggleDropdown: function () {
        this.$('.dropdown-toggle').dropdown('toggle');
    }
});

return NotificationRequestPopup;

});
