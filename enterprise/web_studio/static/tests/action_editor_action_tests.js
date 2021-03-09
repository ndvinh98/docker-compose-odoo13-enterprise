odoo.define('web_studio.ActionEditorActionTests', function (require) {
    "use strict";

    var testUtils = require('web.test_utils');

    var createActionManager = testUtils.createActionManager;

    QUnit.module('Studio', {
        beforeEach: function () {
            this.data = {
                kikou: {
                    fields: {
                        display_name: { type: "char" },
                        start: { type: 'datetime', store: 'true' },
                    },
                },
                'res.groups': {
                    fields: {
                        display_name: { string: "Display Name", type: "char" },
                    },
                    records: [{
                        id: 4,
                        display_name: "Admin",
                    }],
                },
            };
        }
    }, function () {

        QUnit.module('ActionEditorAction');

        QUnit.test('add a gantt view', async function (assert) {
            assert.expect(5);

            var actionManager = await createActionManager({
                actions: this.actions,
                data: this.data,
                mockRPC: function (route, args) {
                    if (route === '/web_studio/add_view_type') {
                        assert.strictEqual(args.view_type, 'gantt',
                            "should add the correct view");
                        return Promise.resolve(false);
                    } else if (args.method === 'fields_get') {
                        assert.strictEqual(args.model, 'kikou',
                            "should read fields on the correct model");
                    }
                    return this._super.apply(this, arguments);
                },
            });
            await actionManager.doAction('action_web_studio_action_editor', {
                action: {
                    res_model: 'kikou',
                    view_mode: 'list',
                    views: [[1, 'list'], [2, 'form']],
                },
                noEdit: true,
            });

            await testUtils.dom.click(actionManager.$('.o_web_studio_view_type[data-type="gantt"] .o_web_studio_thumbnail'));

            assert.containsOnce($, '.o_web_studio_new_view_modal',
                "there should be an opened dialog to select gantt attributes");
            assert.strictEqual($('.o_web_studio_new_view_modal select[name="date_start"]').val(), 'start',
                "date start should be prefilled (mandatory)");
            assert.strictEqual($('.o_web_studio_new_view_modal select[name="date_stop"]').val(), 'start',
                "date stop should be prefilled (mandatory)");

            actionManager.destroy();
        });

        QUnit.test('disable the view from studio', async function (assert) {
            assert.expect(3);

            let loadActionStep = 0;
            const actionManager = await createActionManager({
                actions: [{
                    id: 1,
                    name: 'Kikou Action',
                    res_model: 'kikou',
                    type: 'ir.actions.act_window',
                    view_mode: 'list,form',
                    views: [[1, 'list'], [2, 'form']],
                }],
                data: this.data,
                archs: {
                    'kikou,1,list': `<tree><field name="display_name"/></tree>`,
                    'kikou,1,search': `<search></search>`,
                    'kikou,2,form': `<form><field name="display_name"/></form>`,
                },
                async mockRPC(route) {
                    if (route === '/web_studio/edit_action') {
                        return true;
                    } else if (route === '/web/action/load') {
                        loadActionStep++;
                        /**
                         * step 1: initial action/load
                         * step 2: on disabling list view
                         */
                        if (loadActionStep === 2) {
                            return {
                                name: 'Kikou Action',
                                res_model: 'kikou',
                                view_mode: 'form',
                                type: 'ir.actions.act_window',
                                views: [[2, 'form']],
                                id: 1,
                            };
                        }
                    }
                    return this._super(...arguments);
                },
                intercepts: {
                    do_action(ev) {
                        actionManager.doAction(ev.data.action, ev.data.options);
                    },
                },
            });
            await actionManager.doAction(1);
            const action = actionManager.getCurrentAction();
            await actionManager.doAction('action_web_studio_action_editor', {
                action: action,
                noEdit: true,
            });
            // make list view disable and form view only will be there in studio view
            await testUtils.dom.click(actionManager.$('div[data-type="list"] .o_web_studio_more'));
            await testUtils.dom.click(actionManager.$('div[data-type="list"] a[data-action="disable_view"]'));
            // reloadAction = false;
            assert.hasClass(
                actionManager.$('div[data-type="list"]'),
                'o_web_studio_inactive',
                "list view should have become inactive");

            // make form view disable and it should prompt the alert dialog
            await testUtils.dom.click(actionManager.$('div[data-type="form"] .o_web_studio_more'));
            await testUtils.dom.click(actionManager.$('div[data-type="form"] a[data-action="disable_view"]'));
            assert.containsOnce(
                $,
                '.o_technical_modal',
                "should display a modal when attempting to disable last view");
            assert.strictEqual(
                $('.o_technical_modal .modal-body').text().trim(),
                "You cannot deactivate this view as it is the last one active.",
                "modal should tell that last view cannot be disabled");

            actionManager.destroy();
        });

        QUnit.test('add groups on action', async function (assert) {
            assert.expect(1);

            var actionManager = await createActionManager({
                actions: this.actions,
                data: this.data,
                mockRPC: function (route, args) {
                    if (route === '/web_studio/edit_action') {
                        assert.strictEqual(args.args.groups_id[0], 4,
                            "group admin should be applied on action");
                        return Promise.resolve();
                    }
                    return this._super.apply(this, arguments);
                },
            });
            await actionManager.doAction('action_web_studio_action_editor', {
                action: {
                    res_model: 'kikou',
                    view_mode: 'list',
                    views: [[1, 'list'], [2, 'form']],
                },
                noEdit: true,
            });

            await testUtils.fields.many2one.clickOpenDropdown('groups_id');
            await testUtils.fields.many2one.clickHighlightedItem('groups_id');

            actionManager.destroy();
        });
    });

});
