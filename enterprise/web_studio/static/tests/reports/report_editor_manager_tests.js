odoo.define('web_studio.ReportEditorManager_tests', function (require) {
"use strict";

var ace = require('web_editor.ace');
var concurrency = require('web.concurrency');
var config = require('web.config');
var MediaDialog = require('wysiwyg.widgets.MediaDialog');
var NotificationService = require('web.NotificationService');
var testUtils = require('web.test_utils');
var testUtilsDom = require('web.test_utils_dom');
var studioTestUtils = require('web_studio.testUtils');
var session = require('web.session');

function getFloatSizeFromPropertyInPixels($element, propertyName) {
    var size = $element.css(propertyName);
    size = size.slice(0, size.length - 2); // remove the 'px' at the end
    return parseFloat(size);
}

function mmToPx(size) {
    return size * 3.7795275591;
};

/**
 * Some tests need the style assets inside the iframe, mainly to correctly
 * display the hooks (the hooks sizes are taken into account to decide which
 * ones are the closest ones). This function loads the iframe assets
 * (server-side) and insert them inside the corresponding test template[0] HTML.
 *
 * As a server-side call needs to be done before executing the test, this
 * function wraps the original function.
 *
 * **Warning** only use this function when it's really needed as it's quite
 * expensive.
 */
var loadIframeCss = function (callback) {
    return function WrapLoadIframeCss(assert) {
        var self = this;
        var done = assert.async();
        if (loadIframeCss.assets) {
            var html = self.templates[0].arch.replace('<head/>', loadIframeCss.head);
            self.templates[0].arch = html;
            return callback.call(self, assert, done);
        }

        session.rpc('/web_studio/edit_report/test_load_assets').then(function (assets) {
            loadIframeCss.assets = assets;
            loadIframeCss.head = '<head>';
            loadIframeCss.head += _.map(loadIframeCss.assets.css, function (cssCode, cssFileName) {
                cssCode = cssCode
                    .replace(/\\/g, "\\\\")
                    .replace(/&/g, "&amp;")
                    .replace(/</g, "&lt;")
                    .replace(/>/g, "&gt;")
                    .replace(/"/g, "&quot;")
                    .replace(/'/g, "&#039;")
                    .replace(/}/g, "}\n");

                var style = '<style data-href="' + cssFileName + '">\n' + cssCode + '\n</style>';
                var htmlForValidation = '<html><head>' + style + '</head><body></body></html>';
                var xmlDoc = new DOMParser().parseFromString(htmlForValidation, "text/xml");
                if ($('parsererror', xmlDoc).length) {
                    var error = $('div', xmlDoc).text();
                    throw new Error(error);
                }
                return style;
            }).join('\n');
            loadIframeCss.head += '</head>';

            var html = self.templates[0].arch.replace('<head/>', loadIframeCss.head);
            self.templates[0].arch = html;
            return callback.call(self, assert, done);
        });
    };
};


QUnit.module('Studio', {}, function () {

QUnit.module('ReportEditorManager', {
    beforeEach: function () {
        this.models = {
            'model.test': 'Model Test',
            'model.test.child': 'Model Test Child',
        };
        this.data = {
            'model.test': {
                fields: {
                    name: {string: "Name", type: "char"},
                    child: {string: "Child", type: 'many2one', relation: 'model.test.child', searchable: true},
                    child_bis: {string: "Child Bis", type: 'many2one', relation: 'model.test.child', searchable: true},
                    children: {string: "Children", type: 'many2many', relation: 'model.test.child', searchable: true},
                    attachment_ids: {string: "Attachments", type: 'one2many', relation: 'ir.attachment', searchable: true},
                },
                records: [],
            },
            'model.test.child': {
                fields: {
                    name: { string: "Name", type: "char"},
                    grandchild: {string: "Grandchild", type: 'many2one', relation: 'model.test.grandchild', searchable: true},

                },
                records: [],
            },
            'model.test.grandchild': {
                fields: {
                    name: { string: "Name", type: "char"},
                },
                records: [],
            },
            'ir.attachment': {
                fields: {
                    name: {string: "Name", type: "char"},
                    mimetype: {string: "mimetype", type: "char"},
                    checksum: {string: "checksum", type: "char"},
                    url: {string: "url", type: "char"},
                    image_src: {string: "url", type: "char"},
                    type: {string: "type", type: "char"},
                    res_id: {string: "resID", type: "integer"},
                    res_model: {string: "model", type: "char"},
                    access_token: {string: "access_token", type: "char"},
                },
                records: [{
                    access_token: "token",
                    checksum: "checksum",
                    id: 3480,
                    mimetype: "image/png",
                    name: "joes_garage.jpeg",
                    res_id: 0,
                    res_model: "ir.ui.view",
                    type: "binary",
                    url: "/web/static/joes_garage.png",
                    image_src: "/web/static/joes_garage.png",
                }],
            },
        };
        this.templates = [{
            key: 'template0',
            view_id: 42,
            arch:
                '<kikou>' +
                    '<t t-name="template0">' +
                        '<html>\n' +
                            '<head/>\n' +
                            '<body>' +
                                '<div id="wrapwrap">' +
                                    '<main>' +
                                        '<div class="page">' +
                                            '<t t-call="template1"/>' +
                                        '</div>' +
                                    '</main>' +
                                '</div>' +
                            '</body>\n' +
                        '</html>' +
                    '</t>' +
                '</kikou>',
        }];
    }
}, function () {

    QUnit.test('empty editor rendering', async function (assert) {
        assert.expect(5);

        this.templates.push({
            key: 'template1',
            view_id: 55,
            arch:
                '<kikou>' +
                    '<t t-name="template1">' +
                    '</t>' +
                '</kikou>',
        });

        var rem = await studioTestUtils.createReportEditorManager({
            env: {
                modelName: 'kikou',
                ids: [42, 43],
                currentId: 42,
            },
            report: {
                report_name: 'awesome_report',
            },
            reportHTML: studioTestUtils.getReportHTML(this.templates),
            reportViews: studioTestUtils.getReportViews(this.templates),
            mockRPC: function (route, args) {
                if (route === '/web_studio/print_report') {
                    assert.strictEqual(args.report_name, 'awesome_report',
                        "the correct report should be printed");
                    assert.strictEqual(args.record_id, 42,
                        "the report should be printed with the correct record");
                    return Promise.resolve();
                }
                return this._super.apply(this, arguments);
            },
        });

        await rem.editorIframeDef.then(async function () {
            assert.containsOnce(rem, '.o_web_studio_sidebar',
                "a sidebar should be rendered");

            // no content helper
            assert.strictEqual(rem.$('iframe').contents().find('.page .o_no_content_helper').length, 1,
                "the iframe should be rendered with a no content helper");
            testUtils.mock.intercept(rem, 'node_clicked', function () {
                throw new Error("The no content helper shouldn't be clickable.");
            });
            await testUtils.dom.click(rem.$('iframe').contents().find('.page .o_no_content_helper'));

            // printing the report
            assert.containsOnce(rem, '.o_web_studio_report_print',
                "it should be possible to print the report");
            await testUtils.dom.click(rem.$('.o_web_studio_report_print'));

            rem.destroy();
        });
    });

    QUnit.test('basic editor rendering', async function (assert) {
        assert.expect(12);

        this.templates.push({
            key: 'template1',
            view_id: 55,
            arch:
                '<kikou>' +
                    '<t t-name="template1">' +
                        '<div class="class1">' +
                            '<span>First span</span>' +
                        '</div>' +
                        '<t t-call="template2"/>' +
                    '</t>' +
                '</kikou>',
        });
        this.templates.push({
            key: 'template2',
            view_id: 56,
            arch:
                '<kikou>' +
                    '<t t-name="template2">' +
                        '<span>Second span</span>' +
                    '</t>' +
                '</kikou>'
        });

        var rem = await studioTestUtils.createReportEditorManager({
            data: this.data,
            models: this.models,
            env: {
                modelName: 'kikou',
                ids: [42, 43],
                currentId: 42,
            },
            report: {
                report_name: 'awesome_report',
            },
            reportHTML: studioTestUtils.getReportHTML(this.templates),
            reportViews: studioTestUtils.getReportViews(this.templates),
            reportMainViewID: 42,
        });

        await rem.editorIframeDef.then(async function () {
            assert.containsOnce(rem, '.o_web_studio_sidebar',
                "a sidebar should be rendered");
            assert.strictEqual(rem.$('iframe').contents().find('.page').text(),"First spanSecond span",
                "the iframe should be rendered");

            var iframeContainerwidth = getFloatSizeFromPropertyInPixels(rem.$('.o_web_studio_report_iframe_container'),'width');
            assert.ok(Math.abs(iframeContainerwidth - 794) <= 1,"the default width should be A4 (794px = 210mm) +/- 1px");

            var iframeMinHeight = getFloatSizeFromPropertyInPixels(rem.$('.o_web_studio_report_iframe_container'), 'min-height');
            var heightDifference  = Math.abs( 1122.52 - iframeMinHeight);
            assert.ok( heightDifference <= 1, "the default height should be A4 (1122.52px = 297mm) at +/- 1 px because of decimals");

            // click to edit a span
            await testUtils.dom.click(rem.$('iframe').contents().find('span:contains(Second)'));

            assert.hasClass(rem.$('iframe').contents().find('span:contains(Second)'),'o_web_studio_report_selected',
                "the corresponding nodes should be selected");
            assert.hasClass(rem.$('.o_web_studio_sidebar .o_web_studio_sidebar_header div[name="options"]'),'active',
                "the sidebar should have been updated");
            assert.containsN(rem, '.o_web_studio_sidebar .o_web_studio_sidebar_content .card', 2,
                "there should be 2 cards in the sidebar");

            // click to edit first span
            await testUtils.dom.click(rem.$('iframe').contents().find('span:contains(First span)'));
            assert.hasClass(rem.$('iframe').contents().find('span:contains(First span)'),'o_web_studio_report_selected',
                "the corresponding nodes should be selected");
            assert.containsN(rem, '.o_web_studio_sidebar .o_web_studio_sidebar_content .card', 3,
                "there should be 3 cards in the sidebar");
            // click 2nd card on "Options" tab
            await testUtils.dom.click(rem.$('.o_web_studio_sidebar .o_web_studio_sidebar_content_properties div.card:eq(1)'));
            assert.hasClass(rem.$('iframe').contents().find('div.class1'), 'o_web_studio_report_selected',
                "the corresponding nodes should be selected");
            assert.doesNotHaveClass(rem.$('iframe').contents().find('span:contains(First span)'), 'o_web_studio_report_selected',
                "the corresponding node should not be selected now");

            // click on "Options" (shouldn't do anything)
            await testUtils.dom.click(rem.$('.o_web_studio_sidebar .o_web_studio_sidebar_header div[name="options"]'));
            assert.containsN(rem, '.o_web_studio_sidebar .o_web_studio_sidebar_content .card', 3,
                "there should still be 3 cards in the sidebar");

            rem.destroy();
        });
    });

    QUnit.test('editor rendering with paperformat', async function (assert) {
        var done = assert.async();
        assert.expect(2);

        this.templates.push({
            key: 'template1',
            view_id: 55,
            arch:
                '<kikou>' +
                    '<t t-name="template1">' +
                        '<div class="class1">' +
                            '<span>First span</span>' +
                        '</div>' +
                    '</t>' +
                '</kikou>',
        });

        var rem = await studioTestUtils.createReportEditorManager({
            data: this.data,
            models: this.models,
            env: {
                modelName: 'kikou',
                ids: [42, 43],
                currentId: 42,
            },
            paperFormat: {
                print_page_width: 200,
                print_page_height: 400,
            },
            report: {
                report_name: 'awesome_report',
            },
            reportHTML: studioTestUtils.getReportHTML(this.templates),
            reportViews: studioTestUtils.getReportViews(this.templates),
            reportMainViewID: 42,
        });

        await rem.editorIframeDef.then(async function () {
            var iframeWidth = getFloatSizeFromPropertyInPixels(rem.$('.o_web_studio_report_iframe_container'),'width');
            assert.ok(Math.abs(iframeWidth-756) <= 1,"the width should be taken from the paperFormat +/- 1px");

            var iframeHeight = getFloatSizeFromPropertyInPixels(rem.$('.o_web_studio_report_iframe_container'), 'min-height');
            var heightDifference  = Math.abs( 1511.81 - iframeHeight) ;
            assert.ok(heightDifference <= 1, "the height should be taken from the paperFormat +/- 1 px");

            rem.destroy();
            done();
        });
    });

    QUnit.test('preview zoomed by paperformat DPI or smart-shrinking', async function (assert) {
        assert.expect(7);

        this.templates = [{
            key: 'template0',
            view_id: 55,
            arch:
                '<kikou>' +
                    '<t t-name="template0">' +
                        '<html>\n' +
                            '<head/>\n' +
                            '<body style="margin:0; margin-left: 5px; margin-right: 10px;">' +
                                '<div id="wrapwrap">' +
                                    '<main>' +
                                        '<div class="header"><div style="width:2000px">this is</div></div>' +
                                        '<div class="article"><div style="width:100px">a test</div></div>' +
                                        '<div class="footer"><div style="width:3000px">without hello world</div></div>' +
                                    '</main>' +
                                '</div>' +
                            '</body>\n' +
                        '</html>' +
                    '</t>' +
                '</kikou>',
        }];

        var paperFormat = {
            print_page_width: 200,
            print_page_height: 400,
            margin_top: 10,
            margin_left: 30,
            margin_right: 20,
            header_spacing: 5,
            dpi: 200,
        };

        var topMargin = mmToPx(paperFormat.margin_top - paperFormat.header_spacing);
        var leftMargin = mmToPx(paperFormat.margin_left);
        var rightMargin = mmToPx(paperFormat.margin_right);
        var width = mmToPx(paperFormat.print_page_width);

        // paper width minus paperformat margins and content container margins
        var contentWidth = width - leftMargin - rightMargin - 5 - 10;

        var rem = await studioTestUtils.createReportEditorManager({
            data: this.data,
            models: this.models,
            env: {
                modelName: 'kikou',
                ids: [42, 43],
                currentId: 42,
            },
            paperFormat: paperFormat,
            report: {
                report_name: 'awesome_report',
            },
            reportHTML: studioTestUtils.getReportHTML(this.templates),
            reportViews: studioTestUtils.getReportViews(this.templates),
            reportMainViewID: 55,
        });

        var containerStyles = rem.editor.$iframe.parent().css([
            'paddingTop', 'paddingLeft', 'paddingRight', 'width'
        ]);

        var diffTopMargin = Math.abs(topMargin - parseFloat(containerStyles.paddingTop));
        assert.ok(diffTopMargin < 1, "preview top margin same than paperformat");

        var diffLeftMargin = Math.abs(leftMargin - parseFloat(containerStyles.paddingLeft));
        assert.ok(diffLeftMargin < 1, "preview left margin same than paperformat");

        var diffRightMargin = Math.abs(rightMargin - parseFloat(containerStyles.paddingRight));
        assert.ok(diffRightMargin < 1, "preview right margin same than paperformat");

        var diffWidth = Math.abs(width - parseFloat(containerStyles.width));
        assert.ok(diffWidth < 1, "preview width same than paperformat");

        // end test if zoom not supported by browser (currently firefox)
        if ($('<div />').css({zoom: 0.5}).css('zoom') === undefined) {
            assert.ok(true, "zoom not supported by browser");
            assert.ok(true, "zoom not supported by browser");
            assert.ok(true, "zoom not supported by browser");
            rem.destroy();
            return;
        }

        // test that overflowing sections are shrinked and other fit paper DPI

        var headerZoom = rem.editor.$content.find('.header').css('zoom');
        var diffHeaderZoom = Math.abs(headerZoom - contentWidth / 2000);
        assert.ok(diffHeaderZoom < 0.01, "zoom value shrink header content to fit");

        var bodyZoom = rem.editor.$content.find('.article').css('zoom');
        var diffContentZoom = Math.abs(bodyZoom - 96 / paperFormat.dpi);
        assert.ok(diffContentZoom < 0.01, "zoom value to have body content match DPI");

        var footerZoom = rem.editor.$content.find('.footer').css('zoom');
        var diffFooterZoom = Math.abs(footerZoom - contentWidth / 3000);
        assert.ok(diffFooterZoom < 0.01, "zoom value shrink footer content to fit");

        rem.destroy();
    });

    QUnit.test('use pager', async function (assert) {
        assert.expect(6);
        var self = this;

        this.templates.push({
            key: 'template1',
            view_id: 55,
            arch:
                '<kikou>' +
                    '<t t-name="template1">' +
                        '<div class="class1">' +
                            '<span>First span</span>' +
                        '</div>' +
                    '</t>' +
                '</kikou>',
        });

        var rem = await studioTestUtils.createReportEditorManager({
            data: this.data,
            models: this.models,
            env: {
                modelName: 'kikou',
                ids: [42, 43],
                currentId: 42,
            },
            report: {
                report_name: 'awesome_report',
            },
            reportHTML: studioTestUtils.getReportHTML(this.templates),
            reportViews: studioTestUtils.getReportViews(this.templates),
            reportMainViewID: 42,
            mockRPC: function (route, args) {
                if (route === '/web_studio/get_report_views') {
                    assert.strictEqual(args.record_id, 43,
                        "the record id should be correctly set");
                    self.templates[1].arch = '<kikou>' +
                        '<t t-name="template1">' +
                            '<div class="row">' +
                                '<div class="col-12">' +
                                    '<span>hello</span>' +
                                '</div>' +
                            '</div>' +
                        '</t>' +
                    '</kikou>';
                    return Promise.resolve({
                        report_html: studioTestUtils.getReportHTML(self.templates),
                        views: studioTestUtils.getReportViews(self.templates),
                    });
                }
                return this._super.apply(this, arguments);
            },
        });

        await rem.editorIframeDef.then(async function () {
            assert.strictEqual(rem.$('iframe').contents().find('.page').text(), "First span",
                "the iframe should be rendered");
            assert.containsOnce(rem, '.o_web_studio_report_pager',
                "there should be a pager");
            assert.strictEqual(rem.$('.o_web_studio_report_pager').text().trim(), "1 / 2",
                "the pager should be correctly rendered");

            // click to switch between records
            await testUtils.dom.click(rem.$('.o_web_studio_report_pager .o_pager_next'));

            assert.strictEqual(rem.$('iframe').contents().find('.page').text(), "hello",
                "the iframe should be updated");
            assert.strictEqual(rem.$('.o_web_studio_report_pager').text().trim(), "2 / 2",
                "the pager should be correctly updated");

            rem.destroy();
        });
    });

    QUnit.test('components edition', async function (assert) {
        assert.expect(7);

        var self = this;
        this.templates.push({
            key: 'template1',
            view_id: 55,
            arch:
                '<kikou>' +
                    '<t t-name="template1">' +
                        '<div class="row">' +
                            '<div class="col-12">' +
                                '<span>First span</span>' +
                            '</div>' +
                        '</div>' +
                    '</t>' +
                '</kikou>',
        });

        var rem = await studioTestUtils.createReportEditorManager({
            data: this.data,
            models: this.models,
            env: {
                modelName: 'kikou',
                ids: [42, 43],
                currentId: 42,
            },
            report: {
                report_name: 'awesome_report',
            },
            reportHTML: studioTestUtils.getReportHTML(this.templates),
            reportViews: studioTestUtils.getReportViews(this.templates),
            reportMainViewID: 42,
            mockRPC: function (route, args) {
                if (route === '/web_studio/edit_report_view') {
                    assert.deepEqual(args, {
                        context: {},
                        operations: [{
                            context: {},
                            inheritance: [{
                                content: "<span>hello</span>",
                                position: "replace",
                                view_id: 55,
                                xpath: "/t/div/div/span"
                            }],
                            view_id: 55,
                            xpath: '/t/div/div/span',
                        }],
                        record_id: 42,
                        report_name: "awesome_report",
                        report_views: studioTestUtils.getReportViews(self.templates),
                    });

                    // directly apply the operation on the view
                    self.templates[1].arch = '<kikou>' +
                        '<t t-name="template1">' +
                            '<div class="row">' +
                                '<div class="col-12">' +
                                    '<span>hello</span>' +
                                '</div>' +
                            '</div>' +
                        '</t>' +
                    '</kikou>';

                    return Promise.resolve({
                        report_html: studioTestUtils.getReportHTML(self.templates),
                        views: studioTestUtils.getReportViews(self.templates),
                    });
                }
                return this._super.apply(this, arguments);
            },
        });

        await rem.editorIframeDef
        assert.strictEqual(rem.$('iframe').contents().find('.page').text(),"First span",
            "the iframe should be rendered");

        // click to edit a span
        await testUtils.dom.click(rem.$('iframe').contents().find('span:contains(First)'));

        var $textarea = rem.$('.o_web_studio_sidebar .o_web_studio_active textarea[name="text"]');
        assert.strictEqual($textarea.length, 1,
            "there should be a textarea to edit the node text");
        assert.strictEqual($textarea.val(), "First span",
            "the Text component should be correctly set");

        // change the text (should trigger the report edition)
        await testUtils.fields.editInput($textarea, "hello");

        assert.strictEqual(rem.$('iframe').contents().find('.page').text(),"hello",
            "the iframe should have been updated");
        var $newTextarea = rem.$('.o_web_studio_sidebar .o_web_studio_active textarea[name="text"]');
        assert.strictEqual($newTextarea.length, 1,
            "there should still be a textarea to edit the node text");
        assert.strictEqual($newTextarea.val(), "hello",
            "the Text component should have been updated");

        rem.destroy();
    });

    QUnit.test('components edition 2', async function (assert) {
        var done = assert.async();
        assert.expect(6);

        this.templates.push({
            key: 'template1',
            view_id: 55,
            arch:
                '<kikou>' +
                    '<t t-name="template1">' +
                        '<div class="row">' +
                            '<div class="col-12">' +
                                '<span>First span</span>' +
                            '</div>' +
                        '</div>' +
                    '</t>' +
                '</kikou>',
        });

        var rem = await studioTestUtils.createReportEditorManager({
            data: this.data,
            models: this.models,
            env: {
                modelName: 'kikou',
                ids: [42, 43],
                currentId: 42,
            },
            report: {
                report_name: 'awesome_report',
            },
            reportHTML: studioTestUtils.getReportHTML(this.templates),
            reportViews: studioTestUtils.getReportViews(this.templates),
            reportMainViewID: 42,
        });

        await rem.editorIframeDef.then(async function () {
            assert.hasAttrValue(rem.$('.o_web_studio_sidebar_header .active'), 'name', 'new',
                "the 'Add' tab should be active");
            assert.strictEqual(rem.$('iframe').contents().find('.o_web_studio_report_selected').length, 0,
                "there should be no selected node");

            // click to edit a span
            await testUtils.dom.click(rem.$('iframe').contents().find('span:contains(First)'));
            assert.hasAttrValue(rem.$('.o_web_studio_sidebar_header .active'), 'name', 'options',
                "the 'Options' tab should be active");
            assert.strictEqual(rem.$('iframe').contents().find('.o_web_studio_report_selected').length, 1,
                "the span should be selected");

            // switch tab
            await testUtils.dom.click(rem.$('.o_web_studio_sidebar_header [name="report"]'));
            assert.hasAttrValue(rem.$('.o_web_studio_sidebar_header .active'), 'name', 'report',
                "the 'Report' tab should be active");
            assert.strictEqual(rem.$('iframe').contents().find('.o_web_studio_report_selected').length, 0,
                "there should be no selected node anymore");

            rem.destroy();
            done();
        });
    });

    QUnit.test('remove components - when no node is available to select, the add tab is activated', async function (assert) {
        var self = this;
        assert.expect(1);

        this.templates.push({
            key: 'template1',
            view_id: 55,
            arch:
                '<kikou>' +
                    '<t t-name="template1">' +
                        '<div class="row">' +
                            '<div class="col-12">' +
                                '<span>First span</span>' +
                            '</div>' +
                        '</div>' +
                    '</t>' +
                '</kikou>',
        });

        var rem = await studioTestUtils.createReportEditorManager({
            env: {
                modelName: 'kikou',
                ids: [42, 43],
                currentId: 42,
            },
            report: { },
            reportHTML: studioTestUtils.getReportHTML(this.templates),
            reportViews: studioTestUtils.getReportViews(this.templates),
            reportMainViewID: 42,
            mockRPC: function (route, args) {
                if (route === '/web_studio/edit_report_view') {
                    self.templates[1].arch = '<kikou>' +
                        '<t t-name="template1">' +
                        '</t>' +
                    '</kikou>';
                    return Promise.resolve({
                        report_html: studioTestUtils.getReportHTML(self.templates),
                        views: studioTestUtils.getReportViews(self.templates),
                    });
                }
                return this._super.apply(this, arguments);
            },
        });

        await rem.editorIframeDef.then(async function () {
            // click to edit a span
            await testUtils.dom.click(rem.$('iframe').contents().find('span:contains(First)'));

            // remove the span from the dom
            await testUtils.dom.click(rem.$('.o_web_studio_active .o_web_studio_remove'));
            await testUtils.dom.click($('.modal-content .btn-primary'));
            assert.hasAttrValue(rem.$('.o_web_studio_sidebar_header .active'), 'name', 'new',
                "after the remove, 'Add' tab should be active");

            rem.destroy();
        });
    });

    QUnit.test('drag & drop text component', async function (assert) {
        assert.expect(1);

        var self = this;
        this.templates.push({
            key: 'template1',
            view_id: 55,
            arch:
                '<kikou>' +
                    '<t t-name="template1">' +
                        '<div class="row">' +
                            '<div class="col-12">' +
                                '<span>First span</span>' +
                            '</div>' +
                        '</div>' +
                    '</t>' +
                '</kikou>',
        });

        var rem = await studioTestUtils.createReportEditorManager({
            data: this.data,
            models: this.models,
            env: {
                modelName: 'kikou',
                ids: [42, 43],
                currentId: 42,
            },
            report: {
                report_name: 'awesome_report',
            },
            reportHTML: studioTestUtils.getReportHTML(this.templates),
            reportViews: studioTestUtils.getReportViews(this.templates),
            reportMainViewID: 42,
            mockRPC: function (route, args) {
                if (route === '/web_studio/edit_report_view') {
                    assert.deepEqual(args, {
                        context: {},
                        operations: [{
                            context: {},
                            inheritance: [{
                                content: "<span>New Text Block</span>",
                                position: "after",
                                view_id: 55,
                                xpath: "/t/div/div/span"
                            }],
                            position: "after",
                            type: "add",
                            view_id: 55,
                            xpath: "/t/div/div/span"
                        }],
                        record_id: 42,
                        report_name: "awesome_report",
                        report_views: studioTestUtils.getReportViews(self.templates),
                    });

                    return Promise.resolve({
                        report_html: studioTestUtils.getReportHTML(self.templates),
                        views: studioTestUtils.getReportViews(self.templates),
                    });
                }
                return this._super.apply(this, arguments);
            },
        });

        await rem.editorIframeDef.then(async function () {
            await testUtils.dom.click(rem.$('.o_web_studio_sidebar .o_web_studio_sidebar_header div[name="new"]'));

            // drag and drop a Text component, which should trigger a view edition
            var $text = rem.$('.o_web_studio_sidebar .o_web_studio_field_type_container:eq(1) .o_web_studio_component:contains(Text)');
            await testUtils.dom.dragAndDrop($text, rem.$('iframe').contents().find('span:contains(First span)'));

            rem.destroy();
        });
    });

    QUnit.test('drag & drop text component in existing col', loadIframeCss(async function (assert, done) {
        assert.expect(1);

        var self = this;
        this.templates.push({
            key: 'template1',
            view_id: 55,
            arch:
                '<kikou>' +
                    '<t t-name="template1">' +
                        '<div class="row">' +
                            '<div class="col-6"/>' +
                            '<div class="col-6"/>' +
                        '</div>' +
                    '</t>' +
                '</kikou>',
        });

        var rem = await studioTestUtils.createReportEditorManager({
            env: {
                modelName: 'kikou',
                ids: [42, 43],
                currentId: 42,
            },
            report: {},
            reportHTML: studioTestUtils.getReportHTML(this.templates),
            reportViews: studioTestUtils.getReportViews(this.templates),
            reportMainViewID: 42,
            mockRPC: function (route, args) {
                if (route === '/web_studio/edit_report_view') {
                    assert.deepEqual(args.operations, [{
                        context: {},
                        inheritance: [{
                            content: "<span>New Text Block</span>",
                            position: "inside",
                            view_id: 55,
                            xpath: "/t/div/div[1]"
                        }],
                        position: "inside",
                        type: "add",
                        view_id: 55,
                        xpath: "/t/div/div[1]"
                    }]);

                    return Promise.resolve({
                        report_html: studioTestUtils.getReportHTML(self.templates),
                        views: studioTestUtils.getReportViews(self.templates),
                    });
                }
                return this._super.apply(this, arguments);
            },
        });

        await rem.editorIframeDef.then(async function () {
            await testUtils.dom.click(rem.$('.o_web_studio_sidebar .o_web_studio_sidebar_header div[name="new"]'));

            // drag and drop a Text component, which should trigger a view edition
            var $text = rem.$('.o_web_studio_sidebar .o_web_studio_component:contains(Text):eq(1)');
            await testUtils.dom.dragAndDrop($text, rem.$('iframe').contents().find('.col-6:eq(1)'));

            rem.destroy();
            done();
        });
    }));

    QUnit.test('drag & drop components and cancel', async function (assert) {
        var done = assert.async();
        assert.expect(4);

        this.templates.push({
            key: 'template1',
            view_id: 55,
            arch:
                '<kikou>' +
                    '<t t-name="template1">' +
                        '<div class="row">' +
                            '<div class="col-3">' +
                                '<span>First span</span>' +
                            '</div>' +
                            '<div class="col-3">' +
                            '</div>' +
                        '</div>' +
                    '</t>' +
                '</kikou>',
        });

        var rem = await studioTestUtils.createReportEditorManager({
            data: this.data,
            models: this.models,
            env: {
                modelName: 'kikou',
                ids: [42, 43],
                currentId: 42,
            },
            report: {
                report_name: 'awesome_report',
            },
            reportHTML: studioTestUtils.getReportHTML(this.templates),
            reportViews: studioTestUtils.getReportViews(this.templates),
            reportMainViewID: 42,
        });

        await rem.editorIframeDef.then(async function () {
            await testUtils.dom.click(rem.$('.o_web_studio_sidebar .o_web_studio_sidebar_header div[name="new"]'));

            // drag and drop a Text component
            var $text = rem.$('.o_web_studio_sidebar .o_web_studio_component:contains(Field):eq(1)');
            await testUtils.dom.dragAndDrop($text, rem.$('iframe').contents().find('.col-3:last'));
            assert.strictEqual($('.o_web_studio_field_modal').length, 1, "a field modal should be opened");

            // cancel the field selection
            await testUtils.dom.click($('.o_web_studio_field_modal .btn-secondary'));
            assert.strictEqual(rem.$('iframe').contents().find('.o_web_studio_hook').length, 0, "Must cancel the dragAndDrop");

            // drag and drop an Address component
            var $address = rem.$('.o_web_studio_sidebar .o_web_studio_component:contains(Address)');
            await testUtils.dom.dragAndDrop($address, rem.$('iframe').contents().find('.col-3:last'));
            assert.strictEqual($('.o_web_studio_field_modal').length, 1, "a field modal should be opened");

            // cancel the field selection
            await testUtils.dom.click($('.o_web_studio_field_modal .btn-secondary'));
            assert.strictEqual(rem.$('iframe').contents().find('.o_web_studio_hook').length, 0, "Must cancel the dragAndDrop");

            rem.destroy();
            done();
        });
    });

    QUnit.test('drag & drop field block', async function (assert) {
        assert.expect(6);
        var done = assert.async();

        this.templates.push({
            key: 'template1',
            view_id: 55,
            arch:
                '<kikou>' +
                    '<t t-name="template1">' +
                    '</t>' +
                '</kikou>',
        });

        var templateData = {
            dataOeContext: '{"o": "model.test", "docs": "model.test"}'
        };

        var rem = await studioTestUtils.createReportEditorManager({
            data: this.data,
            models: this.models,
            env: {
                modelName: 'kikou',
                ids: [42, 43],
                currentId: 42,
            },
            report: {
                report_name: 'awesome_report',
            },
            reportHTML: studioTestUtils.getReportHTML(this.templates, templateData),
            reportViews: studioTestUtils.getReportViews(this.templates, templateData),
            reportMainViewID: 42,
            mockRPC: function (route, args) {
                if (route === '/web_studio/edit_report_view') {
                    var operation = _.last(args.operations);
                    if (!operation) {
                        // this is to deal with undo operation (which is
                        // triggered after the first promise reject)
                        return Promise.reject();
                    }
                    assert.deepEqual(operation.inheritance[0].content, "<div class='row'><div class='col'><span t-field=\"o.child.name\"></span></div></div>",
                        "the block should be correctly added");
                    return Promise.reject();
                }
                return this._super.apply(this, arguments);
            },
        });

        await rem.editorIframeDef.then(async function () {
            await testUtils.dom.click(rem.$('.o_web_studio_sidebar .o_web_studio_sidebar_header div[name="new"]'));

            var $field = rem.$('.o_web_studio_sidebar .o_web_studio_field_type_container:eq(0) .o_web_studio_component:contains(Field):eq(0)');
            var $target = rem.$('iframe').contents().find('.page');

            // drag and drop a Field component, which should trigger a view edition
            await testUtils.dom.dragAndDrop($field, $target, {position: 'inside'});

            $('.o_web_studio_field_modal .o_field_selector').trigger('focusin');
            await testUtils.nextTick();

            assert.strictEqual($('.o_web_studio_field_modal .o_field_selector_item').text().trim(), "o (Model Test)",
                'Only "o" should be selectable, not "docs"');

            await testUtils.dom.click($('.o_web_studio_field_modal .o_field_selector_item[data-name="o"]'));

            var allAvailableFields = $('.o_web_studio_field_modal .o_field_selector_item').text().trim();

            assert.ok(allAvailableFields.includes('Name'),
                'Char field is present');
            assert.ok(allAvailableFields.includes('Child'),
                'many2one fields are present');

            assert.notOk(allAvailableFields.includes('Children'),
                'many2many fields should not be present');
            assert.notOk(allAvailableFields.includes('Attachments'),
                'one2many fields should not be present');

            await testUtils.dom.click($('.o_web_studio_field_modal .o_field_selector_item[data-name="child"]'));
            await testUtils.dom.click($('.o_web_studio_field_modal .o_field_selector_item[data-name="name"]'));
            await testUtils.dom.click($('.o_web_studio_field_modal .btn-primary'));

            rem.destroy();
            done();
        });
    });

    QUnit.test('drag & drop field in row', loadIframeCss(async function (assert, done) {
        assert.expect(4); // 2 asserts by test

        this.templates.push({
            key: 'template1',
            view_id: 55,
            arch:
                '<kikou>' +
                    '<t t-name="template1">' +
                        '<div class="row">' +
                            '<div class="col-6">' +
                                '<span>Coucou</span>' +
                            '</div>' +
                            '<div class="col-6">' +
                            '</div>' +
                        '</div>' +
                    '</t>' +
                '</kikou>',
        });
        var templateData = {
            docs: [
                {firstname: 'firstname 1', name: 'name 1', product: 'product 1', price: 10, quantity: 1000, total: 10000},
                {firstname: 'firstname 2', name: 'name 2', product: 'product 2', price: 20, quantity: 2000, total: 40000},
                {firstname: 'firstname 3', name: 'name 3', product: 'product 3', price: 30, quantity: 3000, total: 90000}
            ],
            sum: function (list) {
                return list.reduce(function (a, b) {
                    return a + b;
                }, 0);
            },
            dataOeContext: '{"o": "model.test"}'
        };
        templateData.docs.mapped = function (fieldName) {return _.pluck(this, fieldName);};

        var rem = await studioTestUtils.createReportEditorManager({
            data: this.data,
            models: this.models,
            env: {
                modelName: 'kikou',
                ids: [42, 43],
                currentId: 42,
            },
            report: {
                report_name: 'awesome_report',
            },
            reportHTML: studioTestUtils.getReportHTML(this.templates, templateData),
            reportViews: studioTestUtils.getReportViews(this.templates, templateData),
            reportMainViewID: 42,
            mockRPC: function (route, args) {
                if (route === '/web_studio/edit_report_view') {
                    var operation = _.last(args.operations);
                    if (!operation) {
                        // this is to deal with undo operation (which is
                        // triggered after the first promise reject)
                        return Promise.reject();
                    }
                    assert.deepEqual(operation.inheritance, tests[testIndex].inheritance, tests[testIndex].text);
                    return Promise.reject();
                }
                return this._super.apply(this, arguments);
            },
        });

        // create multiple tests to avoid duplicating very similar tests
        var tests = [
            {
                text: "Should select the hook next to the span",
                selector: '.row:first .col-6:eq(0)',
                position: 'center',
                nearestHookNumber: 1,
                inheritance: [{
                    content: '<span t-field="o.child.name"></span>',
                    position: 'after',
                    view_id: 55,
                    xpath: '/t/div/div/span',
                }],
            }, {
                text: "Should select the hook inside the col",
                selector: '.row:first .col-6:eq(1)',
                position: 'bottom',
                nearestHookNumber: 1,
                inheritance: [{
                    content: '<span t-field="o.child.name"></span>',
                    position: 'inside',
                    view_id: 55,
                    xpath: '/t/div/div[1]',
                }],
            },
        ];
        var testIndex = 0;

        await rem.editorIframeDef.then(async function () {
            await testUtils.dom.click(rem.$('.o_web_studio_sidebar .o_web_studio_sidebar_header div[name="new"]'));

            var $field = rem.$('.o_web_studio_sidebar .o_web_studio_field_type_container:eq(1) .o_web_studio_component:contains(Field)');

            for (testIndex; testIndex < tests.length; testIndex++) {
                var test = tests[testIndex];
                var $target = rem.$('iframe').contents().find(test.selector);
                // drag and drop a Field component, which should trigger a view edition
                await testUtils.dom.dragAndDrop($field, $target, {position: test.position});
                var $nearestHook = rem.$('iframe').contents().find('.o_web_studio_nearest_hook');
                assert.strictEqual($nearestHook.length, test.nearestHookNumber, test.text + ' (nearestHook number)');

                $('.o_web_studio_field_modal .o_field_selector').trigger('focusin');
                await testUtils.nextTick();
                await testUtils.dom.click($('.o_web_studio_field_modal .o_field_selector_item[data-name="o"]'));
                await testUtils.dom.click($('.o_web_studio_field_modal .o_field_selector_item[data-name="child"]'));
                await testUtils.dom.click($('.o_web_studio_field_modal .o_field_selector_item[data-name="name"]'));
                await testUtils.dom.click($('.o_web_studio_field_modal .btn-primary'));
            }

            rem.destroy();
            done();
        });
    }));

    QUnit.test('drag & drop field in table', loadIframeCss(async function (assert, done) {
        assert.expect(20);

        this.templates.push({
            key: 'template1',
            view_id: 55,
            arch:
                '<kikou>' +
                    '<t t-name="template1">' +
                        '<table class="table table-sm" style="width: 600px">' +
                            '<thead>' +
                                '<tr>' +
                                    '<th colspan="2"><span>Titre 1</span></th>' +
                                    '<th><span>Titre 2</span></th>' +
                                    '<th colspan="2"><span>Titre 3</span></th>' +
                                    '<th><span>Titre 4</span></th>' +
                                '</tr>' +
                            '</thead>' +
                            '<tbody>' +
                                '<tr t-foreach="docs" t-as="l">' +
                                    '<td width="100px"><span><t t-esc="l.firstname"/></span></td>' +
                                    '<td width="100px"><span><t t-esc="l.name"/></span></td>' +
                                    '<td width="100px"><span><t t-esc="l.product"/></span></td>' +
                                    '<td width="100px"><span><t t-esc="l.price"/></span></td>' +
                                    '<td width="100px"><span><t t-esc="l.quantity"/></span></td>' +
                                    '<td width="100px"><span><t t-esc="l.total"/></span></td>' +
                                '</tr>' +
                                '<tr>' +
                                    '<td/>' +
                                    '<td/>' +
                                    '<td/>' +
                                    '<td class="text-right" colspan="2"><span class="o_bold">Total</span></td>' +
                                    '<td class="text-right"><span class="o_bold"><t t-esc="sum(docs.mapped(\'total\'))"/></span></td>' +
                                '</tr>' +
                            '</tbody>' +
                        '</table>' +
                    '</t>' +
                '</kikou>',
        });
        var templateData = {
            docs: [
                {firstname: 'firstname 1', name: 'name 1', product: 'product 1', price: 10, quantity: 1000, total: 10000},
                {firstname: 'firstname 2', name: 'name 2', product: 'product 2', price: 20, quantity: 2000, total: 40000},
                {firstname: 'firstname 3', name: 'name 3', product: 'product 3', price: 30, quantity: 3000, total: 90000}
            ],
            sum: function (list) {
                return list.reduce(function (a, b) {
                    return a + b;
                }, 0);
            },
            dataOeContext: '{"o": "model.test"}'
        };
        templateData.docs.mapped = function (fieldName) {return _.pluck(this, fieldName);};

        var rem = await studioTestUtils.createReportEditorManager({
            data: this.data,
            models: this.models,
            env: {
                modelName: 'kikou',
                ids: [42, 43],
                currentId: 42,
            },
            report: {
                report_name: 'awesome_report',
            },
            reportHTML: studioTestUtils.getReportHTML(this.templates, templateData),
            reportViews: studioTestUtils.getReportViews(this.templates, templateData),
            reportMainViewID: 42,
            mockRPC: function (route, args) {
                if (route === '/web_studio/edit_report_view') {
                    var operation = _.last(args.operations);
                    if (!operation) {
                        return Promise.reject();
                    }
                    assert.deepEqual(operation.inheritance, tests[testIndex].inheritance, tests[testIndex].text);
                    return Promise.reject();
                }
                return this._super.apply(this, arguments);
            },
        });

        var testIndex = 0;
        var tests = [
            {
                text: "Should select the hooks inside the th",
                selector: 'thead tr th:eq(0)',
                buildingBlockSelector: '.o_web_studio_sidebar .o_web_studio_field_type_container:eq(1) .o_web_studio_component:contains(Field)',
                position: 'left',
                nearestHookNumber: 1,
                inheritance: [{
                    content: "<span t-field=\"o.child.name\"></span>",
                    position: "before",
                    view_id: 55,
                    xpath: "/t/table/thead/tr/th/span"
                }],
            }, {
                text: "Should select the column (1)",
                buildingBlockSelector: '.o_web_studio_sidebar .o_web_studio_field_type_container:eq(2) .o_web_studio_component:contains(Field Column)',
                selector: 'tbody tr:eq(1) td:first',
                position: {left: 20, top: 0},
                nearestHookNumber: 5,
                inheritance: [{
                    content: "<th><span>Name</span></th>",
                    position: "before",
                    view_id: 55,
                    xpath: "/t/table/thead/tr/th"
                }, {
                    content: "<td><span t-field=\"o.child.name\"></span></td>",
                    position: "before",
                    view_id: 55,
                    xpath: "/t/table/tbody/tr/td"
                }, {
                    content: "<td></td>",
                    position: "before",
                    view_id: 55,
                    xpath: "/t/table/tbody/tr[1]/td"
                }],
                onDragAndDrop: function ($table) {
                    assert.strictEqual($table.find('tr th:first-child.o_web_studio_nearest_hook').length, 1,
                            "Should select the first title cell");
                    assert.strictEqual($table.find('tr td:first-child.o_web_studio_nearest_hook').length, 4,
                            "Should select the first cell of each line");
                },
            }, {
                text: "Should select the hooks inside the td, on the left",
                buildingBlockSelector: '.o_web_studio_sidebar .o_web_studio_field_type_container:eq(1) .o_web_studio_component:contains(Field)',
                selector: 'tbody tr:eq(1) td:first',
                position: 'left',
                nearestHookNumber: 3,
                inheritance: [{
                    content: "<span t-field=\"o.child.name\"></span>",
                    position: "before",
                    view_id: 55,
                    xpath: "/t/table/tbody/tr/td/span"
                }]
            }, {
                text: "Should select the hooks inside the td, on the right",
                buildingBlockSelector: '.o_web_studio_sidebar .o_web_studio_field_type_container:eq(1) .o_web_studio_component:contains(Field)',
                selector: 'tbody tr:eq(1) td:eq(0)',
                position: 'center',
                nearestHookNumber: 3,
                inheritance: [{
                    content: "<span t-field=\"o.child.name\"></span>",
                    position: "after",
                    view_id: 55,
                    xpath: "/t/table/tbody/tr/td/span"
                }],
            },{
                text: "Should select column without the header because it's colspan=2",
                buildingBlockSelector: '.o_web_studio_sidebar .o_web_studio_field_type_container:eq(2) .o_web_studio_component:contains(Field Column)',
                selector: 'tbody tr:eq(1) td:eq(1)',
                position: {left: -10, top: 0},
                nearestHookNumber: 4,
                inheritance: [{
                    content: "<td><span t-field=\"o.child.name\"></span></td>",
                    position: "after",
                    view_id: 55,
                    xpath: "/t/table/tbody/tr/td"
                }, {
                    content: "<td></td>",
                    position: "after",
                    view_id: 55,
                    xpath: "/t/table/tbody/tr[1]/td"
                }, {
                    content: "<attribute name=\"colspan\">3</attribute>",
                    position: "attributes",
                    view_id: 55,
                    xpath: "/t/table/thead/tr/th"
                }],
            }, {
                text: "Should insert between 2nd and 3rd column",
                buildingBlockSelector: '.o_web_studio_sidebar .o_web_studio_field_type_container:eq(2) .o_web_studio_component:contains(Field Column)',
                selector: 'tbody tr:eq(1) td:eq(2)',
                position: {left: -10, top: 0},
                nearestHookNumber: 5,
                inheritance: [{
                    content: "<th><span>Name</span></th>",
                    position: "after",
                    view_id: 55,
                    xpath: "/t/table/thead/tr/th"
                }, {
                    content: "<td><span t-field=\"o.child.name\"></span></td>",
                    position: "after",
                    view_id: 55,
                    xpath: "/t/table/tbody/tr/td[1]"
                  },
                  {
                    content: "<td></td>",
                    position: "after",
                    view_id: 55,
                    xpath: "/t/table/tbody/tr[1]/td[1]"
                  },
                  {
                    content: "<attribute name=\"colspan\">3</attribute>",
                    position: "attributes",
                    view_id: 55,
                    xpath: "/t/table/thead/tr/th"
                  }],
            }, {
                text: "Should select column without the header because there are two colspan=2",
                buildingBlockSelector: '.o_web_studio_sidebar .o_web_studio_field_type_container:eq(2) .o_web_studio_component:contains(Field Column)',
                selector: 'tbody tr:eq(1) td:eq(4)',
                position: {top: 0, left: -10},
                nearestHookNumber: 3,
                inheritance: [{
                    content: "<td><span t-field=\"o.child.name\"></span></td>",
                    position: "after",
                    view_id: 55,
                    xpath: "/t/table/tbody/tr/td[3]"
                }, {
                    content: "<attribute name=\"colspan\">3</attribute>",
                    position: "attributes",
                    view_id: 55,
                    xpath: "/t/table/thead/tr/th[2]"
                }, {
                    content: "<attribute name=\"colspan\">3</attribute>",
                    position: "attributes",
                    view_id: 55,
                    xpath: "/t/table/tbody/tr[1]/td[3]"
                }],
            }, {
                text: "Should select the column (3)",
                buildingBlockSelector: '.o_web_studio_sidebar .o_web_studio_field_type_container:eq(2) .o_web_studio_component:contains(Field Column)',
                selector: 'tbody tr:eq(1) td:eq(5)',
                position: 'left',
                nearestHookNumber: 5,
                inheritance: [{
                    content: "<th><span>Name</span></th>",
                    position: "after",
                    view_id: 55,
                    xpath: "/t/table/thead/tr/th[2]"
                }, {
                    content: "<td><span t-field=\"o.child.name\"></span></td>",
                    position: "after",
                    view_id: 55,
                    xpath: "/t/table/tbody/tr/td[4]"
                }, {
                    content: "<td></td>",
                    position: "after",
                    view_id: 55,
                    xpath: "/t/table/tbody/tr[1]/td[3]"
                }, {
                    content: "<attribute name=\"colspan\">3</attribute>",
                    position: "attributes",
                    view_id: 55,
                    xpath: "/t/table/tbody/tr[1]/td[3]"
                }, {
                    content: "<attribute name=\"colspan\">3</attribute>",
                    position: "attributes",
                    view_id: 55,
                    xpath: "/t/table/thead/tr/th[2]"
                }],
            }, {
                text: "Should select the column (4)",
                buildingBlockSelector: '.o_web_studio_sidebar .o_web_studio_field_type_container:eq(2) .o_web_studio_component:contains(Field Column)',
                selector: 'tbody tr:first td:eq(5)',
                position: 'right',
                nearestHookNumber: 5,
                inheritance: [{
                        content: "<th><span>Name</span></th>",
                        position: "after",
                        view_id: 55,
                        xpath: "/t/table/thead/tr/th[3]"
                      },
                      {
                        content: "<td><span t-field=\"o.child.name\"></span></td>",
                        position: "after",
                        view_id: 55,
                        xpath: "/t/table/tbody/tr/td[5]"
                      },
                      {
                        content: "<td></td>",
                        position: "after",
                        view_id: 55,
                        xpath: "/t/table/tbody/tr[1]/td[4]"
                      }
                ],
            },
        ];


        await rem.editorIframeDef.then(async function () {
            await testUtils.dom.click(rem.$('.o_web_studio_sidebar .o_web_studio_sidebar_header div[name="new"]'));

            // drag and drop a Text component, which should trigger a view edition
            var $table = rem.$('iframe').contents().find('table');

            for (testIndex; testIndex < tests.length; testIndex++) {
                var test = tests[testIndex];
                var $buildingBlock = rem.$(test.buildingBlockSelector);
                var $target = $table.find(test.selector);
                $target.css('border','1px solid black'); // makes debugging easier
                await testUtils.dom.dragAndDrop($buildingBlock, $target, {position: test.position});
                var $nearestHook = $table.find('.o_web_studio_nearest_hook');
                assert.strictEqual($nearestHook.length, test.nearestHookNumber, test.text + ' (nearestHook number)');
                if (test.onDragAndDrop) {
                    test.onDragAndDrop($table);
                }
                $('.o_web_studio_field_modal .o_field_selector').trigger('focusin');
                await testUtils.nextTick();
                await testUtils.dom.click($('.o_web_studio_field_modal .o_field_selector_item[data-name="o"]'));
                await testUtils.dom.click($('.o_web_studio_field_modal .o_field_selector_item[data-name="child"]'));
                await testUtils.dom.click($('.o_web_studio_field_modal .o_field_selector_item[data-name="name"]'));
                await testUtils.dom.click($('.o_web_studio_field_modal .btn-primary'));
            }
            rem.destroy();
            done();
        });
    }));

    QUnit.test('drag & drop field in table without loop', loadIframeCss(async function (assert, done) {
        assert.expect(4);

        this.templates.push({
            key: 'template1',
            view_id: 55,
            arch:
                '<kikou>' +
                    '<t t-name="template1">' +
                        '<table class="table table-sm" style="width: 600px">' +
                            '<thead>' +
                                '<tr>' +
                                    '<th colspan="2"><span>Titre 1</span></th>' +
                                    '<th><span>Titre 2</span></th>' +
                                    '<th colspan="2"><span>Titre 3</span></th>' +
                                    '<th><span>Titre 4</span></th>' +
                                '</tr>' +
                            '</thead>' +
                            '<tbody>' +
                                '<tr>' +
                                    '<td/>' +
                                    '<td/>' +
                                    '<td/>' +
                                    '<td class="text-right" colspan="2"><span class="o_bold">Total</span></td>' +
                                    '<td class="text-right"><span class="o_bold"><t t-esc="sum(docs.mapped(\'total\'))"/></span></td>' +
                                '</tr>' +
                            '</tbody>' +
                        '</table>' +
                    '</t>' +
                '</kikou>',
        });
        var templateData = {
            docs: [
                {firstname: 'firstname 1', name: 'name 1', product: 'product 1', price: 10, quantity: 1000, total: 10000},
                {firstname: 'firstname 2', name: 'name 2', product: 'product 2', price: 20, quantity: 2000, total: 40000},
                {firstname: 'firstname 3', name: 'name 3', product: 'product 3', price: 30, quantity: 3000, total: 90000}
            ],
            sum: function (list) {
                return list.reduce(function (a, b) {
                    return a + b;
                }, 0);
            },
            dataOeContext: '{"o": "model.test"}'
        };
        templateData.docs.mapped = function (fieldName) {return _.pluck(this, fieldName);};

        var rem = await studioTestUtils.createReportEditorManager({
            data: this.data,
            models: this.models,
            env: {
                modelName: 'kikou',
                ids: [42, 43],
                currentId: 42,
            },
            report: {
                report_name: 'awesome_report',
            },
            reportHTML: studioTestUtils.getReportHTML(this.templates, templateData),
            reportViews: studioTestUtils.getReportViews(this.templates, templateData),
            reportMainViewID: 42,
            mockRPC: function (route, args) {
                if (route === '/web_studio/edit_report_view') {
                    var operation = _.last(args.operations);
                    if (!operation) {
                        return Promise.reject();
                    }
                    assert.deepEqual(operation.inheritance, tests[testIndex].inheritance, tests[testIndex].text);
                    return Promise.reject();
                }
                return this._super.apply(this, arguments);
            },
        });

        var testIndex = 0;
        var tests = [
            {
                text: "Should select the column (1)",
                buildingBlockSelector: '.o_web_studio_sidebar .o_web_studio_field_type_container:eq(2) .o_web_studio_component:contains(Field Column)',
                selector: 'tbody tr:eq(0) td:first',
                position: {left: 20, top: 0},
                nearestHookNumber: 2,
                inheritance: [{
                    content: "<th><span>Name</span></th>",
                    position: "before",
                    view_id: 55,
                    xpath: "/t/table/thead/tr/th"
                }, {
                    content: "<td><span t-field=\"o.child.name\"></span></td>",
                    position: "before",
                    view_id: 55,
                    xpath: "/t/table/tbody/tr/td"
                }],
                onDragAndDrop: function ($table) {
                    assert.strictEqual($table.find('tr th:first-child.o_web_studio_nearest_hook').length, 1,
                            "Should select the first title cell");
                    assert.strictEqual($table.find('tr td:first-child.o_web_studio_nearest_hook').length, 1,
                            "Should select the first cell of each line");
                },
            }
        ];

        await rem.editorIframeDef.then(async function () {
            await testUtils.dom.click(rem.$('.o_web_studio_sidebar .o_web_studio_sidebar_header div[name="new"]'));

            // drag and drop a Text component, which should trigger a view edition
            var $table = rem.$('iframe').contents().find('table');

            for (testIndex; testIndex < tests.length; testIndex++) {
                var test = tests[testIndex];
                var $buildingBlock = rem.$(test.buildingBlockSelector);
                var $target = $table.find(test.selector);
                $target.css('border','1px solid black'); // makes debugging easier
                await testUtils.dom.dragAndDrop($buildingBlock, $target, {position: test.position});
                var $nearestHook = $table.find('.o_web_studio_nearest_hook');
                assert.strictEqual($nearestHook.length, test.nearestHookNumber, test.text + ' (nearestHook number)');
                if (test.onDragAndDrop) {
                    test.onDragAndDrop($table);
                }
                $('.o_web_studio_field_modal .o_field_selector').trigger('focusin');
                await testUtils.nextTick();
                await testUtils.dom.click($('.o_web_studio_field_modal .o_field_selector_item[data-name="o"]'));
                await testUtils.dom.click($('.o_web_studio_field_modal .o_field_selector_item[data-name="child"]'));
                await testUtils.dom.click($('.o_web_studio_field_modal .o_field_selector_item[data-name="name"]'));
                await testUtils.dom.click($('.o_web_studio_field_modal .btn-primary'));
            }
            rem.destroy();
            done();
        });
    }));

    QUnit.test('drag & drop block "Accounting Total"', loadIframeCss(async function (assert, done) {
        assert.expect(1);

        this.templates.push({
            key: 'template1',
            view_id: 55,
            arch:
                '<kikou>' +
                    '<t t-name="template1">' +
                        '<div class="row">' +
                            '<div class="col-12">' +
                                '<span>Content</span>' +
                            '</div>' +
                        '</div>' +
                    '</t>' +
                '</kikou>',
        });
        this.models['account.move'] = 'Invoice';
        this.data['account.move'] = {
            fields: {
                name: { string: "Name", type: "char"},
            },
            records: [],
        };
        var templateData = {
            dataOeContext: '{"o": "account.move"}'
        };
        var rem = await studioTestUtils.createReportEditorManager({
            data: this.data,
            models: this.models,
            env: {
                modelName: 'kikou',
                ids: [42, 43],
                currentId: 42,
            },
            report: {
                report_name: 'awesome_report',
            },
            reportHTML: studioTestUtils.getReportHTML(this.templates, templateData),
            reportViews: studioTestUtils.getReportViews(this.templates, templateData),
            reportMainViewID: 42,
            mockRPC: function (route, args) {
                if (route === '/web_studio/edit_report_view') {
                    var operation = _.last(args.operations);
                    if (!operation) {
                        return Promise.reject();
                    }
                    assert.deepEqual(operation.inheritance, [{
                        content:
                            '<div class="row">' +
                                '<div class="col-5">' +
                                    '<table class="table table-sm o_report_block_total">' +
                                        '<t t-set="total_currency_id" t-value="o.currency_id"/>' +
                                        '<t t-set="total_amount_total" t-value="o.amount_total"/>' +
                                        '<t t-set="total_amount_untaxed" t-value="o.amount_untaxed"/>' +
                                        '<t t-set="total_amount_by_groups" t-value="o.amount_by_group"/>' +
                                        '<tr class="border-black o_subtotal">' +
                                        '<td><strong>Subtotal</strong></td>' +
                                        '<td class="text-right">' +
                                            '<span t-esc="total_amount_untaxed" t-options="{\'widget\': \'monetary\', \'display_currency\': total_currency_id}"/>' +
                                        '</td>' +
                                        '</tr>' +
                                        '<t t-foreach="total_amount_by_groups" t-as="total_amount_by_group">' +
                                            '<tr>' +
                                                '<t t-if="len(total_amount_by_group) == 1 and total_amount_untaxed == total_amount_by_group[2]">' +
                                                    '<td><span t-esc="total_amount_by_group[0]"/></td>' +
                                                    '<td class="text-right o_price_total">' +
                                                        '<span t-esc="total_amount_by_group[3]"/>' +
                                                    '</td>' +
                                                '</t>' +
                                                '<t t-else="">' +
                                                    '<td>' +
                                                        '<span t-esc="total_amount_by_group[0]"/>' +
                                                        '<span><span>on</span>' +
                                                            '<t t-esc="total_amount_by_group[4]"/>' +
                                                        '</span>' +
                                                    '</td>' +
                                                    '<td class="text-right o_price_total">' +
                                                        '<span t-esc="total_amount_by_group[3]"/>' +
                                                    '</td>' +
                                                '</t>' +
                                            '</tr>' +
                                        '</t>' +
                                        '<t t-if="total_amount_by_groups is None">' +
                                            '<tr>' +
                                                '<td>Taxes</td>' +
                                                '<td class="text-right">' +
                                                    '<span t-esc="total_amount_total - total_amount_untaxed" t-options="{\'widget\': \'monetary\', \'display_currency\': total_currency_id}"/>' +
                                                '</td>' +
                                            '</tr>' +
                                        '</t>' +
                                        '<tr class="border-black o_total">' +
                                            '<td><strong>Total</strong></td>' +
                                            '<td class="text-right">' +
                                                '<span t-esc="total_amount_total" t-options="{\'widget\': \'monetary\', \'display_currency\': total_currency_id}"/>' +
                                            '</td>' +
                                        '</tr>' +
                                    '</table>' +
                                '</div>' +
                                '<div class="col-5 offset-2"></div>' +
                            '</div>',
                        position: "after",
                        view_id: 55,
                        xpath: "/t/div"
                    }], 'Should send the xpath node with the content');
                    return Promise.reject();
                }
                return this._super.apply(this, arguments);
            },
        });

        await rem.editorIframeDef.then(async function () {
            await testUtils.dom.click(rem.$('.o_web_studio_sidebar .o_web_studio_sidebar_header div[name="new"]'));
            var $main = rem.$('iframe').contents().find('main');

            var $text = rem.$('.o_web_studio_sidebar .o_web_studio_field_type_container:eq(2) .o_web_studio_component:contains(Subtotal & Total)');
            await testUtils.dom.dragAndDrop($text, $main, {position: {top: 50, left: 100}});
            $('.o_web_studio_field_modal .o_field_selector').trigger('focusin');
            await testUtils.nextTick();
            await testUtils.dom.click($('.o_web_studio_field_modal .o_field_selector_item[data-name="o"]'));
            await testUtils.dom.click($('.o_web_studio_field_modal .btn-primary'));

            rem.destroy();
            done();
        });
    }));

    QUnit.test('drag & drop block "Accounting Total"', loadIframeCss(async function (assert, done) {
        assert.expect(3);

        var initialDebugMode = odoo.debug;
        // show all nodes in the sidebar
        odoo.debug = true;

        this.templates.push({
            key: 'template1',
            view_id: 55,
            arch:
                '<kikou>' +
                    '<t t-name="template1">' +
                        '<div class="row">' +
                            '<div class="col-5">' +
                                '<table class="table table-sm o_report_block_total">' +
                                    '<t t-set="total_currency_id" t-value="o.child"/>' +
                                    '<t t-set="total_amount_total" t-value="o.child"/>' +
                                    '<t t-set="total_amount_untaxed" t-value="o.child"/>' +
                                    '<t t-set="total_amount_by_groups" t-value="o.child"/>' +
                                    '<tr>' +
                                        '<th>Subtotal</th>' +
                                        // not need to add content for this test
                                    '</tr>' +
                                '</table>' +
                            '</div>' +
                            '<div class="col-5 offset-2"></div>' +
                        '</div>' +
                    '</t>' +
                '</kikou>',
        });
        var templateData = {
            dataOeContext: '{"o": "model.test"}',
            o: {
                currency_id: 1,
                amount_total: 55,
                amount_untaxed: 55,
                amount_by_group: null,
            }
        };
        var rem = await studioTestUtils.createReportEditorManager({
            data: this.data,
            models: this.models,
            env: {
                modelName: 'kikou',
                ids: [42, 43],
                currentId: 42,
            },
            report: {
                report_name: 'awesome_report',
            },
            reportHTML: studioTestUtils.getReportHTML(this.templates, templateData),
            reportViews: studioTestUtils.getReportViews(this.templates, templateData),
            reportMainViewID: 42,
            mockRPC: function (route, args) {
                if (route === '/web_studio/edit_report_view') {
                    var operation = _.last(args.operations);
                    if (!operation) {
                        return Promise.reject();
                    }
                    assert.deepEqual(operation.inheritance, [{
                        content: '<attribute name="t-value">o.child.grandchild</attribute>',
                        position: "attributes",
                        view_id: 55,
                        xpath: "/t/div/div/table//t[@t-set='total_currency_id']"
                    }], 'Should send the xpath node with the content');
                    return Promise.reject();
                }
                return this._super.apply(this, arguments);
            },
        });

        await rem.editorIframeDef.then(async function () {
            await testUtils.dom.click(rem.$('iframe').contents().find('main th'));
            var $card = rem.$('.o_web_studio_sidebar .card:has(.o_text:contains(table))');
            await testUtils.dom.click($card.find('[data-toggle="collapse"]'));
            $card = rem.$('.o_web_studio_sidebar .card.o_web_studio_active');
            assert.strictEqual($card.find('.o_text').text().trim(), 'table',
                'Correct card should be active after sidebar updation');

            assert.strictEqual($card.find('.o_web_studio_report_currency_id .o_field_selector_chain_part').text().replace(/\s+/g, ' '),
                ' o (Model Test) Child ', 'Should display the t-foreach value');

            rem.$('.o_web_studio_report_currency_id .o_field_selector').trigger('focusin');
            await testUtils.nextTick();
            await testUtils.dom.click(rem.$('.o_web_studio_report_currency_id .o_field_selector_item[data-name="grandchild"]'));
            await testUtils.dom.click(rem.$('.o_web_studio_report_currency_id .o_field_selector_close'));

            rem.destroy();
            odoo.debug = initialDebugMode;
            done();
        });
    }));

    QUnit.test('drag & drop block "Data table"', loadIframeCss(async function (assert, done) {
        assert.expect(2);

        this.templates.push({
            key: 'template1',
            view_id: 55,
            arch:
                '<kikou>' +
                    '<t t-name="template1">' +
                        '<div class="row">' +
                            '<div class="col-12">' +
                                '<span>Content</span>' +
                            '</div>' +
                        '</div>' +
                    '</t>' +
                '</kikou>',
        });
        var templateData = {
            dataOeContext: '{"o": "model.test"}'
        };
        var rem = await studioTestUtils.createReportEditorManager({
            data: this.data,
            models: this.models,
            env: {
                modelName: 'kikou',
                ids: [42, 43],
                currentId: 42,
            },
            report: {
                report_name: 'awesome_report',
            },
            reportHTML: studioTestUtils.getReportHTML(this.templates, templateData),
            reportViews: studioTestUtils.getReportViews(this.templates, templateData),
            reportMainViewID: 42,
            mockRPC: function (route, args) {
                if (route === '/web_studio/edit_report_view') {
                    var operation = _.last(args.operations);
                    if (!operation) {
                        return Promise.reject();
                    }
                    assert.deepEqual(operation.inheritance, [{
                        content:
                            '<table class="table o_report_block_table">' +
                                '<thead>' +
                                    '<tr>' +
                                        '<th><span>Name</span></th>' +
                                    '</tr>' +
                                '</thead>' +
                                '<tbody>' +
                                    '<tr t-foreach="o.children" t-as="table_line">' +
                                        '<td><span t-field="table_line.display_name"/></td>' +
                                    '</tr>' +
                                '</tbody>' +
                            '</table>',
                        position: "after",
                        view_id: 55,
                        xpath: "/t/div"
                    }], 'Should send the xpath node with the content');
                    return Promise.reject();
                }
                return this._super.apply(this, arguments);
            },
        });

        await rem.editorIframeDef.then(async function () {
            await testUtils.dom.click(rem.$('.o_web_studio_sidebar .o_web_studio_sidebar_header div[name="new"]'));
            var $main = rem.$('iframe').contents().find('main');

            var $text = rem.$('.o_web_studio_sidebar .o_web_studio_component:contains(Data table)');
            await testUtils.dom.dragAndDrop($text, $main, {position: {top: 50, left: 300}});
            $('.o_web_studio_field_modal .o_field_selector').trigger('focusin');
            await testUtils.dom.click($('.o_web_studio_field_modal .o_field_selector_item[data-name="o"]'));
            await testUtils.dom.click($('.o_web_studio_field_modal .btn-primary'));

            assert.strictEqual($('.o_technical_modal h4:contains(Alert)').length, 1, "Should display an alert because the selected field is wrong");

            await testUtils.dom.click($('.o_technical_modal:contains(Alert) .btn-primary'));
            await testUtils.dom.click($('.o_web_studio_field_modal .o_field_selector_item[data-name="children"]'));
            await testUtils.dom.click($('.o_web_studio_field_modal .btn-primary'));

            rem.destroy();
            done();
        });
    }));

    QUnit.test('drag & drop block "Address"', async function (assert) {
        assert.expect(1);
        var done = assert.async();

        this.templates.push({
            key: 'template1',
            view_id: 55,
            arch: '<kikou><t t-name="template1"/></kikou>',
        });

        var templateData = {
            dataOeContext: '{"o": "model.test"}',
        };

        // the address block requires a many2one to res.partner
        this.data['model.test'].fields.partner = {
            string: "Partner", type: 'many2one', relation: 'res.partner', 'searchable': true,
        };

        var rem = await studioTestUtils.createReportEditorManager({
            data: this.data,
            models: this.models,
            env: {
                modelName: 'kikou',
                ids: [42, 43],
                currentId: 42,
            },
            report: {},
            reportHTML: studioTestUtils.getReportHTML(this.templates, templateData),
            reportViews: studioTestUtils.getReportViews(this.templates, templateData),
            reportMainViewID: 42,
            mockRPC: function (route, args) {
                if (route === '/web_studio/edit_report_view') {
                    var operation = _.last(args.operations);
                    if (!operation) {
                        return Promise.reject();
                    }
                    assert.deepEqual(operation.inheritance, [{
                        content:
                            '<div class="row address">' +
                                '<div class="col-5"></div>' +
                                '<div class="col-5 offset-2">' +
                                    "<div t-field=\"o.partner\" t-options-widget=\"'contact'\"/>" +
                                '</div>' +
                            '</div>',
                        position: "inside",
                        view_id: 42,
                        xpath: "/t/html/body/div/main/div",
                    }], 'Should send the xpath node with the content');
                    return Promise.reject();
                }
                return this._super.apply(this, arguments);
            },
        });

        await rem.editorIframeDef.then(async function () {
            await testUtils.dom.click(rem.$('.o_web_studio_sidebar .o_web_studio_sidebar_header div[name="new"]'));
            var $page = rem.$('iframe').contents().find('.page');

            var $text = rem.$('.o_web_studio_sidebar .o_web_studio_component:contains(Address)');
            await testUtils.dom.dragAndDrop($text, $page, {position: 'inside'});
            $('.o_web_studio_field_modal .o_field_selector').trigger('focusin');
            await testUtils.dom.click($('.o_web_studio_field_modal .o_field_selector_item[data-name="o"]'));
            await testUtils.dom.click($('.o_web_studio_field_modal .o_field_selector_item[data-name="partner"]'));
            await testUtils.dom.click($('.o_web_studio_field_modal .btn-primary'));

            rem.destroy();
            done();
        });
    });

    QUnit.test('drag & drop block "Image"', async function (assert) {
        assert.expect(2);
        var done = assert.async();
        var self = this;

        this.templates.push({
            key: 'template1',
            view_id: 55,
            arch: '<kikou><t t-name="template1"/></kikou>',
        });

        var editReportViewCalls = 0;
        var rem = await studioTestUtils.createReportEditorManager({
            data: this.data,
            models: this.models,
            env: {
                modelName: 'kikou',
                ids: [42, 43],
                currentId: 42,
            },
            report: {},
            reportHTML: studioTestUtils.getReportHTML(this.templates),
            reportViews: studioTestUtils.getReportViews(this.templates),
            reportMainViewID: 42,
            mockRPC: function (route, args) {
                // Bypass mockSearchRead domain evauation
                if (route === '/web/dataset/call_kw/ir.attachment/search_read') {
                    return Promise.resolve([self.data['ir.attachment'].records[0]]);
                }
                if (route === '/web_studio/edit_report_view') {
                    if (editReportViewCalls === 0) {
                        assert.strictEqual(
                            args.operations[0].inheritance[0].content,
                            '<img class="img-fluid" src="/web/static/joes_garage.png?access_token=token"/>',
                            'The image should be added to the view with a relative path as src'
                        );
                    }
                    editReportViewCalls++;
                    return Promise.reject();
                }
                if (route.indexOf('/web/static/joes_garage.png') === 0) {
                    return Promise.resolve();
                }
                return this._super.apply(this, arguments);
            },
        });

        // Process to use the report editor
        await rem.editorIframeDef.then(async function () {
            var defMediaDialogInit = testUtils.makeTestPromise();
            testUtils.mock.patch(MediaDialog, {
                init: function () {
                    this._super.apply(this, arguments);
                    this.opened(defMediaDialogInit.resolve.bind(defMediaDialogInit));
                },
            });

            // Wait for the image modal to be fully loaded in two steps:
            // First, the Bootstrap modal itself
            $('body').one('shown.bs.modal', function () {
                assert.containsOnce($('body'), '.modal-dialog.o_select_media_dialog',
                    'The bootstrap modal for media selection is open');
            });
            // Second, when the modal element is there, bootstrap focuses on the "image" tab
            // then only could we use the widget and select an image safely
            defMediaDialogInit.then(async function () {
                var $modal = $('.o_select_media_dialog');
                await testUtilsDom.click($modal.find('.o_existing_attachment_cell'));
                await testUtilsDom.click($modal.find('footer button:contains(Add)'));

                testUtils.mock.unpatch(MediaDialog);
                done();
                rem.destroy();
            });

            var $page = rem.$('iframe').contents().find('.page');
            var $imageBlock = rem.$('.o_web_studio_sidebar .o_web_studio_component:contains(Image)');
            await testUtils.dom.dragAndDrop($imageBlock, $page, {position: 'inside'});
        });
    });

    QUnit.test('edit text', async function (assert) {
        assert.expect(2);

        this.templates.push({
            key: 'template1',
            view_id: 55,
            arch:
                '<kikou>' +
                    '<t t-name="template1">' +
                        '<span>taratata <strong>bo</strong></span>' +
                    '</t>' +
                '</kikou>',
        });
        var rem = await studioTestUtils.createReportEditorManager({
            data: this.data,
            models: this.models,
            env: {
                modelName: 'kikou',
                ids: [42, 43],
                currentId: 42,
            },
            report: {
                report_name: 'awesome_report',
            },
            reportHTML: studioTestUtils.getReportHTML(this.templates),
            reportViews: studioTestUtils.getReportViews(this.templates),
            reportMainViewID: 42,
            mockRPC: function (route, args) {
                if (route === '/web_studio/edit_report_view') {
                    var operation = _.last(args.operations);
                    if (!operation) {
                        return Promise.reject();
                    }
                    assert.deepEqual(operation.inheritance, [{
                        content: '<span>toto <small>titi</small></span>',
                        position: "replace",
                        view_id: 55,
                        xpath: "/t/span"
                    }], 'Should replace the title content');
                    return Promise.reject();
                }
                return this._super.apply(this, arguments);
            },
        });

        await rem.editorIframeDef.then(async function () {
            await testUtils.dom.click(rem.$('iframe').contents().find('span'));

            var $editable = rem.$('.o_web_studio_sidebar .card.o_web_studio_active .note-editable');

            assert.strictEqual($editable.html(), 'taratata <strong>bo</strong>', 'Should display the text content');

            $editable.mousedown();
            await testUtils.nextTick();
            $editable.html('toto <small>titi</small>');
            $editable.find('span').mousedown();
            await testUtils.nextTick();
            $editable.keydown();
            await testUtils.nextTick();
            $editable.blur();
            await testUtils.nextTick();

            rem.destroy();
        });
    });

    QUnit.test('open XML editor after modification', async function (assert) {
        assert.expect(7);

        // the XML editor lazy loads its libs and its templates so its start
        // method is monkey-patched to know when the widget has started
        var XMLEditorProm = testUtils.makeTestPromise();
        testUtils.mock.patch(ace, {
            start: function () {
                return this._super.apply(this, arguments).then(function () {
                    XMLEditorProm.resolve();
                });
            },
        });
        var initialDebugMode = odoo.debug;
        // the XML editor button is only available in debug mode
        odoo.debug = true;

        var self = this;
        this.templates.push({
            key: 'template1',
            view_id: 55,
            arch:
                '<kikou>' +
                    '<t t-name="template1">' +
                        '<div class="row">' +
                            '<div class="col-12">' +
                                '<span>First span</span>' +
                            '</div>' +
                        '</div>' +
                    '</t>' +
                '</kikou>',
        });

        var rem = await studioTestUtils.createReportEditorManager({
            data: this.data,
            models: this.models,
            env: {
                modelName: 'kikou',
                ids: [42, 43],
                currentId: 42,
            },
            report: {
                report_name: 'awesome_report',
            },
            reportHTML: studioTestUtils.getReportHTML(this.templates),
            reportViews: studioTestUtils.getReportViews(this.templates),
            reportMainViewID: 42,
            mockRPC: function (route, args) {
                if (route === '/web_studio/edit_report_view') {
                    // directly apply the operation on the view
                    self.templates[1].arch = '<kikou>' +
                        '<t t-name="template1">' +
                            '<div class="row">' +
                                '<div class="col-12">' +
                                    '<span>hello</span>' +
                                '</div>' +
                            '</div>' +
                        '</t>' +
                    '</kikou>';

                    return Promise.resolve({
                        report_html: studioTestUtils.getReportHTML(self.templates),
                        views: studioTestUtils.getReportViews(self.templates),
                    });
                } else if (route === '/web_editor/get_assets_editor_resources') {
                    assert.strictEqual(args.key, self.templates[0].view_id, "the correct view should be fetched");
                    return Promise.resolve({
                        views: [{
                            active: true,
                            arch: self.templates[0].arch,
                            id: self.templates[0].view_id,
                            inherit_id: false,
                        }],
                        scss: [],
                        js: [],
                    });
                }
                return this._super.apply(this, arguments);
            },
        });

        await rem.editorIframeDef.then(async function () {
            assert.strictEqual(rem.$('iframe').contents().find('.page').text(),"First span",
                "the iframe should be rendered");

            // click to edit a span and change the text (should trigger the report edition)
            await testUtils.dom.click(rem.$('iframe').contents().find('span:contains(First)'));
            await testUtils.fields.editInput(rem.$('.o_web_studio_sidebar .o_web_studio_active textarea[name="text"]'), "hello");

            var $textarea = rem.$('.o_web_studio_sidebar .o_web_studio_active textarea[name="text"]');
            testUtils.fields.editInput($textarea, "hello");

            assert.strictEqual(rem.$('iframe').contents().find('.page').text(), "hello",
                "the iframe should have been updated");
            var $newTextarea = rem.$('.o_web_studio_sidebar .o_web_studio_active textarea[name="text"]');
            assert.strictEqual($newTextarea.length, 1,
                "there should still be a textarea to edit the node text");
            assert.strictEqual($newTextarea.val(), "hello",
                "the Text component should have been updated");
            assert.strictEqual(rem.$('iframe').contents().find('.page').text(),"hello",
                "the iframe should be re-rendered");

            // switch tab
            await testUtils.dom.click(rem.$('.o_web_studio_sidebar_header [name="report"]'));
            // open the XML editor
            await testUtils.dom.click(rem.$('.o_web_studio_sidebar .o_web_studio_xml_editor'));

            await XMLEditorProm.then(function () {
                assert.strictEqual(rem.$('iframe').contents().find('.page').text(),"hello",
                    "the iframe should be re-rendered");

                odoo.debug = initialDebugMode;
                testUtils.mock.unpatch(ace);
                rem.destroy();
            });
        });
    });

    QUnit.test('automatic undo of correct operation', async function (assert) {
        var self = this;
        var done = assert.async();
        assert.expect(5);

        this.templates.push({
            key: 'template1',
            view_id: 55,
            arch:
                '<kikou>' +
                    '<t t-name="template1"><div>First</div></t>' +
                '</kikou>',
        });

        var rem = await studioTestUtils.createReportEditorManager({
            env: {
                modelName: 'kikou',
                ids: [42, 43],
                currentId: 42,
            },
            report: {},
            reportHTML: studioTestUtils.getReportHTML(this.templates),
            reportViews: studioTestUtils.getReportViews(this.templates),
            reportMainViewID: 42,
            mockRPC: function (route, args) {
                if (route === '/web_studio/edit_report_view') {
                    nbEdit++;
                    switch (nbEdit) {
                        case 1:
                            assert.strictEqual(args.operations.length, 1);
                            assert.deepEqual(args.operations[0].inheritance, [{
                                content: '<attribute name="class" separator=" " add="o_bold"/>',
                                position: 'attributes',
                                view_id: 55,
                                xpath: '/t/div',
                            }]);
                            // first rpc that we will make fail
                            return firstDef;
                        case 2:
                            // NB: undo RPC and second op RPC are dropped by
                            // MutexedDropPrevious
                            assert.strictEqual(args.operations.length, 2,
                                "should have undone the first operation");
                            assert.deepEqual(args.operations[0].inheritance, [{
                                content: '<attribute name="class" separator=" " add="o_italic"/>',
                                position: 'attributes',
                                view_id: 55,
                                xpath: '/t/div',
                            }]);
                            assert.deepEqual(args.operations[1].inheritance, [{
                                content: '<attribute name="class" separator=" " add="o_underline"/>',
                                position: 'attributes',
                                view_id: 55,
                                xpath: '/t/div',
                            }]);
                            // second rpc that succeeds
                            return Promise.resolve({
                                report_html: studioTestUtils.getReportHTML(self.templates),
                                views: studioTestUtils.getReportViews(self.templates),
                            });
                        case 3:
                            assert.ok(false, "should not edit a third time");
                    }

                }
                return this._super.apply(this, arguments);
            },
        });

        var nbEdit = 0;
        var firstDef = testUtils.makeTestPromise();
        rem.editorIframeDef.then(async function () {
            await testUtils.dom.click(rem.$('iframe').contents().find('div:contains(First):last'));

            // trigger a modification
            await testUtils.dom.click(rem.$('.o_web_studio_sidebar .card:eq(1) .o_web_studio_text_decoration button[data-property="bold"]'));

            // trigger a second modification before the first one has finished
            await testUtils.dom.click(rem.$('.o_web_studio_sidebar .card:eq(1) .o_web_studio_text_decoration button[data-property="italic"]'));

            // trigger a third modification before the first one has finished
            await testUtils.dom.click(rem.$('.o_web_studio_sidebar .card:eq(1) .o_web_studio_text_decoration button[data-property="underline"]'));

            // make the first op fail (will release the MutexedDropPrevious)
            firstDef.reject();
            await testUtils.nextTick();

            rem.destroy();
            done();
        });
    });

    QUnit.test('automatic undo on AST error', async function (assert) {
        var self = this;
        var done = assert.async();
        assert.expect(4);

        this.templates.push({
            key: 'template1',
            view_id: 55,
            arch:
                '<kikou>' +
                    '<t t-name="template1">' +
                        '<div>Kikou</div>' +
                    '</t>' +
                '</kikou>',
        });
        var nbEdit = 0;
        var rem = await studioTestUtils.createReportEditorManager({
            env: {
                modelName: 'kikou',
                ids: [42, 43],
                currentId: 42,
            },
            report: {},
            reportHTML: studioTestUtils.getReportHTML(this.templates),
            reportViews: studioTestUtils.getReportViews(this.templates),
            reportMainViewID: 42,
            mockRPC: function (route, args) {
                if (route === '/web_studio/edit_report_view') {
                    nbEdit++;
                    if (nbEdit === 1) {
                        assert.strictEqual(args.operations.length, 1, "the operation is correctly applied");
                        // simulate an AST error
                        return Promise.resolve({
                            report_html: {
                                error: 'AST error',
                                message: 'You have probably done something wrong',
                            },
                        });
                    }
                    if (nbEdit === 2) {
                        assert.strictEqual(args.operations.length, 0, "the operation should be undone");
                        return Promise.resolve({
                            report_html: studioTestUtils.getReportHTML(self.templates),
                            views: studioTestUtils.getReportViews(self.templates),
                        });
                    }
                }
                return this._super.apply(this, arguments);
            },
            services: {
                notification: NotificationService.extend({
                    notify: function (params) {
                        assert.step(params.type);
                    }
                }),
            },
        });

        await rem.editorIframeDef.then(async function () {
            await testUtils.dom.click(rem.$('iframe').contents().find('div:contains(Kikou):last'));

            // trigger a modification that will fail
            await testUtils.dom.click(rem.$('.o_web_studio_sidebar .card:eq(1) .o_web_studio_text_decoration button[data-property="bold"]'));

            assert.verifySteps(['danger'], "should have undone the operation");

            rem.destroy();
            done();
        });
    });

    QUnit.test('reattach studio editor, no error', async function (assert) {
        var done = assert.async();
        assert.expect(1);

        this.templates.push({
            key: 'template1',
            view_id: 55,
            arch:
                '<kikou>' +
                    '<t t-name="template1">' +
                    '</t>' +
                '</kikou>',
        });

        var rem = await studioTestUtils.createReportEditorManager({
            env: {
                modelName: 'kikou',
                ids: [42, 43],
                currentId: 42,
            },
            report: {
                report_name: 'awesome_report',
            },
            reportHTML: studioTestUtils.getReportHTML(this.templates),
            reportViews: studioTestUtils.getReportViews(this.templates),
        });

        await rem.editorIframeDef.then(async function () {
            // detach then reattach $iframe to simulate iframe content loss
            $('<div />').replaceAll(rem.view.$iframe).replaceWith(rem.view.$iframe);
            rem.updateEditor();
            assert.ok(true, "Updating report editor did not cause an error");
            rem.destroy();
            done();
        });
    });

    QUnit.test('t-field are editable in non-debug mode', async function (assert) {
        assert.expect(4);

        const initialDebugMode = config.debug;
        config.debug = false;

        this.templates.push({
            key: 'template1',
            view_id: 55,
            arch:
                `<kikou>
                    <t t-name="template1">
                        <p>
                            <span t-field="name">awesome_field</span>
                        </p>
                    </t>
                </kikou>`
        });

        const rem = await studioTestUtils.createReportEditorManager({
            data: this.data,
            models: this.models,
            env: {
                modelName: 'model.test',
                ids: [42, 43],
                currentId: 42,
            },
            report: {
                report_name: 'awesome_report',
            },
            reportHTML: studioTestUtils.getReportHTML(this.templates),
            reportViews: studioTestUtils.getReportViews(this.templates),
            reportMainViewID: 42,
        });

        await rem.editorIframeDef;
        const tFieldName = rem.$('iframe').contents().find('span[t-field="name"]');
        assert.ok(tFieldName, "should have t-field 'name' in the report editor");

        await testUtils.dom.click(tFieldName);
        assert.containsOnce(
            $,
            '.o_web_studio_report_sidebar',
            "should display report editor sidebar on clicking on tfield");
        assert.containsOnce(
            $('.o_web_studio_report_sidebar'),
            '.card.o_web_studio_active',
            "report editor sidebar should have an active card");
        assert.strictEqual(
            $(`.o_web_studio_report_sidebar
               .card.o_web_studio_active
               .card-header
               .o_text`)
            .text()
            .replace(/\s/g, ''),
            "span[name]",
            "active card in sidebar should be on t-field 'name' (which is a span)");

        config.debug = initialDebugMode;
        rem.destroy();
    });
});

});

});
