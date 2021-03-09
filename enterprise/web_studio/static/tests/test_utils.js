odoo.define('web_studio.testUtils', function (require) {
"use strict";

var dom = require('web.dom');
var QWeb = require('web.QWeb');
var testUtils = require('web.test_utils');
var utils = require('web.utils');
var Widget = require('web.Widget');

var ReportEditor = require('web_studio.ReportEditor');
var ReportEditorManager = require('web_studio.ReportEditorManager');
var ReportEditorSidebar = require('web_studio.ReportEditorSidebar');
var ViewEditorManager = require('web_studio.ViewEditorManager');

var weTestUtils = require('web_editor.test_utils');
var Wysiwyg = require('web_editor.wysiwyg.root');

/**
 * Test Utils
 *
 * In this module, we define some utility functions to create Studio objects.
 */

var assetsLoaded;
function loadAssetLib(parent) {
    if (assetsLoaded) { // avoid flickering when begin to edit
        return assetsLoaded;
    }
    assetsLoaded = new Promise(function (resolve, reject) {
        var wysiwyg = new Wysiwyg(parent, {
            recordInfo: {
                context: {},
            }
        });
        wysiwyg.attachTo($('<textarea>')).then(function () {
            wysiwyg.destroy();
            resolve();
        });
    });
    return assetsLoaded;
}

/**
 * Create a ReportEditorManager widget.
 *
 * @param {Object} params
 * @return {ReportEditorManager}
 */
function createReportEditor(params) {
    var Parent = Widget.extend({
        start: function () {
            var self = this;
            this._super.apply(this, arguments).then(function () {
                var $studio = $.parseHTML(
                    "<div class='o_web_studio_client_action'>" +
                            "<div class='o_web_studio_editor_manager o_web_studio_report_editor_manager'/>" +
                        "</div>" +
                    "</div>");
                self.$el.append($studio);
            });
        },
    });
    var parent = new Parent();
    weTestUtils.patch();
    params.data = weTestUtils.wysiwygData(params.data);
    testUtils.mock.addMockEnvironment(parent, params);

    var selector = params.debug ? 'body' : '#qunit-fixture';
    return parent.appendTo(selector).then(function () {
        var editor = new ReportEditor(parent, params);
        // override 'destroy' of editor so that it calls 'destroy' on the parent
        // instead
        editor.destroy = function () {
            // remove the override to properly destroy editor and its children
            // when it will be called the second time (by its parent)
            delete editor.destroy;
            // TODO: call super?
            parent.destroy();
            weTestUtils.unpatch();
        };
        return editor.appendTo(parent.$('.o_web_studio_editor_manager')).then(function () {
            return editor;
        });
    });
}

/**
 * Create a ReportEditorManager widget.
 *
 * @param {Object} params
 * @return {Promise<ReportEditorManager>}
 */
async function createReportEditorManager(params) {
    var parent = new StudioEnvironment();
    testUtils.mock.addMockEnvironment(parent, params);
    weTestUtils.patch();
    params.data = weTestUtils.wysiwygData(params.data);

    await loadAssetLib(parent);
    var rem = new ReportEditorManager(parent, params);
    // also destroy to parent widget to avoid memory leak
    rem.destroy = function () {
        delete rem.destroy;
        parent.destroy();
        weTestUtils.unpatch();
    };

    var fragment = document.createDocumentFragment();
    var selector = params.debug ? 'body' : '#qunit-fixture';
    if (params.debug) {
        $('body').addClass('debug');
    }
    await parent.prependTo(selector);
    await rem.appendTo(fragment)
    // use dom.append to call on_attach_callback
    dom.append(parent.$('.o_web_studio_client_action'), fragment, {
        callbacks: [{widget: rem}],
        in_DOM: true,
    });
    await rem.editorIframeDef
    return rem;
}

/**
 * Create a sidebar widget.
 *
 * @param {Object} params
 * @return {Promise<ReportEditorSidebar>}
 */
function createSidebar(params) {
    var Parent = Widget.extend({
        start: function () {
            var self = this;
            this._super.apply(this, arguments).then(function () {
                var $studio = $.parseHTML(
                    "<div class='o_web_studio_client_action'>" +
                            "<div class='o_web_studio_editor_manager o_web_studio_report_editor_manager'/>" +
                    "</div>");
                self.$el.append($studio);
            });
        },
    });
    var parent = new Parent();
    weTestUtils.patch();
    params.data = weTestUtils.wysiwygData(params.data);
    testUtils.mock.addMockEnvironment(parent, params);

    return loadAssetLib(parent).then(function () {
        var sidebar = new ReportEditorSidebar(parent, params);
        sidebar.destroy = function () {
            // remove the override to properly destroy sidebar and its children
            // when it will be called the second time (by its parent)
            delete sidebar.destroy;
            parent.destroy();
            weTestUtils.unpatch();
        };

        var selector = params.debug ? 'body' : '#qunit-fixture';
        if (params.debug) {
            $('body').addClass('debug');
        }
        parent.appendTo(selector);

        var fragment = document.createDocumentFragment();
        return sidebar.appendTo(fragment).then(function () {
            sidebar.$el.appendTo(parent.$('.o_web_studio_editor_manager'));
            return sidebar;
        });
    });
}

/**
 * Create a ViewEditorManager widget.
 *
 * @param {Object} params
 * @return {Promise<ViewEditorManager>}
 */
function createViewEditorManager(params) {
    var parent = new StudioEnvironment();
    weTestUtils.patch();
    params.data = weTestUtils.wysiwygData(params.data);
    var mockServer = testUtils.mock.addMockEnvironment(parent, params);
    var fieldsView = testUtils.mock.fieldsViewGet(mockServer, params);
    if (params.viewID) {
        fieldsView.view_id = params.viewID;
    }
    var vem = new ViewEditorManager(parent, {
        action: {
            context: params.context || {},
            domain: params.domain || [],
            res_model: params.model,
        },
        controllerState: {
            currentId: 'res_id' in params ? params.res_id : undefined,
            resIds: 'res_id' in params ? [params.res_id] : undefined,
        },
        fields_view: fieldsView,
        viewType: fieldsView.type,
        studio_view_id: params.studioViewID,
        chatter_allowed: params.chatter_allowed,
    });

    // also destroy to parent widget to avoid memory leak
    var originalDestroy = ViewEditorManager.prototype.destroy;
    vem.destroy = function () {
        vem.destroy = originalDestroy;
        parent.destroy();
        weTestUtils.unpatch();
    };

    var fragment = document.createDocumentFragment();
    var selector = params.debug ? 'body' : '#qunit-fixture';
    if (params.debug) {
        $('body').addClass('debug');
    }
    return parent.prependTo(selector).then(function () {
        return vem.appendTo(fragment).then(function () {
            dom.append(parent.$('.o_web_studio_client_action'), fragment, {
                callbacks: [{widget: vem}],
                in_DOM: true,
            });
            return vem;
        });
    });
}

/**
 * Renders a list of templates.
 *
 * @param {Array<Object>} templates
 * @param {Object} data
 * @param {String} [data.dataOeContext]
 * @returns {string}
 */
function getReportHTML(templates, data) {
    _brandTemplates(templates, data && data.dataOeContext);

    var qweb = new QWeb();
    _.each(templates, function (template) {
        qweb.add_template(template.arch);
    });
    var render = qweb.render('template0', data);
    return render;
}

/**
 * Builds the report views object.
 *
 * @param {Array<Object>} templates
 * @param {Object} [data]
 * @param {String} [data.dataOeContext]
 * @returns {Object}
 */
function getReportViews(templates, data) {
    _brandTemplates(templates, data && data.dataOeContext);

    var reportViews = {};
    _.each(templates, function (template) {
        reportViews[template.view_id] = {
            arch: template.arch,
            key: template.key,
            studio_arch: '</data>',
            studio_view_id: false,
            view_id: template.view_id,
        };
    });
    return reportViews;
}

/**
 * Brands (in place) a list of templates.
 *
 * @private
 * @param {Array<Object>} templates
 * @param {String} [dataOeContext]
 */
function _brandTemplates(templates, dataOeContext) {

    _.each(templates, function (template) {
        brandTemplate(template);
    });

    function brandTemplate(template) {
        var doc = $.parseXML(template.arch).documentElement;
        var rootNode = utils.xml_to_json(doc, true);
        brandNode([rootNode], rootNode, '');

        function brandNode(siblings, node, xpath) {
            // do not brand already branded nodes
            if (_.isObject(node) && !node.attrs['data-oe-id']) {
                if (node.tag !== 'kikou') {
                    xpath += ('/' + node.tag);
                    var index = _.filter(siblings, {tag: node.tag}).indexOf(node);
                    if (index > 0) {
                        xpath += '[' + index + ']';
                    }
                    node.attrs['data-oe-id'] = template.view_id;
                    node.attrs['data-oe-xpath'] = xpath;
                    node.attrs['data-oe-context'] = dataOeContext || '{}';
                }

                _.each(node.children, function (child) {
                    brandNode(node.children, child, xpath);
                });
            }
        }
        template.arch = utils.json_node_to_xml(rootNode);
    }
}

var StudioEnvironment = Widget.extend({
    className: 'o_web_client o_in_studio',
    start: function () {
        var self = this;
        this._super.apply(this, arguments).then(function () {
            // reproduce the DOM environment of Studio
            var $studio = $.parseHTML(
                "<div class='o_content'>" +
                    "<div class='o_web_studio_client_action'/>" +
                "</div>"
            );
            self.$el.append($studio);
        });
    },
});

return {
    createReportEditor: createReportEditor,
    createReportEditorManager: createReportEditorManager,
    createSidebar: createSidebar,
    createViewEditorManager: createViewEditorManager,
    getData: weTestUtils.wysiwygData,
    getReportHTML: getReportHTML,
    getReportViews: getReportViews,
    patch: weTestUtils.patch,
    unpatch: weTestUtils.unpatch,
};

});
