odoo.define('snailmail_account_followup.FollowupFormModel', function (require) {
"use strict";

var FollowupFormModel = require('account_followup.FollowupFormModel');

FollowupFormModel.include({

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Save the fact that the user has decided to send a letter for this record.
     *
     * @param {string} handle Local resource id of a record
     */
    doSendLetter: function (handle) {
        var level = this.localData[handle].data.followup_level;
        if (level && level.send_letter) {
            level.send_letter = false;
        }
    },
});
});
