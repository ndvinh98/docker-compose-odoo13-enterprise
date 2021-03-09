odoo.define('mail_push.fcm', function (require) {
"use strict";

var mobile = require('web_mobile.rpc');
var ajax = require('web.ajax');

//Send info only if client is mobile
if (mobile.methods.getFCMKey) {
    var sessionInfo = odoo.session_info;
    var registerDevice = function (fcm_project_id) {
        mobile.methods.getFCMKey({
            project_id: fcm_project_id,
            inbox_action: sessionInfo.inbox_action,
        }).then(function (response) {
            if (response.success) {
                ajax.rpc('/web/dataset/call_kw/res.config.settings/register_device', {
                    model: 'res.config.settings',
                    method: 'register_device',
                    args: [response.data.subscription_id, response.data.device_name],
                    kwargs: {},
                }).then(function (ocn_token) {
                    if (mobile.methods.setOCNToken) {
                        mobile.methods.setOCNToken({ocn_token: ocn_token});
                    }
                });
            }
        });
    };
    if (sessionInfo.fcm_project_id) {
        registerDevice(sessionInfo.fcm_project_id);
    } else {
        ajax.rpc('/web/dataset/call_kw/res.config.settings/get_fcm_project_id', {
            model: 'res.config.settings',
            method: 'get_fcm_project_id',
            args: [],
            kwargs: {},
        }).then(function (response) {
            if (response) {
                registerDevice(response);
            }
        });
    }
}

if (mobile.methods.hashChange) {
    var currentHash;
    $(window).bind('hashchange', function (event) {
        var hash = event.getState();
        if (!_.isEqual(currentHash, hash)) {
            mobile.methods.hashChange(hash);
        }
        currentHash = hash;
    });
}

});
