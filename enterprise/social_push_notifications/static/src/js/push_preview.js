odoo.define('social_push_notifications.social_push_preview', function (require) {
'use strict';

var widgetRegistry = require('web.widget_registry');
var Widget = require('web.Widget');
var core = require('web.core');
var _t = core._t;

/**
 * This widget will trigger a native notification to be able to preview the actual
 * push notifications that will be sent to registered users (website.visitor#push_token).
 */
var PushPreviewButton = Widget.extend({
    tagName: 'button',
    className: 'btn btn-secondary',
    events: {
        'click': '_onClick',
    },

    /**
     *
     * @override
     */
    init: function (parent, record, node) {
        this.record = record;
        this.node = node;
        this._super.apply(this, arguments);
    },

    /**
     * Adds the icon tag inside the button.
     *
     * @override
     */
    start: function () {
        var self = this;
        return this._super.apply(this, arguments).then(function () {
            self.$el.append($('<i/>', {
                class: 'fa fa-fw o_button_icon fa-bell'
            })).append($('<span/>', {
                text: _t('Test Notification')
            }));
        });
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Overrides the click event to display a native notification to the user.
     * This notification will use the data of the current state of the parent form.
     *
     * @param {MouseEvent} ev
     * @private
     */
    _onClick: function (ev) {
        var self = this;

        ev.preventDefault();
        ev.stopPropagation();

        if (Notification.permission === "denied") {
            this.do_warn(
                _t("Notifications blocked"),
                _t("Your browser notifications are blocked or you're not in an HTTPS environment.")
            );
            return;
        }

        var recordState = this.getParent().state.data;
        var message = recordState.message;
        var title = recordState.push_notification_title || _('New Message');
        var image = recordState.push_notification_image;
        var targetUrl = recordState.push_notification_target_url;

        Notification.requestPermission().then(function () {
            if (Notification.permission === "granted") {
                var notification = new Notification(title, {
                    body: message,
                    icon: self._getImageUrl(image)
                });

                notification.onclick = function () {
                    if (targetUrl) {
                        window.open(targetUrl);
                    }
                };
            }
        });
    },

    /**
     * Will try to extract the base64 string from the image.
     *
     * If the string is not a base64, that means the record was already saved and we can use
     * the standard route to recover the image.
     *
     * If the image has not been set, will use the default fallback (odoobot image).
     *
     * @param {string} recordImage base64 image or size if record already saved
     */
    _getImageUrl(recordImage) {
        if (recordImage) {
            try {
                window.atob(recordImage);
                return 'data:image/png;base64, ' + recordImage;
            } catch (e) {
                return '/web/image/social.post/' + this.record.data.id + '/push_notification_image';
            }
        }

        return '/mail/static/src/img/odoobot_transparent.png';
    }
});

widgetRegistry.add('social_push_preview', PushPreviewButton);

return PushPreviewButton;

});
