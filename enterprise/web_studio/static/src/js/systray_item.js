odoo.define('web_studio.SystrayItem', function (require) {
"use strict";

var SystrayMenu = require('web.SystrayMenu');
var Widget = require('web.Widget');


/*
 * Menu item appended in the systray part of the navbar
 */

var SystrayItem = Widget.extend({
    events: {
        'click': '_onClick',
    },
    // force this item to be the first one to the left of the UserMenu in the
    // systray
    sequence: 1,
    template: 'web_studio.SystrayItem',
    /**
     * @constructor
     */
    init: function () {
        this._super.apply(this, arguments);
        this.disabled = true;
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Disable the item.
     */
    disable: function () {
        this.disabled = true;
        this.renderElement();
    },
    /**
     * Enable the item.
     */
    enable: function () {
        this.disabled = false;
        this.renderElement();
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {Event} event
     */
    _onClick: function (event) {
        event.preventDefault();
        this.disable();
        this.trigger_up('studio_icon_clicked');
    },
});

SystrayMenu.Items.unshift(SystrayItem);

return SystrayItem;

});
