odoo.define('account_invoice_extract.testUtils', function (require) {
"use strict";

var InvoiceExtractBoxLayer = require('account_invoice_extract.BoxLayer');

var testUtils = require('web.test_utils');

/**
 * @param {Object} params
 * @param {string} params.fieldName
 * @param {integer} params.id
 * @param {intger} [params.page=0]
 * @param {integer} params.selected_status
 * @param {boolean} params.user_selected
 */
function createBoxData(params) {
    return {
        box_angle: 0, // no angle
        box_height: 0.2, // 20% of the box layer for the height
        box_midX: 0.5, // box in the middle of box layer (horizontally)
        box_midY: 0.5, // box in the middle of box layer (vertically)
        box_width: 0.2, // 20% of the box layer of the width
        feature: params.fieldName,
        id: params.id,
        page: params.page || 0, // which box layer this box is linked to
        selected_status: params.selected_status, // if value != 0, OCR chosen
        user_selected: params.user_selected,
    };
}

/**
 * Important: the field name of boxes should be compatible.
 * @see account_invoice_extract.Fields:init
 *
 * @returns {Object[]}
 */
function createBoxesData() {
    // 'VAT_Number' boxes: not selected, ocr chosen, user selected
    var vatBoxes = [
        createBoxData({
            fieldName: 'VAT_Number',
            id: 1,
            selected_status: 0,
            user_selected: false,
        }),
        createBoxData({
            fieldName: 'VAT_Number',
            id: 2,
            selected_status: 1,
            user_selected: false,
        }),
        createBoxData({
            fieldName: 'VAT_Number',
            id: 3,
            selected_status: 0,
            user_selected: true,
        })
    ];
    // 'invoice_id' boxes: not selected, ocr chosen
    var InvoiceIdBoxes = [
        createBoxData({
            fieldName: 'invoice_id',
            id: 4,
            selected_status: 0,
            user_selected: false,
        }),
        createBoxData({
            fieldName: 'invoice_id',
            id: 5,
            selected_status: 1,
            user_selected: false,
        }),
    ];
    var boxes = vatBoxes.concat(InvoiceIdBoxes);
    return boxes;
}

/**
 * @param {Object} [params={}]
 * @param {Object[]} [params.boxesData] @see createBoxesData if not set
 * @param {web.Widget} [params.parent]
 * @param {integer} [params.pageNum=0]
 * @returns {Object}
 */
async function createBoxLayer(params) {
    params = params || {};
    var $page = $('<div>', { class: 'page' });
    $page.css('height', 100);
    $page.css('width', 200);

    if (!params.parent) {
        var parentParams = {};
        if ('debug' in params) {
            parentParams.debug = params.debug;
        }
        if ('intercepts' in params) {
            parentParams.intercepts = params.intercepts;
        }
        _.extend(parentParams.session, {}, {
            user_has_group: function () {
                return Promise.resolve();
            }
        });
        params.parent = testUtils.createParent(parentParams);
    }

    var boxLayer = new InvoiceExtractBoxLayer(params.parent, {
        boxesData: params.boxesData || createBoxesData(),
        mode: 'img',
        pageNum: params.pageNum || 0,
        $page: $page,
    });

    var $target = params.debug ? $('body') : $('#qunit-fixture');
    $page.appendTo($target);
    return boxLayer.appendTo($target).then(function () {
        return {
            boxLayer: boxLayer,
            parent: params.parent,
        };
    });

}

return {
    createBoxData: createBoxData,
    createBoxesData: createBoxesData,
    createBoxLayer: createBoxLayer,
};

});
