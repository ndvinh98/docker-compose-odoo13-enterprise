odoo.define('documents.systray.ActivityMenu', function (require) {
"use strict";

var ActivityMenu = require('mail.systray.ActivityMenu');

const session = require('web.session');

ActivityMenu.include({
    events: _.extend({}, ActivityMenu.prototype.events, {
        'click .o_sys_documents_request': '_onRequestDocument',
    }),

    /**
     * @override
     */
    async willStart() {
        await this._super(...arguments);
        this.hasDocumentUserGroup = await session.user_has_group('documents.group_documents_user');
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {MouseEvent} ev
     */
   _onRequestDocument: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this.do_action('documents.action_request_form');
    },
});
});
