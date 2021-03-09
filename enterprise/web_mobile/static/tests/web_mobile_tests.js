odoo.define('web_mobile.tests', function (require) {
"use strict";

const Dialog = require('web.Dialog');
const dom = require('web.dom');
const FormView = require('web.FormView');
const KanbanView = require('web.KanbanView');
const testUtils = require('web.test_utils');
const Widget = require('web.Widget');

const mobileMixins = require('web_mobile.mixins');
const mobile = require('web_mobile.rpc');

const {createParent, createView} = testUtils;

QUnit.module('web_mobile', {
    beforeEach: function () {
        this.data = {
            partner: {
                fields: {
                    name: {string: "name", type: "char"},
                    image_1920: {},
                    parent_id: {string: "Parent", type: "many2one", relation: 'partner'},
                    sibling_ids: {string: "Sibling", type: "many2many", relation: 'partner'},
                    phone: {},
                    mobile: {},
                    email: {},
                    street: {},
                    street2: {},
                    city: {},
                    state_id: {},
                    zip: {},
                    country_id: {},
                    website: {},
                    function: {},
                    title: {},
                },
                records: [{
                    id: 1,
                    name: 'coucou1',
                }, {
                    id: 2,
                    name: 'coucou2',
                }, {
                    id: 11,
                    name: 'coucou3',
                    image_1920: 'image',
                    parent_id: 1,
                    phone: 'phone',
                    mobile: 'mobile',
                    email: 'email',
                    street: 'street',
                    street2: 'street2',
                    city: 'city',
                    state_id: 'state_id',
                    zip: 'zip',
                    country_id: 'country_id',
                    website: 'website',
                    function: 'function',
                    title: 'title',
                }],
            },
        };
    },
}, function () {

    QUnit.test("contact sync in a non-mobile environment", async function (assert) {
        assert.expect(2);

        let rpcCount = 0;

        const form = await createView({
            View: FormView,
            arch: '<form>' +
                    '<sheet>' +
                        '<div name="button_box">' +
                            '<contactsync> </contactsync>' +
                        '</div>' +
                        '<field name="name"/>' +
                    '</sheet>' +
                  '</form>',
            data: this.data,
            model: 'partner',
            mockRPC: function () {
                rpcCount++;
                return this._super.apply(this, arguments);
            },
            res_id: 11,
        });

        const $button = form.$('button.oe_stat_button[widget="contact_sync"]');

        assert.strictEqual($button.length, 0, "the tag should not be visible in a non-mobile environment");
        assert.strictEqual(rpcCount, 1, "no extra rpc should be done by the widget (only the one from the view)");

        form.destroy();
    });

    QUnit.test("contact sync in a mobile environment", async function (assert) {
        assert.expect(5);


        const __addContact = mobile.methods.addContact;
        let addContactRecord;
        // override addContact to simulate a mobile environment
        mobile.methods.addContact = function (r) {
            addContactRecord = r;
        };

        let rpcDone;
        let rpcCount = 0;

        const form = await createView({
            View: FormView,
            arch:
                '<form>' +
                    '<sheet>' +
                        '<div name="button_box">' +
                            '<contactsync> </contactsync>' +
                        '</div>' +
                        '<field name="name"/>' +
                    '</sheet>' +
                '</form>',
            data: this.data,
            model: 'partner',
            mockRPC: function (route, args) {
                if (args.method === "read" && args.args[0] === 11 && _.contains(args.args[1], 'phone')) {
                    rpcDone = true;
                }
                rpcCount++;
                return this._super(route, args);
            },
            res_id: 11,
        });

        const $button = form.$('button.oe_stat_button[widget="contact_sync"]');

        assert.strictEqual($button.length, 1, "the tag should be visible in a mobile environment");
        assert.strictEqual(rpcCount, 1, "no extra rpc should be done by the widget (only the one from the view)");

        await testUtils.dom.click($button);

        assert.strictEqual(rpcCount, 2, "an extra rpc should be done on click");
        assert.ok(rpcDone, "a read rpc should have been done");
        assert.deepEqual(addContactRecord, {
            city: "city",
            country_id: "country_id",
            email: "email",
            function: "function",
            id: 11,
            image: "image",
            mobile: "mobile",
            name: "coucou3",
            parent_id: [
                1,
                "coucou1",
            ],
            phone: "phone",
            state_id: "state_id",
            street: "street",
            street2: "street2",
            website: "website",
            zip: "zip"
        }, "all data should be correctly passed");

        mobile.methods.addContact = __addContact;

        form.destroy();
    });

    QUnit.test('autofocus quick create form', async function (assert) {
        assert.expect(2);

        const kanban = await createView({
            View: KanbanView,
            model: 'partner',
            data: this.data,
            arch: '<kanban on_create="quick_create">' +
                    '<templates><t t-name="kanban-box">' +
                        '<div><field name="name"/></div>' +
                    '</t></templates>' +
                '</kanban>',
            groupBy: ['parent_id'],
        });

        // quick create in first column
        await testUtils.dom.click(kanban.$buttons.find('.o-kanban-button-new'));
        assert.ok(kanban.$('.o_kanban_group:nth(0) > div:nth(1)').hasClass('o_kanban_quick_create'),
            "clicking on create should open the quick_create in the first column");
        assert.strictEqual(document.activeElement, kanban.$('.o_kanban_quick_create .o_input:first')[0],
            "the first input field should get the focus when the quick_create is opened");

        kanban.destroy();
    });

    QUnit.test("control panel appears at top on scroll event", async function (assert) {
        assert.expect(11);

        const Q_UNIT_FIXTURE_SELECTOR = '#qunit-fixture';
        const MOBILE_STICK_CLASS = 'o_mobile_sticky';
        const MAX_HEIGHT = 400;
        const MIDLE_HEIGHT = 200;
        const DELTA_TEST = 20;
        const scrollEvent = new UIEvent('scroll');

        function scrollAtHeight(height) {
            window.scrollTo(0, height);
            document.dispatchEvent(scrollEvent);
        }

        const form = await createView({
            View: FormView,
            arch:
                '<form>' +
                    '<sheet>' +
                        '<div style="height: 1000px"></div>' +
                    '</sheet>' +
                '</form>',
            data: this.data,
            model: 'partner',
            res_id: 11,
        });

        const controlPanelElement = document.querySelector('.o_cp_controller');
        const controlPanelHeight = controlPanelElement.clientHeight;

        // Force viewport to have a scrollbar
        document.querySelector(Q_UNIT_FIXTURE_SELECTOR).style.position = 'initial';

        assert.strictEqual(controlPanelElement.style.top, '0px',
            'Top must be 0px (start position)');
        assert.notOk(controlPanelElement.classList.contains(MOBILE_STICK_CLASS),
            'Must not have class o_mobile_sticky (start position)');

        scrollAtHeight(MAX_HEIGHT);

        const valueExpected = -controlPanelHeight;
        assert.strictEqual(controlPanelElement.style.top, valueExpected + 'px',
            'Top must be ' + valueExpected + 'px (after scroll to MAX_HEIGHT)');
        assert.ok(controlPanelElement.classList.contains(MOBILE_STICK_CLASS),
            'Must have class o_mobile_sticky (after scroll to MAX_HEIGHT)');

        scrollAtHeight(MAX_HEIGHT - DELTA_TEST);

        const valueExpectedWithDelta = -(controlPanelHeight - DELTA_TEST);
        assert.strictEqual(controlPanelElement.style.top, valueExpectedWithDelta + 'px',
            'Top must be ' + valueExpectedWithDelta + 'px (after scroll to MAX_HEIGHT - DELTA_TEST)');
        assert.ok(controlPanelElement.classList.contains(MOBILE_STICK_CLASS),
            'Must have class o_mobile_sticky (after scroll to MAX_HEIGHT - DELTA_TEST)');

        scrollAtHeight(MIDLE_HEIGHT);

        assert.strictEqual(controlPanelElement.style.top, '0px',
            'Top must be 0px (after scroll to MIDLE_HEIGHT)');
        assert.ok(controlPanelElement.classList.contains(MOBILE_STICK_CLASS),
            'Must have class o_mobile_sticky (after scroll to MIDLE_HEIGHT)');

        scrollAtHeight(MAX_HEIGHT);

        assert.strictEqual(controlPanelElement.style.top, (-controlPanelHeight) + 'px',
            'Top must be ' + (-controlPanelHeight) + 'px (after scroll to MAX_HEIGHT again)');
        assert.ok(controlPanelElement.classList.contains(MOBILE_STICK_CLASS),
            'Must have class o_mobile_sticky (after scroll to MAX_HEIGHT again)');

        scrollAtHeight(0);

        assert.notOk(controlPanelElement.classList.contains(MOBILE_STICK_CLASS),
            'Must not have class o_mobile_sticky (after return to start position)');

        form.destroy();

        // Reset viewport position attribute
        document.querySelector(Q_UNIT_FIXTURE_SELECTOR).style.position = '';
    });

    QUnit.module('BackButtonEventMixin');

    QUnit.test('widget should receive a backbutton event', async function (assert) {
        assert.expect(5);

        const __overrideBackButton = mobile.methods.overrideBackButton;
        mobile.methods.overrideBackButton = function ({enabled}) {
            assert.step(`overrideBackButton: ${enabled}`);
        };

        const DummyWidget = Widget.extend(mobileMixins.BackButtonEventMixin, {
            _onBackButton(ev) {
                assert.step(`${ev.type} event`);
            },
        });
        const backButtonEvent = new Event('backbutton');
        const dummy = new DummyWidget();
        dummy.appendTo($('<div>'));

        // simulate 'backbutton' event triggered by the app
        document.dispatchEvent(backButtonEvent);
        // waiting nextTick to match testUtils.dom.triggerEvents() behavior
        await testUtils.nextTick();

        assert.verifySteps([], "shouldn't have register handle before attached to the DOM");

        dom.append($('qunit-fixtures'), dummy.$el, {in_DOM: true, callbacks: [{widget: dummy}]});

        // simulate 'backbutton' event triggered by the app
        document.dispatchEvent(backButtonEvent);
        await testUtils.nextTick();

        dom.detach([{widget: dummy}]);

        assert.verifySteps([
            'overrideBackButton: true',
            'backbutton event',
            'overrideBackButton: false',
        ], "should have enabled/disabled the back-button override");

        dummy.destroy();
        mobile.methods.overrideBackButton = __overrideBackButton;
    });

    QUnit.test('multiple widgets should receive backbutton events in the right order', async function (assert) {
        assert.expect(6);

        const __overrideBackButton = mobile.methods.overrideBackButton;
        mobile.methods.overrideBackButton = function ({enabled}) {
            assert.step(`overrideBackButton: ${enabled}`);
        };

        const DummyWidget = Widget.extend(mobileMixins.BackButtonEventMixin, {
            init(parent, {name}) {
                this._super.apply(this, arguments);
                this.name = name;
            },
            _onBackButton(ev) {
                assert.step(`${this.name}: ${ev.type} event`);
                dom.detach([{widget: this}]);
            },
        });
        const backButtonEvent = new Event('backbutton');
        const dummy1 = new DummyWidget(null, {name: 'dummy1'});
        dom.append($('qunit-fixtures'), dummy1.$el, {in_DOM: true, callbacks: [{widget: dummy1}]});

        const dummy2 = new DummyWidget(null, {name: 'dummy2'});
        dom.append($('qunit-fixtures'), dummy2.$el, {in_DOM: true, callbacks: [{widget: dummy2}]});

        const dummy3 = new DummyWidget(null, {name: 'dummy3'});
        dom.append($('qunit-fixtures'), dummy3.$el, {in_DOM: true, callbacks: [{widget: dummy3}]});

        // simulate 'backbutton' events triggered by the app
        document.dispatchEvent(backButtonEvent);
        // waiting nextTick to match testUtils.dom.triggerEvents() behavior
        await testUtils.nextTick();
        document.dispatchEvent(backButtonEvent);
        await testUtils.nextTick();
        document.dispatchEvent(backButtonEvent);
        await testUtils.nextTick();

        assert.verifySteps([
            'overrideBackButton: true',
            'dummy3: backbutton event',
            'dummy2: backbutton event',
            'dummy1: backbutton event',
            'overrideBackButton: false',
        ]);

        dummy1.destroy();
        dummy2.destroy();
        dummy3.destroy();
        mobile.methods.overrideBackButton = __overrideBackButton;
    });

    QUnit.module('Dialog');

    QUnit.test('dialog is closable with backbutton event', async function (assert) {
        assert.expect(5);

        const __overrideBackButton = mobile.methods.overrideBackButton;
        mobile.methods.overrideBackButton = function () {};

        testUtils.mock.patch(Dialog, {
            close: function () {
                assert.step("close");
                return this._super.apply(this, arguments);
            },
        });

        const parent = createParent({
            data: this.data,
            archs: {
                'partner,false,form': `
                    <form>
                        <sheet>
                            <field name="name"/>
                        </sheet>
                   </form>
                `,
            },
        });

        const backButtonEvent = new Event('backbutton');
        const dialog = new Dialog(parent, {
            res_model: 'partner',
            res_id: 1,
        }).open();
        await dialog.opened().then(() => {
            assert.step('opened');
        });
        assert.containsOnce(document.body, '.modal', "should have a modal");

        // simulate 'backbutton' event triggered by the app waiting
        document.dispatchEvent(backButtonEvent);
        // nextTick to match testUtils.dom.triggerEvents() behavior
        await testUtils.nextTick();

        // The goal of this assert is to check that our event called the
        // opened/close methods on Dialog.
        assert.verifySteps([
            'opened',
            'close',
        ], "should have open/close dialog");
        assert.containsNone(document.body, '.modal', "modal should be closed");

        parent.destroy();
        testUtils.mock.unpatch(Dialog);
        mobile.methods.overrideBackButton = __overrideBackButton;
    });
});
});
