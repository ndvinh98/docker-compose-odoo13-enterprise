odoo.define('web_studio.ReportEditorComponents_tests', function (require) {
"use strict";

var ajax = require('web.ajax');

var testUtils = require('web.test_utils');
var studioTestUtils = require('web_studio.testUtils');
var Widget = require('web.Widget');

var studioTestUtils = require('web_studio.testUtils');
var editComponentsRegistry = require('web_studio.reportEditComponentsRegistry');
var reportNewComponentsRegistry = require('web_studio.reportNewComponentsRegistry');


QUnit.module('Studio', {}, function () {

QUnit.module('ReportComponents', {
    before: function() {
        return new Promise(function (resolve, reject) {
            studioTestUtils.createSidebar({}).then(function (sidebar) {
                sidebar.destroy();
                resolve();
            });
        });
    },
    beforeEach: function () {
        this.widgetsOptions = {
            monetary: {
                company_id: {
                    type: "model",
                    string: "Company",
                    description: "Company used for the original currency (only used for t-esc)",
                    default_value: "Company used to render the template",
                    params: "res.company"
                },
                date: {
                    type: "date",
                    string: "Date",
                    description: "Date used for the original currency (only used for t-esc)",
                    default_value: "Current date"
                },
                from_currency: {
                    type: "model",
                    string: "Original currency",
                    params: "res.currency"
                },
                display_currency: {
                    type: "model",
                    string: "Display currency",
                    required: "value_to_html",
                    params: "res.currency"
                }
            },
            relative: {
                now: {
                    type: "datetime",
                    string: "Reference date",
                    description: "Date to compare with the field value.",
                    default_value: "Current date"
                }
            },
            image: {},
            text: {},
            html: {},
            many2many: {},
            date: {
                format: {
                    type: "string",
                    string: "Date format"
                }
            },
            datetime: {
                time_only: {
                    type: "boolean",
                    string: "Display only the time"
                },
                hide_seconds: {
                    type: "boolean",
                    string: "Hide seconds"
                },
                format: {
                    type: "string",
                    string: "Pattern to format"
                }
            },
            qweb: {},
            many2one: {},
            integer: {},
            float_time: {},
            contact: {
                separator: {
                    type: "string",
                    string: "Address separator",
                    description: "Separator use to split the addresse from the display_name.",
                    default_value: "\\n"
                },
                no_marker: {
                    type: "boolean",
                    string: "Hide marker",
                    description: "Don't display the font awsome marker"
                },
                country_image: {
                    type: "boolean",
                    string: "Displayed contry image",
                    description: "Display the country image if the field is present on the record"
                },
                fields: {
                    type: "array",
                    string: "Displayed fields",
                    description: "List of contact fields to display in the widget",
                    default_value: [
                        "name",
                        "address",
                        "phone",
                        "mobile",
                        "email"
                    ],
                    params: {
                        type: "selection",
                        params: [
                            "name",
                            "address",
                            "city",
                            "country_id",
                            "phone",
                            "mobile",
                            "email",
                            "fax",
                            "karma",
                            "website"
                        ]
                    }
                },
                no_tag_br: {
                    type: "boolean",
                    string: "Use comma",
                    description: "Use comma instead of the <br> tag to display the address"
                },
                phone_icons: {
                    type: "boolean",
                    string: "Displayed phone icons",
                    description: "Display the phone icons even if no_marker is True"
                }
            },
            duration: {
                unit: {
                    type: "select",
                    string: "Date unit",
                    description: "Date unit used for comparison and formatting",
                    default_value: "hour",
                    params: [
                        [ "year", "year" ],
                        [ "month", "month" ],
                        [ "week", "week" ],
                        [ "day", "day" ],
                        [ "hour", "hour" ],
                        [ "minute", "minute" ],
                        [ "second", "second" ]
                    ]
                },
                round: {
                    type: "select",
                    string: "Rounding unit",
                    description: "Date unit used for the rounding. If the value is given, this must be smaller than the unit",
                    default_value: "Same unit than \"unit\" option",
                    params: [
                        [ "year", "year" ],
                        [ "month", "month" ],
                        [ "week", "week" ],
                        [ "day", "day" ],
                        [ "hour", "hour" ],
                        [ "minute", "minute" ],
                        [ "second", "second" ]
                    ]
                }
            },
            selection: {
                selection: {
                    type: "selection",
                    string: "Selection",
                    default_value: "Use the field informations",
                    required: true
                }
            },
            barcode: {
                type: {
                    type: "string",
                    string: "Barcode type",
                    description: "Barcode type, eg: UPCA, EAN13, Code128",
                    default_value: "Code128"
                },
                width: {
                    type: "integer",
                    string: "Width",
                    default_value: 600
                },
                height: {
                    type: "integer",
                    string: "Height",
                    default_value: 100
                },
                humanreadable: {
                    type: "integer",
                    string: "Human Readable",
                    default_value: 0
                }
            },
            float: {
                precision: {
                    type: "integer",
                    string: "Rounding precision"
                }
            }
        };
        this.data = studioTestUtils.getData({
            'model.test': {
                fields: {
                    name: {string: "Name", type: "char"},
                    image: {string: "Image", type: "binary"},
                    child: {string: "Child", type: 'many2one', relation: 'model.test.child', searchable: true},
                    child_bis: {string: "Child Bis", type: 'many2one', relation: 'model.test.child', searchable: true},
                    children: {string: "Children", type: 'many2many', relation: 'model.test.child', searchable: true},
                },
                records: [],
            },
            'model.test.child': {
                fields: {
                    name: { string: "Name", type: "char" },
                    company_id: { string: "Company", type: "many2one", relation: 'res.company', searchable: true },
                    currency_id: { string: "Currency", type: "many2one", relation: 'res.currency', searchable: true },
                    date: { string: "Date", type: "datetime", searchable: true },
                },
                records: [],
            },
            'res.company': {
                fields: {
                    name: { string: "Name", type: "char" },
                },
                records: [],
            },
            'res.currency': {
                fields: {
                    name: { string: "Name", type: "char" },
                },
                records: [],
            },
        });
        studioTestUtils.patch();
    },
    afterEach: function () {
        studioTestUtils.unpatch();
    },
}, function () {
    QUnit.module('New');

    QUnit.test('field', async function (assert) {
        assert.expect(2);
        var parent = new Widget();
        testUtils.mock.addMockEnvironment(parent, {
            data: this.data,
        });
        await parent.appendTo($('#qunit-fixture'));
        var InlineField = reportNewComponentsRegistry.get('Inline')[1];
        var tOptions = new InlineField(parent, {
            models: {
                'model.test': 'Toto',
            },
        });

        tOptions.add({
            targets: [{
                data: {},
                node: {
                    attrs: {
                        'data-oe-id': 99,
                        'data-oe-xpath': '/my/node/path/',
                    },
                    contextOrder: ['toto'],
                    context: {
                        toto: 'model.test',
                    },
                    parent: {
                        children: [],
                        attrs: {},
                    }
                },
            }]
        }).then(function (res) {
            assert.deepEqual(res.inheritance,
                [{content: '<span t-field="toto.child"></span>', xpath: '/my/node/path/', view_id: 99, position: undefined}],
                "Should send the operation");
        });
        await testUtils.nextTick();

        await testUtils.dom.triggerEvents($('.o_web_studio_field_modal .o_field_selector'), ['focusin']);
        await testUtils.dom.click($('.o_web_studio_field_modal .o_field_selector_item[data-name="toto"]'));
        await testUtils.dom.click($('.o_web_studio_field_modal .o_field_selector_close'));
        await testUtils.dom.click($('.o_web_studio_field_modal .btn-primary'));

        assert.strictEqual($('.modal main[role="alert"]').length, 1,
            "Should display an alert because the field name of the record is wrong");
        await testUtils.dom.click($('.modal:has(main[role="alert"]) .btn-primary'));

        await testUtils.dom.triggerEvents($('.o_web_studio_field_modal .o_field_selector'), ['focusin']);
        await testUtils.dom.click($('.o_web_studio_field_modal .o_field_selector_item[data-name="child"]'));
        await testUtils.dom.click($('.o_web_studio_field_modal .btn-primary'));

        parent.destroy();
    });

    QUnit.test('add a binary field', async function (assert) {
        assert.expect(1);
        var parent = new Widget();
        testUtils.mock.addMockEnvironment(parent, {
            data: this.data,
        });
        await parent.appendTo($('#qunit-fixture'));
        var InlineField = reportNewComponentsRegistry.get('Inline')[1];
        var tOptions = new InlineField(parent, {
            models: {
                'model.test': 'Kikou',
            },
        });

        tOptions.add({
            targets: [{
                data: {},
                node: {
                    attrs: {
                        'data-oe-id': 99,
                        'data-oe-xpath': '/my/node/path/',
                    },
                    contextOrder: ['toto'],
                    context: {
                        toto: 'model.test',
                    },
                    parent: {
                        children: [],
                        attrs: {},
                    }
                },
            }]
        }).then(function (res) {
            assert.deepEqual(res.inheritance,
                [{content: '<span t-field="toto.image" t-options-widget="&quot;image&quot;"></span>', xpath: '/my/node/path/', view_id: 99, position: undefined}],
                "image widget should be set");
        });
        await testUtils.nextTick();

        await testUtils.dom.triggerEvents($('.o_web_studio_field_modal .o_field_selector'), ['focusin']);
        await testUtils.dom.click($('.o_web_studio_field_modal .o_field_selector_item[data-name="toto"]'));
        await testUtils.dom.click($('.o_web_studio_field_modal .o_field_selector_item[data-name="image"]'));
        await testUtils.dom.click($('.o_web_studio_field_modal .btn-primary'));

        parent.destroy();
    });

    QUnit.module('Edit');

    QUnit.test('column component with valid classes', async function (assert) {
        assert.expect(2);
        var parent = new Widget();
        await parent.appendTo($('#qunit-fixture'));
        var column = new (editComponentsRegistry.get('column'))(parent, {
            node: {
                attrs: {
                    class: 'col-5 offset-3',
                },
            },
        });
        await column.appendTo(parent.$el);

        assert.strictEqual(column.$('input[name="size"]').val(), "5",
            "the size should be correctly set");
        assert.strictEqual(column.$('input[name="offset"]').val(), "3",
            "the offset should be correctly set");

        parent.destroy();
    });

    QUnit.test('column component with invalid classes', async function (assert) {
        assert.expect(2);
        var parent = new Widget();
        await parent.appendTo($('#qunit-fixture'));
        var column = new (editComponentsRegistry.get('column'))(parent, {
            node: {
                attrs: {
                    class: 'col- offset-kikou',
                },
            },
        });
        await column.appendTo(parent.$el);

        assert.strictEqual(column.$('input[name="size"]').val(), "",
            "the size should be unkown");
        assert.strictEqual(column.$('input[name="offset"]').val(), "",
            "the offset should be unkown");

        parent.destroy();
    });

    QUnit.test('hidden "width" for layout component with col nodes', async function (assert) {
        assert.expect(1);
        var parent = new Widget();
        testUtils.mock.addMockEnvironment(parent, this);
        await parent.appendTo($('#qunit-fixture'));
        var layout = new (editComponentsRegistry.get('layout'))(parent, {
            node: {
                tag: 'div',
                attrs: {
                    class: 'col- offset-kikou',
                },
                $nodes: $(),
            },
        });
        await layout.appendTo(parent.$el);

        assert.containsNone(layout.$('.o_web_studio_width'),
            "the width attribute shouldn't be displayed for div.col nodes");

        parent.destroy();
    });

    QUnit.test('tOptions component', async function (assert) {
        assert.expect(3);
        var parent = new Widget();
        await parent.appendTo($('#qunit-fixture'));
        var tOptions = new (editComponentsRegistry.get('tOptions'))(parent, {
            widgetsOptions: this.widgetsOptions,
            node: {
                attrs: {
                    't-options': '{"widget": "text"}',
                    't-options-widget': '"image"',
                    't-options-other-options': 'True',
                    'data-oe-id': 99,
                    'data-oe-xpath': '/my/node/path/',
                },
            },
            context: {},
            state: null,
            models: null,
        });
        await tOptions.appendTo(parent.$el);
        assert.strictEqual(tOptions.$('select').val(), 'image',
            "Should select the image widget");
        assert.containsNone(tOptions, '.o_web_studio_toption_option',
            "there should be no available option");

        // unset the `widget`
        testUtils.mock.addMockEnvironment(parent, {
            intercepts: {
                view_change: function (ev) {
                    assert.deepEqual(ev.data.operation.new_attrs, {'t-options-widget': '""'},
                        "should correctly delete the group");
                },
            },
        });
        tOptions.$('select').val('').trigger('change');

        parent.destroy();
    });

    QUnit.test('tOptions component parse expression', async function (assert) {
        assert.expect(5);
        var parent = new Widget();
        await parent.appendTo($('#qunit-fixture'));

        var fields = this.data['model.test.child'].fields;
        fields.company_id = {string: "Company", type: "many2one", relation: 'res.company', searchable: true};
        fields.currency_id = {string: "Currency", type: "many2one", relation: 'res.currency', searchable: true};
        fields.date = {string: "Date", type: "datetime", searchable: true};
        testUtils.mock.addMockEnvironment(parent, {
            data: this.data,
        });

        var tOptions = new (editComponentsRegistry.get('tOptions'))(parent, {
            widgetsOptions: this.widgetsOptions,
            node: {
                attrs: {
                    't-options': 'dict(from_currency=o.child.currency_id, date=o.child.date)',
                    't-options-widget': '"monetary"',
                    't-options-company_id': 'o.child.company_id',
                    'data-oe-id': 99,
                    'data-oe-xpath': '/my/node/path/',
                },
                context: {"o": "model.test"},
            },
            context: {},
            state: null,
            models: {"model.test": "Model Test"},
        });

        await tOptions.appendTo(parent.$el);
        assert.strictEqual(tOptions.$('select').val(), 'monetary',
            "Should select the image widget");
        assert.containsN(tOptions, '.o_web_studio_toption_option', 4,
            "there should be 4 available options for the monetary widget");
        assert.strictEqual(tOptions.$('.o_web_studio_toption_option_monetary_from_currency .o_field_selector_value').text().replace(/\s+/g, ''),
            "o(ModelTest)ChildCurrency",
            "Should display the currency field");
        assert.strictEqual(tOptions.$('.o_web_studio_toption_option_monetary_date .o_field_selector_value').text().replace(/\s+/g, ''),
            "o(ModelTest)ChildDate",
            "Should display the data field");
        assert.strictEqual(tOptions.$('.o_web_studio_toption_option_monetary_company_id .o_field_selector_value').text().replace(/\s+/g, ''),
            "o(ModelTest)ChildCompany",
            "Should display the company field");

        parent.destroy();
    });

    QUnit.test('tEsc component with parsable expression', async function (assert) {
        assert.expect(1);
        var parent = new Widget();
        await parent.appendTo($('#qunit-fixture'));

        testUtils.mock.addMockEnvironment(parent, {
            data: this.data,
        });

        var tOptions = new (editComponentsRegistry.get('tEsc'))(parent, {
            node: {
                attrs: {
                    't-esc': 'o.child.company_id',
                    'data-oe-id': 99,
                    'data-oe-xpath': '/my/node/path/',
                },
                context: {"o": "model.test"},
            },
            context: {},
            state: null,
            models: {"model.test": "Model Test"},
        });
        await tOptions.appendTo(parent.$el);
        await testUtils.nextTick();
        // the component value is parsable so we display it with ModelFieldSelector
        assert.strictEqual(tOptions.$('.o_field_selector_value').text().replace(/\s+/g, ''),
            "o(ModelTest)ChildCompany",
            "Should display the company field");

        parent.destroy();
    });

    QUnit.test('tEsc component with non-parsable expression', async function (assert) {
        assert.expect(1);
        var parent = new Widget();
        await parent.appendTo($('#qunit-fixture'));

        testUtils.mock.addMockEnvironment(parent, {
            data: this.data,
        });

        var tOptions = new (editComponentsRegistry.get('tEsc'))(parent, {
            node: {
                attrs: {
                    't-esc': 'o.child.getCompany()',
                    'data-oe-id': 99,
                    'data-oe-xpath': '/my/node/path/',
                },
                context: {"o": "model.test"},
            },
            context: {},
            state: null,
            models: {"model.test": "Model Test"},
        });
        await tOptions.appendTo(parent.$el);
        await testUtils.nextTick();
        // the component can not parse the value so we display a simple input
        assert.strictEqual(tOptions.$('input[name="t-esc"]').val(),
            "o.child.getCompany()",
            "Should display the company field");

        parent.destroy();
    });

    QUnit.test('contact: many2many_select', async function (assert) {
        assert.expect(11);
        var parent = new Widget();

        $('ul.ui-autocomplete').remove(); // clean the body to avoid errors due to another test

        var optionsFields;
        testUtils.mock.addMockEnvironment(parent, {
            intercepts: {
                view_change: function (ev) {
                    assert.deepEqual(ev.data.operation.new_attrs['t-options-fields'], optionsFields,
                        'Should save the contact options');

                    params.node.attrs['t-options-fields'] = JSON.stringify(ev.data.operation.new_attrs['t-options-fields']);
                },
            },
        });
        await parent.appendTo($('#qunit-fixture'));

        var params = {
            widgetsOptions: this.widgetsOptions,
            node: {
                attrs: {
                    't-options': '{"widget": "contact"}',
                    't-options-no_marker': 'True',
                    'data-oe-id': 99,
                    'data-oe-xpath': '/my/node/path/',
                },
            },
            context: {},
            state: null,
            models: null,
        };

        var tOptions = new (editComponentsRegistry.get('tOptions'))(parent, params);
        await tOptions.appendTo(parent.$el);
        assert.containsN(tOptions, '.o_web_studio_toption_option', 3,
            "there should be 3 available options for the contact widget (they are filtered)");
        assert.strictEqual(tOptions.$('.o_badge_text').text(), 'nameaddressphonemobileemail', 'Should display default value');
        await testUtils.dom.click(tOptions.$('.o_input_dropdown input'));
        assert.strictEqual($('ul.ui-autocomplete .ui-menu-item').length, 5, 'Should not display the unselected items');
        assert.strictEqual($('ul.ui-autocomplete .o_m2o_dropdown_option').length, 0, 'Should not display create button');

        optionsFields = ["name", "address", "phone", "mobile", "email", "city"];
        await testUtils.dom.click($('ul.ui-autocomplete .ui-menu-item:contains(city)'));
        tOptions.destroy();

        tOptions = new (editComponentsRegistry.get('tOptions'))(parent, params);
        await tOptions.appendTo(parent.$el);
        assert.strictEqual(tOptions.$('.o_badge_text').text(), 'nameaddresscityphonemobileemail', 'Should display the new value');
        await testUtils.dom.click(tOptions.$('.o_input_dropdown input'));
        assert.strictEqual($('ul.ui-autocomplete .ui-menu-item').length, 4, 'Should not display the unselected items');
        await testUtils.dom.click(tOptions.$('.o_input_dropdown input'));

        optionsFields = ["address", "phone", "mobile", "email", "city"];
        await testUtils.dom.click(tOptions.$('.o_field_many2manytags .o_delete:first'));
        assert.strictEqual(tOptions.$('.o_badge_text').text(), 'addresscityphonemobileemail', 'Should display the new value without "name"');

        optionsFields = ["phone", "mobile", "email", "city"];
        await testUtils.dom.click(tOptions.$('.o_field_many2manytags .o_delete:first'));
        assert.strictEqual(tOptions.$('.o_badge_text').text(), 'cityphonemobileemail', 'Should display the new value without "name"');

        parent.destroy();
    });

    QUnit.test('no search more in many2many_select', async function (assert) {
        assert.expect(3);
        var parent = new Widget();

        $('ul.ui-autocomplete').remove(); // clean the body to avoid errors due to another test

        await parent.appendTo($('#qunit-fixture'));

        // to display more options in the many2many_select
        this.widgetsOptions.contact.fields.default_value = [];

        var tOptions = new (editComponentsRegistry.get('tOptions'))(parent, {
            widgetsOptions: this.widgetsOptions,
            node: {
                attrs: {
                    't-options': '{"widget": "contact"}',
                    't-options-no_marker': 'True',
                    'data-oe-id': 99,
                    'data-oe-xpath': '/my/node/path/',
                },
            },
            context: {},
            state: null,
            models: null,
        });
        await tOptions.appendTo(parent.$el);

        assert.strictEqual(tOptions.$('.o_badge_text').text(), '', 'Should display default value');
        await testUtils.dom.click(tOptions.$('.o_input_dropdown input'));
        assert.strictEqual($('ul.ui-autocomplete .ui-menu-item').length, 10, 'Should not display the unselected items');
        assert.strictEqual($('ul.ui-autocomplete .o_m2o_dropdown_option').length, 0, 'Should not display create button nor the search more');

        parent.destroy();
    });

    QUnit.test('groups component', async function (assert) {
        assert.expect(3);
        var parent = new Widget();
        await parent.appendTo($('#qunit-fixture'));
        var groups = new (editComponentsRegistry.get('groups'))(parent, {
            widgets: this.widgets,
            node: {
                tag: 'span',
                attrs: {
                    studio_groups: "[" +
                        "{\"name\": \"group_A\", \"display_name\": \"My Awesome Group\", \"id\": 42}," +
                        "{\"name\": \"group_13\", \"display_name\": \"Kikou\", \"id\": 13}" +
                    "]",
                },
            },
        });
        await groups.appendTo(parent.$el);

        assert.containsN(groups, '.o_field_many2manytags .o_badge_text', 2,
            "there should be displayed two groups");
        assert.strictEqual(groups.$('.o_field_many2manytags').text().replace(/\s/g, ''), "MyAwesomeGroupKikou",
            "the groups should be correctly set");

        // delete a group
        testUtils.mock.addMockEnvironment(parent, {
            intercepts: {
                view_change: function (ev) {
                    assert.deepEqual(ev.data.operation.new_attrs, {groups: [13]},
                        "should correctly delete the group");
                },
            },
        });
        await testUtils.dom.click(groups.$('.o_field_many2manytags .o_delete:first'));

        parent.destroy();
    });
});

});

});
