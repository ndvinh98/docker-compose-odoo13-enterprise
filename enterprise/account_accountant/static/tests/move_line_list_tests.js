odoo.define('account_accountant.MoveLineListViewTests', function (require) {
    "use strict";

    var config = require('web.config');
    var testUtils = require('web.test_utils');
    var MoveLineListView = require('account_accountant.MoveLineListView').AccountMoveListView;

    var createView = testUtils.createView;

    QUnit.module('Views', {
        beforeEach: function () {
            this.data = {
                'account.move.line': {
                    fields: {
                        move_id: {type: 'many2one', relation: 'account.move'},
                        move_attachment_ids: {type: 'one2many', relation: 'ir.attachment'},

                    },
                    records: [
                        {id: 1, name: "line1", move_id: 1},
                        {id: 2, name: "line2", move_id: 1},
                        {id: 3, name: "line3", move_id: 2},
                        {id: 4, name: "line4", move_id: 2},
                    ],
                },
                'account.move': {
                    fields: {},
                    records: [
                        {id: 1, name: "move1"},
                        {id: 2, name: "move2"},
                    ],
                },
                'ir.attachment': {
                    fields: {
                        res_id: {type: 'integer'},
                        res_model: {type: 'char'},
                        mimetype: {type: 'char'},
                    },
                    records: [
                        {id: 1, res_id: 1, res_model: 'account.move.line', mimetype: 'application/pdf'},
                        {id: 2, res_id: 2, res_model: 'account.move.line', mimetype: 'application/pdf'},
                    ],
                },
            };
        }
    }, function () {

        QUnit.module('MoveLineListView');

        QUnit.test('No preview on small devices', async function (assert) {
            assert.expect(6);

            this.data['account.move.line'].records[2].move_attachment_ids = [1];
            this.data['account.move.line'].records[3].move_attachment_ids = [2];

            var list = await createView({
                View: MoveLineListView,
                model: 'account.move.line',
                data: this.data,
                arch: "<tree editable='bottom' js_class='account_move_line_list'>" +
                    "<field name='id'/>" +
                    "<field name='name'/>" +
                    "<field name='move_attachment_ids' invisible='1'/>" +
                    "</tree>",
                mockRPC: function (route, args) {
                    if (route.indexOf('/web/static/lib/pdfjs/web/viewer.html') !== -1) {
                        throw new Error('the pdf should not be loaded on small screens');
                    }
                    if (args.method === 'register_as_main_attachment') {
                        return Promise.resolve(true);
                    }
                    var method = args.method || route;
                    assert.step(method + '/' + args.model);
                    if (args.model === 'ir.attachment' && args.method === 'read') {
                        throw new Error('the attachments should not be read on small screens');
                    }
                    return this._super.apply(this, arguments);
                },
                groupBy: ['move_id'],
                config: {
                    device: {
                        size_class: config.device.SIZES.XL,
                    },
                },
            });

            assert.verifySteps(['web_read_group/account.move.line']);
            assert.containsOnce(list, '.o_move_line_list_view',
                "the class should be set");
            assert.containsNone(list, '.o_attachment_preview',
                "there should be no attachment preview on small screens");

            await testUtils.dom.click(list.$('.o_group_header:eq(1)'));
            assert.verifySteps(['/web/dataset/search_read/account.move.line'],
                "should not read attachments");

            list.destroy();
        });

        QUnit.test('Fetch and preview of attachments on big devices', async function (assert) {
            assert.expect(21);

            this.data['account.move.line'].records[2].move_attachment_ids = [1];
            this.data['account.move.line'].records[3].move_attachment_ids = [2];

            var list = await createView({
                View: MoveLineListView,
                model: 'account.move.line',
                data: this.data,
                arch: "<tree editable='bottom' js_class='account_move_line_list'>" +
                        "<field name='id'/>" +
                        "<field name='name'/>" +
                        "<field name='move_attachment_ids' invisible='1'/>" +
                    "</tree>",
                mockRPC: function (route, args) {
                    if (route.indexOf('/web/static/lib/pdfjs/web/viewer.html') !== -1) {
                        return Promise.resolve();
                    }
                    if (args.method === 'register_as_main_attachment') {
                        return Promise.resolve(true);
                    }
                    var method = args.method || route;
                    assert.step(method + '/' + args.model);
                    if (args.model === 'ir.attachment' && args.method === 'read') {
                        assert.deepEqual(args.args, [[1, 2], ["mimetype"]]);
                    }
                    return this._super.apply(this, arguments);
                },
                groupBy: ['move_id'],
                config: {
                    device: {
                        size_class: config.device.SIZES.XXL,
                    },
                },
            });

            assert.verifySteps(['web_read_group/account.move.line']);
            assert.containsOnce(list, '.o_move_line_list_view',
                "the class should be set");
            assert.containsOnce(list, '.o_attachment_preview',
                "there should be an attachment preview");
            assert.containsOnce(list, '.o_attachment_preview .o_move_line_empty',
                "the attachment preview should be empty");

            await testUtils.dom.click(list.$('.o_group_header:eq(0)'));
            assert.verifySteps(['/web/dataset/search_read/account.move.line']);

            await testUtils.dom.click(list.$('.o_data_row:eq(0) .o_data_cell:eq(1)'));
            assert.containsOnce(list, '.o_attachment_preview .o_move_line_without_attachment',
                "an empty message should be displayed");

            await testUtils.dom.click(list.$('.o_data_row:eq(1) .o_data_cell:eq(1)'));
            assert.verifySteps([], "no extra rpc should be done");
            assert.containsOnce(list, '.o_attachment_preview .o_move_line_without_attachment',
                "the empty message should still be displayed");

            await testUtils.dom.click(list.$('.o_group_header:eq(1)'));
            assert.verifySteps(['/web/dataset/search_read/account.move.line', 'read/ir.attachment']);
            await testUtils.dom.click(list.$('.o_data_row:eq(2) .o_data_cell:eq(1)'));
            assert.hasAttrValue(list.$('.o_attachment_preview iframe'), 'data-src',
                '/web/static/lib/pdfjs/web/viewer.html?file=/web/content/1?filename%3Dundefined',
                "the src attribute should be correctly set on the iframe");

            await testUtils.dom.click(list.$('.o_data_row:eq(3) .o_data_cell:eq(1)'));
            assert.hasAttrValue(list.$('.o_attachment_preview iframe'), 'data-src',
                '/web/static/lib/pdfjs/web/viewer.html?file=/web/content/2?filename%3Dundefined',
                "the src attribute should still be correctly set on the iframe");

            // reload with groupBy
            await list.reload({ groupBy: ['move_id', 'move_attachment_ids'] });
            await testUtils.dom.click(list.$('.o_group_header:eq(1)'));
            // clicking on group header line should not do read call to ir.attachment
            assert.verifySteps(["web_read_group/account.move.line",
                "web_read_group/account.move.line",
                "web_read_group/account.move.line",
                "/web/dataset/search_read/account.move.line"]);

            list.destroy();
        });
    });

});
