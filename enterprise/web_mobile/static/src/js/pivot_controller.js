odoo.define('web_mobile.PivotController', function (require) {
'use strict';

var config = require('web.config');

if (!config.device.isMobile) {
    return;
}

var PivotController = require('web.PivotController');

PivotController.include({
    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Remove pseudo css class from HTMLElement (like :hover)
     *
     * @private
     * @param {HTMLElement} node
     */
    _removePseudoCssClass: function (node) {
        var $node = $(node);
        var $original = $node.clone(true);
        $node.replaceWith($original);
    },
    /**
     * @override
     * @private
     */
    _renderGroupBySelection: function () {
        this._super.apply(this, arguments);
        this.$('.o_pivot_header_cell_opened,.o_pivot_header_cell_closed').tooltip('hide');
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @override
     * @private
     * @param {MouseEvent} ev
     */
    _onGroupByMenuSelection: function (ev) {
        var $parent = $(ev.target).closest('.o_pivot_field_menu');
        if ($parent.length) {
            // Use vanillaJS node because jQuery doesn't support :hover selector
            var currentMenu = $parent.get(0).querySelector('.dropdown-item:hover');
            if (currentMenu === ev.target) {
                var parentNodeItem = currentMenu.parentNode;
                if (parentNodeItem && parentNodeItem.classList.contains('o_inline_dropdown')) {
                    if (currentMenu.classList.contains('o_dropdown_open')) {
                        currentMenu.classList.remove('o_dropdown_open');
                        this._removePseudoCssClass(currentMenu);
                    } else {
                        currentMenu.classList.add('o_dropdown_open');
                    }
                    ev.stopPropagation();
                    return false;
                }
            }
        }
        return this._super.apply(this, arguments);
    },
});

});
