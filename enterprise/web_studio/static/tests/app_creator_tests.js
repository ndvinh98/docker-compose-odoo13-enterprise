odoo.define('web_studio.AppCreator_tests', function (require) {
"use strict";

var testUtils = require('web.test_utils');
var triggerKeypressEvent = testUtils.dom.triggerKeypressEvent;

var AppCreator = require('web_studio.AppCreator');


QUnit.module('Studio', {}, function () {

    QUnit.module('AppCreator');

    QUnit.test('basic stuff', async function(assert) {
        assert.expect(11);

        var $target = $('#qunit-fixture');
        var app_creator = new AppCreator(null, {});
        app_creator.debug = false;
        await app_creator.appendTo($target);

        testUtils.mock.addMockEnvironment(app_creator, {
            session: {},
        });

        // step 1
        assert.strictEqual(
            app_creator.currentStep,
            1,
            "currentStep should be set to 1");
        assert.isNotVisible(app_creator.$('.o_web_studio_app_creator_back'),
            "back button should be hidden at step 1");
        assert.hasClass(app_creator.$('.o_web_studio_app_creator_next'), 'is_ready',
            "next button should be ready at step 1");

        // go to step 2
        testUtils.dom.click(app_creator.$('.o_web_studio_app_creator_next'));

        assert.strictEqual(
            app_creator.currentStep,
            2,
            "currentStep should be set to 2");

        // try to go to step 3 but cannot
        testUtils.dom.click(app_creator.$('.o_web_studio_app_creator_next'));

        assert.strictEqual(
            app_creator.currentStep,
            2,
            "currentStep should not be update because the input is not filled");

        app_creator.$('input[name="app_name"]').val('Kikou');

        // go to step 3
        testUtils.dom.click(app_creator.$('.o_web_studio_app_creator_next'));

        assert.strictEqual(
            app_creator.currentStep,
            3,
            "currentStep should be 3");
        await testUtils.nextTick();  // wait for async update of studio

        await testUtils.dom.click(app_creator.$('.o_web_studio_app_creator_next'));

        assert.hasClass(app_creator.$('input[name="menu_name"]').parent(),
            'o_web_studio_app_creator_field_warning',
            "a warning should be displayed on the input");

        assert.containsNone(app_creator, 'input[name="model_choice"]',
            "it shouldn't be possible to select a model without debug");

        app_creator.debug = true;
        app_creator.update();
        await testUtils.nextTick();  // wait for async update of studio

        app_creator.$('input[name="menu_name"]').val('Petite Perruche');

        await testUtils.nextTick();
        assert.containsOnce(app_creator, 'input[name="model_choice"]',
            "it should be possible to select a model in debug");

        // click to select a model
        await testUtils.dom.click(app_creator.$('input[name="model_choice"]'));

        assert.containsOnce(app_creator, '.o_field_many2one',
            "there should be a many2one to select a model");

        // unselect the model
        await testUtils.dom.click(app_creator.$('input[name="model_choice"]'));

        assert.hasClass(app_creator.$('.o_web_studio_app_creator_next'), 'is_ready',
            "next button should be ready at step 3");

        app_creator.destroy();
    });

    QUnit.test('use <Enter> in the app creator', async function(assert) {
        assert.expect(5);

        var $target = $('#qunit-fixture');
        var appCreator = new AppCreator(null, {});
        await appCreator.appendTo($target);

        testUtils.mock.addMockEnvironment(appCreator, {
            session: {},
        });

        // step 1
        assert.strictEqual(appCreator.currentStep, 1,
            "currentStep should be set to 1");

        // go to step 2
        triggerKeypressEvent('Enter');
        assert.strictEqual(appCreator.currentStep, 2,
            "currentStep should be set to 2");

        // try to go to step 3
        triggerKeypressEvent('Enter');
        assert.strictEqual(appCreator.currentStep, 2,
            "currentStep should not be update because the input is not filled");
        appCreator.$('input[name="app_name"]').val('Kikou');

        // go to step 3
        triggerKeypressEvent('Enter');
        assert.strictEqual(appCreator.currentStep, 3,
            "currentStep should be 3");

        await testUtils.nextTick();  // wait for async update of studio
        // try to go to step 4
        triggerKeypressEvent('Enter');
        var $menu = appCreator.$('input[name="menu_name"]').parent();
        assert.hasClass($menu,'o_web_studio_app_creator_field_warning',
            "a warning should be displayed on the input");

        appCreator.destroy();
    });
});

});
