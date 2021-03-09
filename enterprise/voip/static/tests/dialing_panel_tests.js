odoo.define('voip.tests_panel', function (require) {
"use strict";

const mailTestUtils = require('mail.testUtils');

const DialingPanel = require('voip.DialingPanel');
const UserAgent = require('voip.UserAgent');

const testUtils = require('web.test_utils');

/**
 * Create a dialing Panel and attach it to a parent. Uses params to create the parent
 * and to define if mode debug is set
 *
 * @param {Object} params
 * @return {Promise<Object>} resolve with object: { dialingPanel, parent }
 */
async function createDialingPanel(params) {
    const parent = testUtils.createParent(params);
    const dialingPanel = new DialingPanel(parent);
    const container = params.debug ? $('body') : $('#qunit-fixture');
    await dialingPanel.appendTo(container);
    dialingPanel._onToggleDisplay(); // show panel
    await dialingPanel._refreshPhoneCallsStatus();
    await testUtils.nextTick();
    return {
        dialingPanel,
        parent
    };
}

QUnit.module('voip', {}, function () {
QUnit.module('DialingPanel', {
    beforeEach() {
        this.onaccepted = undefined;
        this.services = mailTestUtils.getMailServices();
        this.recentList = {};
        // generate 3 records
        this.phoneCallDetailsData = [10,23,42].map(id => {
            return {
                activity_id: 50+id,
                activity_model_name: "A model",
                activity_note: false,
                activity_res_id: 200+id,
                activity_res_model: 'res.model',
                activity_summary: false,
                date_deadline: "2018-10-26",
                id,
                mobile: false,
                name: `Record ${id}`,
                note: false,
                partner_email: `partner ${100+id} @example.com`,
                partner_id: 100+id,
                partner_image_128: '',
                partner_name: `Partner ${100+id}`,
                phone: "(215)-379-4865",
                state: 'open',
             };
        });
        testUtils.mock.patch(UserAgent, {
            /**
             * Do not play() on media, to prevent "NotAllowedError". This may
             * be triggered if no DOM manipulation is detected before playing
             * the media (chrome policy to prevent from autoplaying)
             *
             * @override
             */
            PLAY_MEDIA: false,
            /**
             * Register callback to avoid the timeout that will accept the call
             * after 3 seconds in demo mode
             *
             * @override
             * @private
             * @param {function} func
             */
            _demoTimeout: func => {
                this.onaccepted = func;
            }
        });
    },
    afterEach() {
        testUtils.mock.unpatch(UserAgent);
    }
}, function () {

QUnit.test('autocall flow', async function (assert) {
    assert.expect(34);

    const self = this;
    let counterNextActivities = 0;

    const {
        dialingPanel,
        parent,
    } = await createDialingPanel({
        async mockRPC(route, args) {
            if (args.method === 'get_pbx_config') {
                return { mode: 'demo' };
            }
            if (args.model === 'voip.phonecall') {
                if (args.method === 'get_next_activities_list') {
                    counterNextActivities++;
                    return self.phoneCallDetailsData.filter(phoneCallDetailData =>
                        ['done', 'cancel'].indexOf(phoneCallDetailData.state) === -1);
                }
                if (args.method === 'get_recent_list') {
                    return self.phoneCallDetailsData.filter(phoneCallDetailData =>
                        phoneCallDetailData.state === 'open');
                }
                const id = args.args[0];
                if (args.method === 'init_call') {
                    assert.step('init_call');
                    return [];
                }
                if (args.method === 'hangup_call') {
                    if (args.kwargs.done) {
                        for (const phoneCallDetailData of self.phoneCallDetailsData) {
                            if (phoneCallDetailData.id === id) {
                                phoneCallDetailData.state = 'done';
                            }
                        }
                    }
                    assert.step('hangup_call');
                    return [];
                }
                if (args.method === 'create_from_rejected_call') {
                    for (const phoneCallDetailData of self.phoneCallDetailsData) {
                        if (phoneCallDetailData.id === id) {
                            phoneCallDetailData.state = 'pending';
                        }
                    }
                    assert.step('rejected_call');
                    return [];
                }
                if (args.method === 'canceled_call') {
                    for (const phoneCallDetailData of self.phoneCallDetailsData) {
                        if (phoneCallDetailData.id === id) {
                            phoneCallDetailData.state = 'pending';
                        }
                    }
                    assert.step('canceled_call');
                    return [];
                }
                if (args.method === 'remove_from_queue') {
                    for (const phoneCallDetailData of self.phoneCallDetailsData) {
                        if (phoneCallDetailData.id === id) {
                            phoneCallDetailData.state = 'cancel';
                        }
                    }
                    assert.step('remove_from_queue');
                    return [];
                }
                if (args.method === 'create_from_incoming_call') {
                    assert.step('incoming_call');
                    return [];
                }
                if (args.method === 'create_from_incoming_call_accepted') {
                    assert.step('incoming_call_accepted');
                    return [];
                }
                if (args.method === 'create_from_incoming_call') {
                    assert.step('incoming_call');
                    return [];
                }
                if (args.method === 'create_from_incoming_call_accepted') {
                    assert.step('incoming_call_accepted');
                    return [];
                }
                if (args.method === 'create_from_incoming_call') {
                    assert.step('incoming_call');
                    return [];
                }
                if (args.method === 'create_from_incoming_call_accepted') {
                    assert.step('incoming_call_accepted');
                    return [];
                }
            }
            return this._super(...arguments);
        },
        services: this.services,
    });

    // make a first call
    assert.containsNone(
        dialingPanel,
        '.o_phonecall_details',
        "Details should not be visible yet");
    assert.containsN(
        dialingPanel, `
            .o_dial_next_activities
            .o_dial_phonecalls
            .o_dial_phonecall`,
        3,
        "Next activities tab should have 3 phonecalls at the beginning");

    // select first call with autocall
    await testUtils.dom.click(dialingPanel.$('.o_dial_call_button'));
    assert.isVisible(
        dialingPanel.$('.o_phonecall_details'),
        "Details should have been shown");
    assert.strictEqual(
        dialingPanel
            .$(`
                .o_phonecall_details
                .o_dial_phonecall_partner_name
                span`)
            .html(),
        'Partner 110',
        "Details should have been shown");

    // start call
    await testUtils.dom.click(dialingPanel.$('.o_dial_call_button'));
    assert.isVisible(
        dialingPanel
            .$('.o_phonecall_in_call')
            .first(),
        "in call info should be displayed");
    assert.ok(dialingPanel._isInCall);

    // simulate end of setTimeout in demo mode or answer in prod
    this.onaccepted();
    // end call
    await testUtils.dom.click(dialingPanel.$('.o_dial_hangup_button'));
    assert.notOk(dialingPanel._isInCall);
    assert.strictEqual(
        dialingPanel
            .$(`
                .o_phonecall_details
                .o_dial_phonecall_partner_name
                span`)
            .html(),
        'Partner 123',
        "Phonecall of second partner should have been displayed");

    // close details
    await testUtils.dom.click(dialingPanel.$('.o_phonecall_details_close'));
    assert.containsN(
        dialingPanel, `
            .o_dial_next_activities
            .o_dial_phonecall`,
        2,
        "Next activities tab should have 2 phonecalls after first call");

    // hangup before accept call
    // select first call with autocall
    await testUtils.dom.click(dialingPanel.$('.o_dial_call_button'));
    assert.strictEqual(
        dialingPanel
            .$(`
                .o_phonecall_details
                .o_dial_phonecall_partner_name
                span`)
            .html(),
        'Partner 123',
        "Phonecall of second partner should have been displayed");

    // start call
    await testUtils.dom.click(dialingPanel.$('.o_dial_call_button'));
    assert.isVisible(
        dialingPanel
            .$('.o_phonecall_in_call')
            .first(),
        "in call info should be displayed");

    // hangup before accept
    await testUtils.dom.click(dialingPanel.$('.o_dial_hangup_button'));
    // we won't accept this call, better clean the current onaccepted
    this.onaccepted = undefined;
    // close details
    await testUtils.dom.click(dialingPanel.$('.o_phonecall_details_close'));

    assert.containsN(
        dialingPanel, `
            .o_dial_next_activities
            .o_dial_phonecall`,
        2,
        "No call should have been removed");

    // end list
    // select first call with autocall
    await testUtils.dom.click(dialingPanel.$('.o_dial_call_button'));
    assert.strictEqual(
        dialingPanel
            .$(`
                .o_phonecall_details
                .o_dial_phonecall_partner_name
                span`)
            .html(),
        'Partner 142',
        "Phonecall of third partner should have been displayed (second one has already been tried)");

    // start call
    await testUtils.dom.click(dialingPanel.$('.o_dial_call_button'));
    // simulate end of setTimeout in demo mode or answer in prod
    this.onaccepted();
    // end call
    await testUtils.dom.click(dialingPanel.$('.o_dial_hangup_button'));
    assert.strictEqual(
        dialingPanel
            .$(`
                .o_phonecall_details
                .o_dial_phonecall_partner_name
                span`)
            .html(),
        'Partner 123',
        "Phonecall of second partner should have been displayed");

    // start call
    await testUtils.dom.click(dialingPanel.$('.o_dial_call_button'));
    // simulate end of setTimeout in demo mode or answer in prod
    this.onaccepted();
    // end call
    await testUtils.dom.click(dialingPanel.$('.o_dial_hangup_button'));
    assert.containsNone(
        dialingPanel, `
            .o_dial_phonecalls
            .o_dial_phonecall`,
        "The list should be empty");
    assert.strictEqual(
        counterNextActivities,
        9,
        "avoid to much call to get_next_activities_list, would be great to lower this counter");

    const incomingCallParams = {
        data: {
            number: "123-456-789"
        }
    };
    // simulate an incoming call
    await dialingPanel._onIncomingCall(incomingCallParams);
    // Accept call
    await testUtils.dom.click(dialingPanel.$('.o_dial_accept_button'));
    assert.ok(
        dialingPanel._isInCall,
        "Should be in call");

    // Hangup call
    await testUtils.dom.click(dialingPanel.$('.o_dial_hangup_button'));
    assert.notOk(
        dialingPanel._isInCall,
        "Call should hang up");
    assert.containsOnce(
        dialingPanel,
        '.o_phonecall_details',
        "Details should be visible");

    // simulate an incoming call
    await dialingPanel._onIncomingCall(incomingCallParams);
    await testUtils.dom.click(dialingPanel.$('.o_dial_reject_button'));
    assert.notOk(dialingPanel._isInCall);
    assert.containsOnce(
        dialingPanel,
        '.o_phonecall_details',
        "Details should be visible");
    assert.verifySteps([
        'init_call',
        'hangup_call',
        'init_call',
        'canceled_call',
        'init_call',
        'hangup_call',
        'init_call',
        'hangup_call',
        'incoming_call',
        'incoming_call_accepted',
        // 'hangup_call', // disabled due to prevent crash from phonecall with no Id
        'incoming_call',
        'rejected_call'
    ]);

    parent.destroy();
});

QUnit.test('Call from Recent tab + keypad', async function (assert) {
    assert.expect(9);

    const self = this;

    const {
        dialingPanel,
        parent,
    } = await createDialingPanel({
        async mockRPC(route, args) {
            if (args.method === 'get_pbx_config') {
                return { mode: 'demo' };
            }
            if (args.model === 'voip.phonecall') {
                if (args.method === 'create_from_number') {
                    assert.step('create_from_number');
                    self.recentList = [{
                        call_date: '2019-06-06 08:05:47',
                        create_date: '2019-06-06 08:05:47.00235',
                        create_uid: 2,
                        date_deadline: '2019-06-06',
                        id: 0,
                        in_queue: 't',
                        name: 'Call to 123456789',
                        user_id: 2,
                        phone: '123456789',
                        phonecall_type: 'outgoing',
                        start_time: 1559808347,
                        state: 'pending',
                        write_date: '2019-06-06 08:05:48.568076',
                        write_uid: 2,
                    }];
                    return self.recentList[0];
                }
                if (args.method === 'create_from_recent') {
                    assert.step('create_from_recent');
                    return;
                }
                if (args.method === 'get_recent_list'){
                    return self.recentList;
                }
                if (args.method === 'get_next_activities_list') {
                    return self.phoneCallDetailsData.filter(phoneCallDetailData =>
                        ['done', 'cancel'].indexOf(phoneCallDetailData.state) === -1);
                }
                if (args.method === 'init_call') {
                    assert.step('init_call');
                    return [];
                }
                if (args.method === 'hangup_call') {
                    if (args.kwargs.done) {
                        for (const phoneCallDetailData of self.phoneCallDetailsData) {
                            if (phoneCallDetailData.id === args.args[0]) {
                                phoneCallDetailData.state = 'done';
                            }
                        }
                    }
                    assert.step('hangup_call');
                    return [];
                }
            }
            return this._super(...arguments);
        },
        services: this.services,
    });

    // make a first call
    assert.containsNone(
        dialingPanel,
        '.o_phonecall_details',
        "Details should not be visible yet");
    assert.containsNone(
        dialingPanel, `
            .o_dial_recent
            .o_dial_phonecalls
            .o_dial_phonecall`,
        "Recent tab should have 0 phonecall at the beginning");

    // select keypad
    await testUtils.dom.click(dialingPanel.$('.o_dial_keypad_icon'));
    // click on 1
    await testUtils.dom.click(dialingPanel.$('.o_dial_keypad_button')[0]);
    // click on 2
    await testUtils.dom.click(dialingPanel.$('.o_dial_keypad_button')[1]);
    // click on 3
    await testUtils.dom.click(dialingPanel.$('.o_dial_keypad_button')[2]);
    // click on 4
    await testUtils.dom.click(dialingPanel.$('.o_dial_keypad_button')[3]);
    // click on 5
    await testUtils.dom.click(dialingPanel.$('.o_dial_keypad_button')[4]);
    // click on 6
    await testUtils.dom.click(dialingPanel.$('.o_dial_keypad_button')[5]);
    // click on 7
    await testUtils.dom.click(dialingPanel.$('.o_dial_keypad_button')[6]);
    // click on 8
    await testUtils.dom.click(dialingPanel.$('.o_dial_keypad_button')[7]);
    // click on 9
    await testUtils.dom.click(dialingPanel.$('.o_dial_keypad_button')[8]);
    // call number 123456789
    await testUtils.dom.click(dialingPanel.$('.o_dial_call_button'));

    assert.strictEqual(
        dialingPanel
            .$(`
                .o_phonecall_details
                .o_dial_phonecall_partner_name
                span`)
            .html(),
        'Call to 123456789',
        "Details should have been shown");
    assert.ok(dialingPanel._isInCall);

    // simulate end of setTimeout in demo mode or answer in prod
    this.onaccepted();
    // end call
    await testUtils.dom.click(dialingPanel.$('.o_dial_hangup_button'));
    assert.notOk(dialingPanel._isInCall);

    // call number 123456789
    await testUtils.dom.click(dialingPanel.$('.o_dial_call_button'));
    this.onaccepted();
    // end call
    await testUtils.dom.click(dialingPanel.$('.o_dial_hangup_button'));
    assert.verifySteps([
        'create_from_number',
        'hangup_call',
        'create_from_recent',
        // 'hangup_call', // disabled due to prevent crash from phonecall with no Id
    ]);

    parent.destroy();
});

});
});
});
