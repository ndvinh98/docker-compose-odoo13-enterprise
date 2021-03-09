odoo.define('website_studio.formManager_tests', function (require) {
"use strict";

var testUtils = require('web.test_utils');
var FormManager = require('website_studio.FormManager');

QUnit.module('FormManager', {
    beforeEach: function () {
        this.data = {
            partner: {
                fields: {
                    name: {
                        string: "Name",
                        type: "char"
                    },
                },
            },
        };
        this.options = {
                action: {
                    res_model: 'partner',
                }
        };
    }
}, function () {

    QUnit.test('Simple Form Manager rendering', async function (assert) {
        assert.expect(4);
        var clientAction = new FormManager(null, {}, this.options);
        testUtils.mock.addMockEnvironment(clientAction, {
            data: this.data,
            mockRPC: function (route, args) {
                if (route === '/website_studio/get_forms') {
                    assert.ok(true, "should call /website_studio/get_forms");
                    return Promise.resolve([{id: 1, name: 'partner', url: '/partner'}]);
                }
                return this._super(route, args);
            },
        });
        await clientAction.appendTo($('#qunit-fixture'));
        var $thumbnails = clientAction.$('.o_web_studio_thumbnail');
        assert.strictEqual($thumbnails.length, 2,
            "should be 2 thumbnails");
        assert.strictEqual($thumbnails.eq(0).data('newForm'), true,
            "the first thumbnail should be the one to create a new form");
        assert.strictEqual($thumbnails.eq(1).data('url'), '/partner',
            "the second thumbnail should contains the form url");
        clientAction.destroy();
    });

});
});
