odoo.define('website.home_menu', function (require) {
    'use strict';

    var session = require('web.session');
    var websiteNavbarData = require('website.navbar');

    websiteNavbarData.WebsiteNavbar.include({
        events: _.extend({}, websiteNavbarData.WebsiteNavbar.prototype.events || {}, {
            'click .o_menu_toggle': '_onMenuToggleClick',
        }),

        //----------------------------------------------------------------------
        // Handlers
        //----------------------------------------------------------------------

        /**
         * Called when the menu toggle is clicked -> redirects to backend
         *
         * @private
         * @param {Event} ev
         */
        _onMenuToggleClick: function (ev) {
            ev.preventDefault();

            // We add a spinner for the user to understand the loading.
            var $button = $(ev.currentTarget);
            if (!$button.hasClass('fa')) {
                return;
            }
            $button.removeClass('fa fa-th').append($('<span/>', {'class': 'fa fa-spin fa-spinner'}));
            var url = '/web#home';
            window.location.href = url;
        },
    });
});
