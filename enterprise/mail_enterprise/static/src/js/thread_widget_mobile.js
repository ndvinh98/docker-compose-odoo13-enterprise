odoo.define('mail_enterprise.widget.Thread', function (require) {

const config = require('web.config');
if (!config.device.isMobile) {
    return;
}
const core = require('web.core');
const ThreadWidget = require('mail.widget.Thread');
const SwipeItemMixin = require('web_enterprise.SwipeItemMixin');
const SnackBar = require('web_enterprise.SnackBar');

const _t = core._t;

ThreadWidget.include(Object.assign({}, SwipeItemMixin, {
    events: Object.assign({}, SwipeItemMixin.events, ThreadWidget.prototype.events),
    init() {
        SwipeItemMixin.init.call(this, {
            actions: {
                right: {
                    classesImage: ['fa-check-circle', 'fa', 'fa-2x', 'text-white'],
                    backgroundClassColor: 'bg-success',
                    allowSwipe: ev => this._allowRightSwipe(ev),
                    actionCallback: (ev, restore) => {
                        const $threadMessageElement = this._getThreadMessageElement(ev);
                        const messageId = $threadMessageElement.data('message-id');
                        if (this._currentThreadID === 'mailbox_inbox' && messageId) {
                            let params = {
                                message: _t('Marked as read'),
                                delay: 3000,
                                onComplete: () => {
                                    this.trigger('mark_as_read', messageId);
                                },
                                actionText: _t('UNDO'),
                                onActionClick: () => {
                                    $threadMessageElement.slideDown('fast');
                                    restore();
                                },
                            };
                            $threadMessageElement.slideUp('fast', () => new SnackBar(this, params).show());
                        }
                    },
                    avoidRestorePositionElement: () => true,
                },
            },
            selectorTarget: '.o_thread_message',
        });
        return this._super(...arguments);
    },
    render(thread, options) {
        options = Object.assign({}, options, {
            displayMarkAsRead: false,
        });
        let renderResult = this._super(thread, options);
        SwipeItemMixin.addClassesToTarget.call(this);
        return renderResult;
    },
    _allowRightSwipe(ev) {
        return this._currentThreadID === 'mailbox_inbox';
    },
    _getThreadMessageElement(ev) {
        return $(ev.currentTarget);
    },
}));

});
