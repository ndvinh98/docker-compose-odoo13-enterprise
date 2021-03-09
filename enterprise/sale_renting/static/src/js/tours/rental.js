odoo.define('sale_renting.tour', function (require) {
"use strict";

var core = require('web.core');
var tour = require('web_tour.tour');

var _t = core._t;

tour.register('rental_tour', {
    url: "/web",
}, [tour.STEPS.SHOW_APPS_MENU_ITEM, {
    trigger: '.o_app[data-menu-xmlid="sale_renting.rental_menu_root"]',
    content: _t("Want to <b>rent products</b>? \n Let's discover Odoo Rental App."),
    position: 'bottom',
    edition: 'enterprise'
}, {
    trigger: '.o_menu_entry_lvl_1[data-menu-xmlid="sale_renting.menu_rental_products"]',
    content: _t("At first, let's create some products to rent."),
    position: 'bottom',
}, {
    trigger: '.o-kanban-button-new',
    extra_trigger: '.breadcrumb-item:contains(Products)',
    content: _t("Click here to set up your first rental product."),
    position: 'bottom',
}, {
    trigger: "input[name='name']",
    content: _t("Enter the product name."),
    position: 'bottom',
}, {
    trigger: ".nav-item a.nav-link:contains(Rental)",
    content: _t("The rental configuration is available here."),
    position: 'top',
}, {
    trigger: '.o_form_button_save',
    content: _t("Save the product."),
    position: 'bottom',
}, {
    trigger: '.o_menu_header_lvl_1[data-menu-xmlid="sale_renting.rental_order_menu"]',
    extra_trigger: '.o_form_button_edit',
    content: _t("Let's now create an order."),
    position: 'bottom',
}, {
    trigger: '.o_menu_entry_lvl_2[data-menu-xmlid="sale_renting.rental_orders_all"]',
    content: _t("Go to the orders menu."),
    position: 'bottom',
}, {
    trigger: '.o-kanban-button-new',
    content: _t("Click here to create a new quotation."),
    position: 'bottom',
}, {
    trigger: ".o_field_many2one[name=partner_id] input",
    content: _t("Create or select a customer here."),
    position: 'bottom',
    run: 'text Agrolait',
}, {
    trigger: '.ui-menu-item > a',
    auto: true,
    in_modal: false,
}, {
    trigger: "a:contains('Add a product')",
    extra_trigger: ".o_field_many2one[name='partner_id'] .o_external_button",
    content: _t("Click here to start filling the quotation."),
    position: 'bottom',
}, {
    trigger: ".o_field_widget[name=product_id] input, .o_field_widget[name=product_template_id] input",
    content: _t("Select your rental product."),
    position: 'bottom',
}, {
    trigger: ".ui-menu-item a:contains('Test')",
    auto: true,
}, {
    trigger: "button[special=save]",
    extra_trigger: ".o_form_nosheet",
    content: _t("Enter the requested dates and check the price.\n Then, click here to add the product."),
    position: 'bottom',
}, {
    trigger: '.o_form_button_save',
    extra_trigger: '.o_sale_order',
    content: _t("Save the quotation."),
    position: 'bottom',
}, {
    trigger: 'button[name=action_confirm]',
    extra_trigger: '.o_form_button_edit',
    content: _t("Confirm the order when the customer agrees with the terms."),
    position: 'bottom',
}, {
    trigger: 'button[name=open_pickup]',
    extra_trigger: '.o_sale_order',
    content: _t("Click here to register the pickup."),
    position: 'bottom',
}, {
    trigger: "button[name='apply']",
    content: _t("Validate the operation after checking the picked-up quantities."),
    position: 'bottom',
}, {
    trigger: "button[name='open_return']",
    extra_trigger: '.o_sale_order',
    content: _t("Once the rental is done, you can register the return."),
    position: 'bottom',
}, {
    trigger: "button[name='apply']",
    content: _t("Confirm the returned quantities and hit Validate."),
    position: 'bottom',
}]);

// message to do : You're done with your fist rental. Congratulations !

});
