odoo.define('web_enterprise.kanban_mobile_tests', function (require) {
"use strict";

const KanbanView = require('web.KanbanView');
const {createView, dom} = require('web.test_utils');

QUnit.module('Views', {
    beforeEach() {
        this.data = {
            partner: {
                fields: {
                    foo: {string: "Foo", type: "char"},
                    bar: {string: "Bar", type: "boolean"},
                    int_field: {string: "int_field", type: "integer", sortable: true},
                    qux: {string: "my float", type: "float"},
                    product_id: {string: "something_id", type: "many2one", relation: "product"},
                    category_ids: { string: "categories", type: "many2many", relation: 'category'},
                    state: { string: "State", type: "selection", selection: [["abc", "ABC"], ["def", "DEF"], ["ghi", "GHI"]]},
                    date: {string: "Date Field", type: 'date'},
                    datetime: {string: "Datetime Field", type: 'datetime'},
                },
                records: [
                    {id: 1, bar: true, foo: "yop", int_field: 10, qux: 0.4, product_id: 3, state: "abc", category_ids: []},
                    {id: 2, bar: true, foo: "blip", int_field: 9, qux: 13, product_id: 5, state: "def", category_ids: [6]},
                    {id: 3, bar: true, foo: "gnap", int_field: 17, qux: -3, product_id: 3, state: "ghi", category_ids: [7]},
                    {id: 4, bar: false, foo: "blip", int_field: -4, qux: 9, product_id: 5, state: "ghi", category_ids: []},
                    {id: 5, bar: false, foo: "Hello \"World\"! #peace_n'_love", int_field: -9, qux: 10, state: "jkl", category_ids: []},
                ]
            },
            product: {
                fields: {
                    id: {string: "ID", type: "integer"},
                    name: {string: "Display Name", type: "char"},
                },
                records: [
                    {id: 3, name: "hello"},
                    {id: 5, name: "xmo"},
                ]
            },
            category: {
                fields: {
                    name: {string: "Category Name", type: "char"},
                    color: {string: "Color index", type: "integer"},
                },
                records: [
                    {id: 6, name: "gold", color: 2},
                    {id: 7, name: "silver", color: 5},
                ]
            },
        };
    },
}, function () {
    QUnit.test('kanban with searchpanel: rendering in mobile', async function (assert) {
        assert.expect(30);

        const kanban = await createView({
            View: KanbanView,
            model: 'partner',
            data: this.data,
            arch: `
                <kanban>
                    <templates><t t-name="kanban-box">
                        <div>
                            <field name="foo"/>
                        </div>
                    </t></templates>
                </kanban>
            `,
            archs: {
                'partner,false,search': `
                    <search>
                        <searchpanel>
                            <field name="product_id"/>
                            <field name="state" select="multi"/>
                        </searchpanel>
                    </search>
                `,
            },
            mockRPC(route, {method}) {
                assert.step(method || route);
                return this._super.apply(this, arguments);
            },
        });

        assert.containsOnce(kanban, 'details.o_search_panel');

        assert.verifySteps([
            'search_panel_select_range',
            'search_panel_select_multi_range',
            '/web/dataset/search_read',
        ]);

        const $searchPanel = kanban.$('details.o_search_panel');

        assert.isVisible($searchPanel.find('> summary'));
        assert.ok($searchPanel.find('> summary ~ *').is(':not(:visible)'),
            "content of the SearchPanel shouldn't be visible");

        // open the search panel
        await dom.click($searchPanel.find('> summary'));

        assert.ok($searchPanel.find('> summary ~ *').is(':visible'),
            "content of the SearchPanel should be visible");
        assert.containsOnce($searchPanel, '.o_search_panel_current_selection');
        assert.isVisible($searchPanel.find('> summary > div > .o_search_panel_mobile_close'));
        assert.containsN($searchPanel, '.o_search_panel_section', 2);

        // looking for 'category' sample section
        const $productSection = $searchPanel.find('.o_search_panel_section:first');
        assert.containsOnce($productSection, '.o_search_panel_section_header:contains(something_id)');
        assert.containsN($productSection, '.o_search_panel_category_value', 3);

        // select category
        await dom.click($productSection.find('.o_search_panel_category_value:contains(hello) label'));
        assert.containsOnce($searchPanel.find('.o_search_panel_current_selection'), '.o_search_panel_category:contains(hello)');
        assert.verifySteps([
            'search_panel_select_multi_range',
            '/web/dataset/search_read',
        ]);

        // looking for 'filter' sample section
        const $stateSection = $searchPanel.find('.o_search_panel_section:last');
        assert.containsOnce($stateSection, '.o_search_panel_section_header:contains(State)');
        assert.containsN($stateSection, '.o_search_panel_filter_value', 3);

        // select filter
        await dom.click($stateSection.find('.o_search_panel_filter_value:contains(DEF) input'));
        assert.containsOnce($searchPanel.find('.o_search_panel_current_selection'), '.o_search_panel_filter:contains(DEF)');
        assert.verifySteps([
            'search_panel_select_multi_range',
            '/web/dataset/search_read',
        ]);

        // close with back button
        assert.containsOnce($searchPanel, '.o_search_panel_mobile_close');
        await dom.click($searchPanel.find('.o_search_panel_mobile_close'));
        assert.ok($searchPanel.find('> summary ~ *').is(':not(:visible)'));

        // selection is kept when closed
        const $summaryCurrentSelection = $searchPanel.find('> summary .o_search_panel_current_selection');
        assert.containsOnce($summaryCurrentSelection, '.o_search_panel_category:contains(hello)');
        assert.containsOnce($summaryCurrentSelection, '.o_search_panel_filter:contains(DEF)');

        // open the search panel
        await dom.click($searchPanel.find('> summary'));
        assert.ok($searchPanel.find('> summary ~ *').is(':visible'));

        // close with bottom button
        assert.containsOnce($searchPanel, '.o_search_panel_mobile_bottom_close');
        await dom.click($searchPanel.find('.o_search_panel_mobile_bottom_close'));
        assert.ok($searchPanel.find('> summary ~ *').is(':not(:visible)'));

        kanban.destroy();
    });
});
});
