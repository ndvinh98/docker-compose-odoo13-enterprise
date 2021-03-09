odoo.define('mail.thread_window_mobile_tests', function (require) {
"use strict";

const mobile = require('web_mobile.rpc');
const mailTestUtils = require('mail.testUtils');
const { createParent, dom, nextTick, mock } = require('web.test_utils');
const Widget = require('web.Widget');

QUnit.module('mail', {}, function () {

QUnit.module('Discuss in mobile', {
    beforeEach() {
        this.data = {
            'mail.channel': {
                fields: {
                    name: {
                        string: "Name",
                        type: "char",
                        required: true,
                    },
                    channel_type: {
                        string: "Channel Type",
                        type: "selection",
                    },
                    channel_message_ids: {
                        string: "Messages",
                        type: "many2many",
                        relation: 'mail.message'
                    },
                    message_unread_counter: {
                        string: "Amount of Unread Messages",
                        type: "integer"
                    },
                },
                records: [],
            },
            'mail.message': {
                fields: {},
                records: [],
            },
            'initMessaging': {
                channel_slots: {
                    channel_channel: [{
                        id: 1,
                        channel_type: "channel",
                        name: "general",
                    }],
                },
            },
        };
        this.services = mailTestUtils.getMailServices();
        this.createParent = (params) => {
            const widget = new Widget();

            // in non-debug mode, append thread windows in qunit-fixture
            // note that it does not hide thread window because it uses fixed
            // position, and qunit-fixture uses absolute...
            if (params.debug) {
                this.services.mail_service.prototype.THREAD_WINDOW_APPENDTO = 'body';
            } else {
                this.services.mail_service.prototype.THREAD_WINDOW_APPENDTO = '#qunit-fixture';
            }

            mock.addMockEnvironment(widget, params);
            return widget;
        };
    },
    afterEach() {
        // reset thread window append to body
        this.services.mail_service.prototype.THREAD_WINDOW_APPENDTO = 'body';
    },
});

QUnit.test('close thread window using backbutton event', async function (assert) {
    assert.expect(5);

    const __overrideBackButton = mobile.methods.overrideBackButton;
    mobile.methods.overrideBackButton = function () {};

    const parent = createParent({
        data: this.data,
        services: this.services,
        mockRPC(route, args) {
            if (args.method === 'channel_fold') {
                assert.step('channel_fold');
            }
            return this._super.apply(this, arguments);
        },
    });
    await nextTick();

    // get channel instance to link to thread window
    const channel = parent.call('mail_service', 'getChannel', 1);
    await nextTick();
    assert.ok(channel, "there should exist a channel locally with ID 1");

    channel.detach();
    await nextTick();
    assert.containsOnce($('body'), '.o_thread_window',
        "there should be a thread window");
    assert.isVisible($('.o_thread_window'),
        "there should be an opened thread window");

    const backButtonEvent = new Event('backbutton');

    // simulate 'backbutton' event triggered by the app
    document.dispatchEvent(backButtonEvent);
    // waiting nextTick to match testUtils.dom.triggerEvents() behavior
    await nextTick();
    assert.containsNone($('body'), '.o_thread_window',
        "the thread window should be closed");
    // shoudn't call channel_fold to update the state on the server
    assert.verifySteps([]);

    parent.destroy();
    mobile.methods.overrideBackButton = __overrideBackButton;
});

QUnit.test('do not automatically open chat window', async function (assert) {
    assert.expect(4);

    this.data['mail.channel'].records = [{
        id: 2,
        name: "DM",
        channel_type: "chat",
        message_unread_counter: 1,
        direct_partner: [{ id: 666, name: 'DemoUser1', im_status: '' }],
        is_minimized: false,
        state: 'open',
    }];

    const parent = this.createParent({
        data: this.data,
        services: this.services,
        session: { partner_id: 3 },
        async mockRPC(route, args) {
            if (args.method === 'channel_join_and_get_info') {
                this.data['mail.channel'].records[0].is_minimized = true;
                return Object.assign({ info: 'join' }, this.data['mail.channel'].records[0]);
            }
            if (args.method === 'channel_seen') {
                assert.step('channel_seen');
            }
            return this._super(...arguments);
        }
    });

    assert.containsNone($, '.o_thread_window',
        "shouldn't have any DM window open at first load");

    // simulate receiving new message form new DM
    const messageData = {
        author_id: [5, "Someone else"],
        body: "<p>Test message</p>",
        id: 2,
        model: 'mail.channel',
        res_id: 2,
        channel_ids: [2],
    };
    this.data['mail.message'].records.push(messageData);
    let notification = [[false, 'mail.channel', 2], messageData];
    parent.call('bus_service', 'trigger', 'notification', [notification]);
    await nextTick();
    assert.containsNone($, '.o_thread_window',
        "shouldn't have any DM window open after receiving it");
    assert.verifySteps([]); //should not mark channel as seen

    // simulate receiving notification (cross-tab synchronization)
    // open the chat window on a desktop tab.
    const dmInfo = Object.assign({}, this.data['mail.channel'].records[0], {
        is_minimized: true,
        state: 'open',
    });
    notification = [[false, 'res.partner', 3], dmInfo];
    parent.call('bus_service', 'trigger', 'notification', [notification]);
    await nextTick();
    assert.containsNone($, '.o_thread_window',
        "shouldn't have any DM window after openning it on a desktop browser");

    parent.destroy();
});

QUnit.test('do not automatically open chat window at first load', async function (assert) {
    assert.expect(1);

    // simulate existing detached chat window
    this.data.initMessaging.channel_slots.channel_dm = [{
        channel_type: 'chat',
        direct_partner: [{ id: 1, name: 'DemoUser1', im_status: '' }],
        id: 50,
        is_minimized: true,
        name: 'DemoUser1',
    }];
    this.data['res.partner'] = {
        fields: {},
        records: [],
    };
    const parent = this.createParent({
        data: this.data,
        services: this.services,
    });
    await nextTick();
    assert.containsNone($, '.o_thread_window',
        "shouldn't have any DM window open at first load");

    parent.destroy();
});

QUnit.test('do not notify the server on open/close thread window', async function (assert) {
    assert.expect(3);

    const parent = this.createParent({
        data: this.data,
        services: this.services,
        async mockRPC(route, args) {
            if (args.method === 'channel_fold') {
                assert.notOk(true, "should not call channel_fold");
                return;
            }
            if (args.method === 'channel_minimize') {
                assert.notOk(true, "should not call channel_minimize");
                return;
            }
            return this._super(...arguments);
        },
    });
    await nextTick();
    // get channel instance to link to thread window
    const channel = parent.call('mail_service', 'getChannel', 1);
    await nextTick();
    assert.ok(channel, "there should exist a channel locally with ID 1");

    channel.detach();
    await nextTick();
    assert.containsOnce($, '.o_thread_window',
        "there should be a thread window that is opened");

    await dom.click($('.o_thread_window .o_thread_window_close'));
    assert.containsNone($, '.o_thread_window',
        "the thread window should be closed");

    parent.destroy();
});

});
});
