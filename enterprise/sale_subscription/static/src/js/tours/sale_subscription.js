odoo.define('sale_subscription.tour', function(require) {
"use_strict";

var core = require('web.core');
var tour = require('web_tour.tour');

var _t = core._t;

tour.register('sale_subscription_tour', {
	url: "/web",
}, [{
    trigger: '.o_app[data-menu-xmlid="sale_subscription.menu_sale_subscription_root"]',
	content: _t('Want recurring billing via subscription management ? Get started by clicking here'),
    position: 'bottom',
},
{
    trigger: '.dropdown-toggle[data-menu-xmlid="sale_subscription.menu_sale_subscription_config"]',
    content: _t('Configure your subscription templates here'),
    position: 'bottom',},
{
    trigger: '.o_menu_entry_lvl_2[data-menu-xmlid="sale_subscription.menu_template_of_subscription"]',
    content: _t('Click here to create <b>your first subscription template</b>'),
    position: 'top',
},
{
    trigger: '.o-kanban-button-new',
    content: _t('Let\'s create your first subscription template.'),
    position: 'bottom',
    width: 200,
},
{
    trigger: 'div.oe_title input',
    extra_trigger: '.o_form_editable',
    content: _t('Enter a name for this template.<br/><i>(e.g. eLearning Yearly)</i>'),
    position: 'right',
    width: 200,
},
{
    trigger: 'select.field_rule_type',
    extra_trigger: '.o_form_editable',
    content: _t('Choose the recurrence for this template.<br/><i>(e.g. 1 time per Year)</i>'),
    position: 'right',
    width: 200,
},
{
    trigger: '.o_form_button_save',
    content: _t('Save this template and the modifications you\'ve made to it.'),
    position: 'bottom',
},
{
    trigger: '.dropdown-toggle[data-menu-xmlid="sale_subscription.menu_sale_subscription"]',
    content: _t('Let\'s go to the catalog to create our first subscription product'),
    position: 'bottom',
},
{
    trigger: '.o_menu_entry_lvl_2[data-menu-xmlid="sale_subscription.menu_sale_subscription_product"]',
    content: _t('Create your first subscription product here'),
    position: 'top',
},
{
    trigger: '.o_list_button_add',
    content: _t('Go ahead and create a new product'),
    position: 'right',
    width: 200,
},
{
    trigger: 'input.o_field_widget[name="name"]',
    content: _t('Choose a product name.<br/><i>(e.g. eLearning Access)</i>'),
    position: 'right',
    width: 200,
},
{
    trigger: 'li.page_sales a',
    extra_trigger: '.o_form_editable',
    content: _t('Link your product to a subscription template in this tab'),
    position: 'top',
},
{
    trigger: '.o_field_widget.field_sub_template_id',
    extra_trigger: '.o_form_editable',
    content: _t('Select your newly created template. Every sale of this product will generate a new subscription!'),
    position: 'top',
},
{
    trigger: '.o_form_button_save',
    content: _t('Save and you\'re all set!<br/>Simply sell this product to create a subscription automatically or create a subscription manually!'),
    position: 'right',
    width: 400,
},
]);

});
