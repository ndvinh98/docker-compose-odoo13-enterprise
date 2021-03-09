odoo.define('web_studio.ReportEditorSidebar_tests', function (require) {
"use strict";

var config = require('web.config');
var testUtils = require('web.test_utils');

var studioTestUtils = require('web_studio.testUtils');

QUnit.module('Studio', {}, function () {

    QUnit.module('ReportEditorSidebar', {
        beforeEach: function () {
            this.data = {
                'report.paperformat': {
                    fields: {
                        display_name: {string: "Name", type: "char"},
                    },
                    records: [{
                        id: 42,
                        display_name: 'My Awesome Format',
                    }],
                },
                'res.groups': {
                    fields: {
                        display_name: {string: "Name", type: "char"},
                    },
                    records: [{
                        id: 6,
                        display_name: 'Group6',
                    }, {
                        id: 7,
                        display_name: 'Group7',
                    }],
                },
                'x_mymodel': {
                    fields: {
                        display_name: {string: "Name", type: "char"},
                    },
                },
            };

            this.widgetsOptions = {
                image: {},
                integer: {},
                text: {},
            };
        },
    }, function () {
        QUnit.test("basic rendering", async function (assert) {
            var done = assert.async();
            assert.expect(5);

            studioTestUtils.createSidebar({
                state: { mode: 'report' },
                report: {},
            }).then(async function (sidebar) {

            assert.hasClass(sidebar.$('.o_web_studio_sidebar_header [name="report"]'),'active',
                "the report tab should be active");
            assert.hasClass(sidebar.$('.o_web_studio_sidebar_header [name="options"]'),'inactive',
                "the options tab should be inactive");

            testUtils.mock.intercept(sidebar, 'sidebar_tab_changed', function (ev) {
                assert.step(ev.data.mode);
            });
            testUtils.dom.click(sidebar.$('.o_web_studio_sidebar_header [name="new"]'));
            assert.verifySteps(['new'], "the sidebar should be updated");

            await testUtils.dom.click(sidebar.$('.o_web_studio_sidebar_header [name="options"]'));
            assert.verifySteps([], "one should not be able to select options");

            sidebar.destroy();
            done();
            });
        });

        QUnit.test("'Report' tab behaviour", async function (assert) {
            assert.expect(6);

            return studioTestUtils.createSidebar({
                data: this.data,
                state: { mode: 'report' },
                report: {
                    name: 'Kikou',
                },
            }).then(async function (sidebar) {

            assert.hasAttrValue(sidebar.$('.o_web_studio_sidebar_header > .active'), 'name', "report",
                "the 'Report' tab should be active");
            assert.strictEqual(sidebar.$('input[name="name"]').val(), "Kikou",
                "the report name should be displayed");

            testUtils.mock.intercept(sidebar, 'studio_edit_report', function (ev) {
                if (ev.data.name) {
                    assert.deepEqual(ev.data, { name: "wow_report" });
                } else if ('paperformat_id' in ev.data) {
                    paperformatValues.push(ev.data);
                } else if (ev.data.groups_id) {
                    assert.deepEqual(ev.data, { groups_id: [7] });
                }
            });
            // edit report name
            sidebar.$('input[name="name"]').val("wow_report").trigger('change');

            // edit the report paperformat
            var paperformatValues = [];
            await testUtils.fields.many2one.clickOpenDropdown('paperformat_id');
            await testUtils.fields.many2one.clickHighlightedItem('paperformat_id');
            assert.deepEqual(paperformatValues, [{ paperformat_id: 42 }]);

            // remove the report paperformat
            sidebar.$('[name="paperformat_id"] input').val('').trigger('keyup').trigger('focusout');
            await testUtils.nextTick();
            assert.deepEqual(paperformatValues, [{ paperformat_id: 42 }, { paperformat_id: false }]);

            // edit groups
            await testUtils.fields.many2one.clickOpenDropdown('groups_id');
            await testUtils.fields.many2one.clickItem('groups_id', 'Group7');

            sidebar.destroy();
            });
        });

        QUnit.test("'Add' tab behaviour", function (assert) {
            var done = assert.async();
            assert.expect(2);

            studioTestUtils.createSidebar({
                state: { mode: 'new' },
            }).then(function (sidebar) {

            assert.hasAttrValue(sidebar.$('.o_web_studio_sidebar_header > .active'), 'name', "new",
                "the 'Add' tab should be active");
            assert.ok(sidebar.$('.ui-draggable').length,
                "there should be draggable components");

            sidebar.destroy();
            done();
            });
        });

        QUnit.test("basic 'Options' tab behaviour", function (assert) {
            var done = assert.async();
            assert.expect(4);

            var node = {
                node: {
                    attrs: {
                        'data-oe-id': '42',
                        'data-oe-xpath': '/t/t/div',
                    },
                    tag: 'span',
                    $nodes: $(),
                },
            };
            studioTestUtils.createSidebar({
                state: {
                    mode: 'properties',
                    nodes: [node],
                },
            }).then(function (sidebar) {

            assert.hasAttrValue(sidebar.$('.o_web_studio_sidebar_header > .active'), 'name', "options",
                "the 'Options' tab should be active");
            assert.containsOnce(sidebar, '.o_web_studio_sidebar_content .collapse',
                "there should be one node in the accordion");
            assert.hasClass(sidebar.$('.o_web_studio_sidebar_content .collapse'),'show',
                "the node should be expanded by default");

            // remove the element
            testUtils.mock.intercept(sidebar, 'element_removed', function (ev) {
                assert.deepEqual(ev.data.node, node.node);
            });
            testUtils.dom.click(sidebar.$('.o_web_studio_sidebar_content .collapse .o_web_studio_remove'));

            sidebar.destroy();
            done();
            });
        });

        QUnit.test("'Options' tab with multiple nodes", function (assert) {
            var done = assert.async();
            assert.expect(9);

            var node1 = {
                node: {
                    attrs: {
                        'data-oe-id': '42',
                        'data-oe-xpath': '/t/t/div',
                    },
                    tag: 'span',
                    $nodes: $(),
                },
            };

            var node2 = {
                node: {
                    attrs: {
                        'data-oe-id': '40',
                        'data-oe-xpath': '/t/t',
                    },
                    tag: 'div',
                    $nodes: $(),
                },
            };
            studioTestUtils.createSidebar({
                state: {
                    mode: 'properties',
                    nodes: [node1, node2],
                },
            }).then(function (sidebar) {

            assert.hasAttrValue(sidebar.$('.o_web_studio_sidebar_header > .active'), 'name', "options",
                "the 'Options' tab should be active");
            assert.containsN(sidebar, '.o_web_studio_sidebar_content .card', 2,
                "there should be one node in the accordion");
            assert.hasClass(sidebar.$('.o_web_studio_sidebar_content .card:has(.o_text:contains(span)) .collapse'),'show',
                "the 'span' node should be expanded by default");
            assert.doesNotHaveClass(sidebar.$('.o_web_studio_sidebar_content .card:has(.o_text:contains(div)) .collapse'), 'show',
                "the 'div' node shouldn't be expanded");
            assert.strictEqual(sidebar.$('.o_web_studio_sidebar_content .o_web_studio_accordion > .card:last .card-header:first').text().trim(), "span",
                "the last node should be the span");

            // expand the first node
            testUtils.dom.click(sidebar.$('.o_web_studio_sidebar_content .o_web_studio_accordion > .card:first [data-toggle="collapse"]:first'));
            // BS4 collapsing is asynchronous
            setTimeout(function () {
                assert.doesNotHaveClass(sidebar.$('.o_web_studio_sidebar_content .card:has(.o_text:contains(span)) .collapse:first'), 'show',
                    "the 'span' node should have been closed");
                assert.hasClass(sidebar.$('.o_web_studio_sidebar_content .card:has(.o_text:contains(div)) .collapse:first'),'show',
                    "the 'div' node should be expanded");

                // reexpand the second node
                testUtils.dom.click(sidebar.$('.o_web_studio_sidebar_content .o_web_studio_accordion > .card:last [data-toggle="collapse"]:first'));
                setTimeout(function () {
                    assert.hasClass(sidebar.$('.o_web_studio_sidebar_content .card:has(.o_text:contains(span)) .collapse:first'),'show',
                        "the 'span' node should be expanded again");
                    assert.doesNotHaveClass(sidebar.$('.o_web_studio_sidebar_content .card:has(.o_text:contains(div)) .collapse:first'), 'show',
                        "the 'div' node shouldn't be expanded anymore");

                    sidebar.destroy();
                    done();
                }, 0);
            },0);
            });
        });

        QUnit.test("'Options' tab with layout component can be expanded", function (assert) {
            var done = assert.async();
            assert.expect(3);

            var node = {
                node: {
                    attrs: {
                        'data-oe-id': '42',
                        'data-oe-xpath': '/t/t/div',
                    },
                    tag: 'span',
                    $nodes: $(),
                },
            };
            studioTestUtils.createSidebar({
                state: {
                    mode: 'properties',
                    nodes: [node],
                },
            }).then(function (sidebar) {

            assert.containsOnce(sidebar, '.o_web_studio_sidebar_content .collapse',
                "there should be one node in the accordion");
            assert.containsOnce(sidebar, '.o_web_studio_sidebar_content .o_web_studio_layout',
                "there should be a layout component");
            assert.containsOnce(sidebar, '.o_web_studio_sidebar_content .o_web_studio_layout .o_web_studio_margin',
                "there should be a margin section in the layout component");

            sidebar.destroy();
            done();
            });
        });

        QUnit.test("'Options' tab with layout component can be expanded on open ", function (assert) {
            var done = assert.async();
            assert.expect(1);

            var node = {
                node: {
                    attrs: {
                        'data-oe-id': '42',
                        'data-oe-xpath': '/t/t/div',
                    },
                    tag: 'span',
                    $nodes: $(),
                },
            };
            studioTestUtils.createSidebar({
                state: {
                    mode: 'properties',
                    nodes: [node],
                },
                previousState: {
                    "42/t/t/div": { 'layout': { showAll: true } }, // opens the layout expanded
                },
            }).then(function (sidebar) {

            assert.equal(sidebar.$('.o_web_studio_width:visible').length, 1);

            sidebar.destroy();
            done();
            });
        });

        QUnit.test("'Options' tab with widget selection (tOptions) component", function (assert) {
            var done = assert.async();
            assert.expect(4);

            var node = {
                context: {
                    'doc': 'x_mymodel',
                },
                node: {
                    attrs: {
                        'data-oe-id': '42',
                        'data-oe-xpath': '/t/t/div',
                        't-field': 'doc.id',
                        't-options-widget': '"text"',
                    },
                    tag: 'span',
                    $nodes: $(),
                },
            };
            studioTestUtils.createSidebar({
                state: {
                    mode: 'properties',
                    nodes: [node],
                },
                widgetsOptions: this.widgetsOptions,
            }).then(function (sidebar) {

            assert.containsOnce(sidebar, '.o_web_studio_tfield_fieldexpression',
                "the t-field component should be displayed");
            assert.containsOnce(sidebar, '.o_web_studio_toption_widget',
                "the t-options component should be displayed");
            assert.strictEqual(sidebar.$('.o_web_studio_toption_widget select').text().replace(/\s/g, ''), "imageintegertext",
                "all widgets should be selectable");
            assert.strictEqual(sidebar.$('.o_web_studio_toption_widget select').val(), "text",
                "the correct widget should be selected");

            sidebar.destroy();
            done();
            });
        });

        QUnit.test("'Options' tab with FieldSelector does not flicker", async function (assert) {
            assert.expect(3);
            var def = testUtils.makeTestPromise();

            var node = {
                context: {
                    'doc': 'x_mymodel',
                },
                node: {
                    attrs: {
                        'data-oe-id': '42',
                        'data-oe-xpath': '/t/t/div',
                        't-field': 'doc.id',
                        't-options-widget': '"text"',
                    },
                    context: {
                        'doc': 'x_mymodel',
                    },
                    tag: 'span',
                    $nodes: $(),
                },
            };
            var sidebarDef = studioTestUtils.createSidebar({
                data: this.data,
                models: {
                    'x_mymodel': 'My Model',
                },
                state: {
                    mode: 'properties',
                    nodes: [node],
                },
                widgetsOptions: this.widgetsOptions,
                mockRPC: function (route, args) {
                    if (args.model === 'x_mymodel' && args.method === 'fields_get') {
                        // Block the 'read' call
                        var result = this._super.apply(this, arguments);
                        return Promise.resolve(def).then(_.constant(result));
                    }
                    return this._super.apply(this, arguments);
                },
            });
            await testUtils.nextTick();
            assert.strictEqual($('.o_web_studio_tfield_fieldexpression').length, 0,
                "the sidebar should wait its components to be rendered before its insertion");

            // release the fields_get
            def.resolve();
            var sidebar = await sidebarDef;
            await testUtils.nextTick();
            assert.strictEqual($('.o_web_studio_tfield_fieldexpression').length, 1,
                "the t-field component should be displayed");
            assert.strictEqual(sidebar.$('.o_web_studio_tfield_fieldexpression .o_field_selector_value').text().replace(/\s/g, ''),
                "doc(MyModel)ID",
                "the field chain should be correctly displayed");

            sidebar.destroy();
        });

        QUnit.test('Various layout changes', function (assert) {
            var done = assert.async();
            // this test is a combinaison of multiple tests, to avoid copy
            // pasting multiple times de sidebar create/intercept/destroy

            var layoutChangeNode = {
                attrs: {
                    'data-oe-id': '99',
                    'data-oe-xpath': '/t/t/div',
                },
                tag: 'div',
                $nodes: $(),
            };
            var layoutChangeTextNode = {
                attrs: {
                    'data-oe-id': '99',
                    'data-oe-xpath': '/t/t/span',
                },
                tag: 'span',
                $nodes: $(),
            };
            var nodeWithAllLayoutPropertiesSet = {
                tag: "div",
                attrs: {
                    //width: "1",
                    style: "margin-top:2px;width:1px;margin-right:3px;margin-bottom:4px;margin-left:5px;",
                    class: "o_bold o_italic h3 bg-gamma text-beta o_underline",
                    'data-oe-id': '99',
                    'data-oe-xpath': '/t/t/div',
                },
                $nodes: $(),
            };

            var nodeWithAllLayoutPropertiesFontAndBackgroundSet = {
                tag: "div",
                attrs: {
                    //width: "1",
                    style: "margin-top:2px;margin-right:3px;width:1px;margin-bottom:4px;margin-left:5px;background-color:#00FF00;color:#00FF00",
                    class: "o_bold o_italic h3 o_underline",
                    'data-oe-id': '99',
                    'data-oe-xpath': '/t/t/div',
                },
                $nodes: $(),
            };
            var layoutChangesOperations = [
                {
                testName: "add a margin top in pixels",
                nodeToUse: layoutChangeNode,
                eventToTrigger: "change",
                sidebarOperationInputSelector: '.o_web_studio_margin [data-margin="margin-top"]',
                valueToPut: "42",
                expectedRPC: {
                    inheritance: [{
                        content: "<attribute name=\"style\" separator=\";\" add=\"margin-top:42px\"/>",
                        position: "attributes",
                        view_id: 99,
                        xpath: "/t/t/div"
                    }]
                }
                }, {
                    testName: "add a margin bottom in pixels",
                    nodeToUse: layoutChangeNode,
                    eventToTrigger: "change",
                    sidebarOperationInputSelector: '.o_web_studio_margin [data-margin="margin-bottom"]',
                    valueToPut: "42",
                    expectedRPC: {
                        inheritance: [{
                            content: "<attribute name=\"style\" separator=\";\" add=\"margin-bottom:42px\"/>",
                            position: "attributes",
                            view_id: 99,
                            xpath: "/t/t/div"
                        }]
                    }
                }, {
                    testName: "add a margin left in pixels",
                    nodeToUse: layoutChangeNode,
                    eventToTrigger: "change",
                    sidebarOperationInputSelector: '.o_web_studio_margin [data-margin="margin-left"]',
                    valueToPut: "42",
                    expectedRPC: {
                        inheritance: [{
                            content: "<attribute name=\"style\" separator=\";\" add=\"margin-left:42px\"/>",
                            position: "attributes",
                            view_id: 99,
                            xpath: "/t/t/div"
                        }]
                    }
                }, {
                    testName: "add a margin right in pixels",
                    nodeToUse: layoutChangeNode,
                    eventToTrigger: "change",
                    sidebarOperationInputSelector: '.o_web_studio_margin [data-margin="margin-right"]',
                    valueToPut: "42",
                    expectedRPC: {
                        inheritance: [{
                            content: "<attribute name=\"style\" separator=\";\" add=\"margin-right:42px\"/>",
                            position: "attributes",
                            view_id: 99,
                            xpath: "/t/t/div"
                        }]
                    }
                }, {
                    testName: "add a width",
                    nodeToUse: layoutChangeNode,
                    eventToTrigger: "change",
                    sidebarOperationInputSelector: '.o_web_studio_width input',
                    valueToPut: "42",
                    expectedRPC: {
                        inheritance: [{
                            content: "<attribute name=\"style\" separator=\";\" add=\"width:42px\"/>",
                            position: "attributes",
                            view_id: 99,
                            xpath: "/t/t/div"
                        }]
                    }
                }, {
                    testName: "add a width on a text",
                    nodeToUse: layoutChangeTextNode,
                    eventToTrigger: "change",
                    sidebarOperationInputSelector: '.o_web_studio_width input',
                    valueToPut: "42",
                    expectedRPC: {
                        inheritance: [{
                            content: "<attribute name=\"style\" separator=\";\" add=\"width:42px;display:inline-block\"/>",
                            position: "attributes",
                            view_id: 99,
                            xpath: "/t/t/span"
                        }]
                    }
                }, {
                    testName: "add a class",
                    nodeToUse: layoutChangeNode,
                    eventToTrigger: "change",
                    sidebarOperationInputSelector: '.o_web_studio_classes input',
                    valueToPut: "new_class",
                    expectedRPC: {
                        new_attrs: {
                        class: "new_class"
                        },
                        type: "attributes",
                    },
                }, {
                    testName: "set the heading level",
                    nodeToUse: layoutChangeNode,
                    eventToTrigger: "click",
                    sidebarOperationInputSelector: '.o_web_studio_font_size .dropdown-item-text[data-value="h3"]',
                    expectedRPC: {
                        inheritance: [{
                            content: "<attribute name=\"class\" separator=\" \" add=\"h3\"/>",
                            position: "attributes",
                            view_id: 99,
                            xpath: "/t/t/div"
                        }]
                    },
                }, {
                    testName: "set the background color to a theme color",
                    nodeToUse: layoutChangeNode,
                    eventToTrigger: "mousedown",
                    sidebarOperationInputSelector: '.o_web_studio_colors .o_web_studio_background_colorpicker button[data-color="gamma"]',
                    expectedRPC: {
                        inheritance: [{
                            content: "<attribute name=\"class\" separator=\" \" add=\"bg-gamma\"/>",
                            position: "attributes",
                            view_id: 99,
                            xpath: "/t/t/div"
                        }]
                    },
                }, {
                    testName: "set the background color to a standard color",
                    nodeToUse: layoutChangeNode,
                    eventToTrigger: "mousedown",
                    sidebarOperationInputSelector: '.o_web_studio_colors .o_web_studio_background_colorpicker button[data-value="#00FF00"]',
                    valueToPut: "h3",
                    expectedRPC: {
                        inheritance: [{
                            content: "<attribute name=\"style\" separator=\";\" add=\"background-color:#00FF00\"/>",
                            position: "attributes",
                            view_id: 99,
                            xpath: "/t/t/div"
                        }]
                    },
                }, {
                    testName: "set the font color to a theme color",
                    nodeToUse: layoutChangeNode,
                    eventToTrigger: "mousedown",
                    sidebarOperationInputSelector: '.o_web_studio_colors .o_web_studio_font_colorpicker button[data-color="gamma"]',
                    expectedRPC: {
                        inheritance: [{
                            content: "<attribute name=\"class\" separator=\" \" add=\"text-gamma\"/>",
                            position: "attributes",
                            view_id: 99,
                            xpath: "/t/t/div"
                        }]
                    },
                }, {
                    testName: "set the font color to a standard color",
                    nodeToUse: layoutChangeNode,
                    eventToTrigger: "mousedown",
                    sidebarOperationInputSelector: '.o_web_studio_colors .o_web_studio_font_colorpicker button[data-value="#00FF00"]',
                    valueToPut: "h3",
                    expectedRPC: {
                        inheritance: [{
                            content: "<attribute name=\"style\" separator=\";\" add=\"color:#00FF00\"/>",
                            position: "attributes",
                            view_id: 99,
                            xpath: "/t/t/div"
                        }]
                    },
                }, {
                    testName: "set the alignment",
                    nodeToUse: layoutChangeNode,
                    eventToTrigger: "click",
                    sidebarOperationInputSelector: '.o_web_studio_text_alignment button[title="right"]',
                    expectedRPC: {
                        inheritance: [{
                            content: "<attribute name=\"class\" separator=\" \" add=\"text-right\"/>",
                            position: "attributes",
                            view_id: 99,
                            xpath: "/t/t/div"
                        }]
                    },
                }, {
                testName: "remove margin top in pixels",
                nodeToUse: nodeWithAllLayoutPropertiesSet,
                eventToTrigger: "change",
                sidebarOperationInputSelector: '.o_web_studio_margin [data-margin="margin-top"]',
                valueToPut: "",
                expectedRPC: {
                    inheritance: [{
                        content: "<attribute name=\"style\" separator=\";\" remove=\"margin-top:2px\"/>",
                        position: "attributes",
                        view_id: 99,
                        xpath: "/t/t/div"
                    }]
                }
                }, {
                    testName: "remove a margin bottom in pixels",
                    nodeToUse: nodeWithAllLayoutPropertiesSet,
                    eventToTrigger: "change",
                    sidebarOperationInputSelector: '.o_web_studio_margin [data-margin="margin-bottom"]',
                    valueToPut: "",
                    expectedRPC: {
                        inheritance: [{
                            content: "<attribute name=\"style\" separator=\";\" remove=\"margin-bottom:4px\"/>",
                            position: "attributes",
                            view_id: 99,
                            xpath: "/t/t/div"
                        }]
                    }
                }, {
                    testName: "remove a margin left in pixels",
                    nodeToUse: nodeWithAllLayoutPropertiesSet,
                    eventToTrigger: "change",
                    sidebarOperationInputSelector: '.o_web_studio_margin [data-margin="margin-left"]',
                    valueToPut: "",
                    expectedRPC: {
                        inheritance: [{
                            content: "<attribute name=\"style\" separator=\";\" remove=\"margin-left:5px\"/>",
                            position: "attributes",
                            view_id: 99,
                            xpath: "/t/t/div"
                        }]
                    }
                }, {
                    testName: "remove a margin right in pixels",
                    nodeToUse: nodeWithAllLayoutPropertiesSet,
                    eventToTrigger: "change",
                    sidebarOperationInputSelector: '.o_web_studio_margin [data-margin="margin-right"]',
                    valueToPut: "",
                    expectedRPC: {
                        inheritance: [{
                            content: "<attribute name=\"style\" separator=\";\" remove=\"margin-right:3px\"/>",
                            position: "attributes",
                            view_id: 99,
                            xpath: "/t/t/div"
                        }]
                    }
                }, {
                    testName: "remove the width",
                    nodeToUse: nodeWithAllLayoutPropertiesSet,
                    eventToTrigger: "change",
                    sidebarOperationInputSelector: '.o_web_studio_width input',
                    valueToPut: "",
                    expectedRPC: {
                        inheritance: [{
                            content: "<attribute name=\"style\" separator=\";\" remove=\"width:1px\"/>",
                            position: "attributes",
                            view_id: 99,
                            xpath: "/t/t/div"
                        }]
                    }
                }, {
                    testName: "remove a class",
                    nodeToUse: nodeWithAllLayoutPropertiesSet,
                    eventToTrigger: "change",
                    sidebarOperationInputSelector: '.o_web_studio_classes input',
                    valueToPut: "o_bold o_italic bg-gamma text-beta o_underline",
                    expectedRPC: {
                        new_attrs: {
                            class: "o_bold o_italic bg-gamma text-beta o_underline"
                        },
                        type: "attributes",
                    },
                },  {
                    testName: "unset the background color to a theme color",
                    nodeToUse: nodeWithAllLayoutPropertiesSet,
                    eventToTrigger: "click",
                    sidebarOperationInputSelector: '.o_web_studio_colors .o_web_studio_background_colorpicker .o_web_studio_reset_color',
                    expectedRPC: {
                        inheritance: [{
                            content: "<attribute name=\"class\" separator=\" \" remove=\"bg-gamma\"/>",
                            position: "attributes",
                            view_id: 99,
                            xpath: "/t/t/div"
                        }]
                    },
                },{
                    testName: "unset the background color to a standard color",
                    nodeToUse: nodeWithAllLayoutPropertiesFontAndBackgroundSet,
                    eventToTrigger: "click",
                    sidebarOperationInputSelector: '.o_web_studio_colors .o_web_studio_background_colorpicker .o_web_studio_reset_color',
                    expectedRPC: {
                        inheritance: [{
                            content: "<attribute name=\"style\" separator=\";\" remove=\"background-color:#00FF00\"/>",
                            position: "attributes",
                            view_id: 99,
                            xpath: "/t/t/div"
                        }]
                    },
                },  {
                    testName: "unset the font color to a theme color",
                    nodeToUse: nodeWithAllLayoutPropertiesSet,
                    eventToTrigger: "click",
                    sidebarOperationInputSelector: '.o_web_studio_colors .o_web_studio_font_colorpicker .o_web_studio_reset_color',
                    expectedRPC: {
                        inheritance: [{
                            content: "<attribute name=\"class\" separator=\" \" remove=\"text-beta\"/>",
                            position: "attributes",
                            view_id: 99,
                            xpath: "/t/t/div"
                        }]
                    },
                }, {
                    testName: "unset the font color to a standard color",
                    nodeToUse: nodeWithAllLayoutPropertiesFontAndBackgroundSet,
                    eventToTrigger: "click",
                    sidebarOperationInputSelector: '.o_web_studio_colors .o_web_studio_font_colorpicker button.o_web_studio_reset_color',
                    expectedRPC: {
                        inheritance: [{
                            content: "<attribute name=\"style\" separator=\";\" remove=\"color:#00FF00\"/>",
                            position: "attributes",
                            view_id: 99,
                            xpath: "/t/t/div"
                        }]
                    },
                },
            ];

            // there is one assert by operation
            assert.expect(layoutChangesOperations.length);

            var initialDebugMode = odoo.debug;
            // show 'class' in the sidebar
            odoo.debug = true;

            var defs = [];

            function poll (changeOperation) {
                var node = {
                    node: changeOperation.nodeToUse,
                };
                studioTestUtils.createSidebar({
                    state: {
                        mode: 'properties',
                        nodes: [node],
                    },
                    previousState: {
                        "99/t/t/div": { 'layout': { showAll: true } }, // opens the layout expanded
                    },
                }).then(function (sidebar) {
                    testUtils.mock.intercept(sidebar, 'view_change', function (ev) {
                        assert.deepEqual(ev.data.operation, changeOperation.expectedRPC, changeOperation.testName);
                    });
                    sidebar.$(changeOperation.sidebarOperationInputSelector)
                        .val(changeOperation.valueToPut)
                        .trigger(changeOperation.eventToTrigger);
                    sidebar.destroy();
                }).then(function () {
                    if (layoutChangesOperations.length) {
                        poll(layoutChangesOperations.shift());
                    } else {
                        odoo.debug = initialDebugMode;
                        done();
                    }
                });
            }
            poll(layoutChangesOperations.shift());

        });
    });

});

});
