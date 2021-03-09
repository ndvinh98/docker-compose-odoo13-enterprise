odoo.define('web_studio.PivotEditor', function (require) {
"use strict";

var PivotRenderer = require('web.PivotRenderer');

var EditorMixin = require('web_studio.EditorMixin');

return PivotRenderer.extend(EditorMixin, {
    /**
     * @override
     */
    start: function () {
        // The pivot renderer is currently embedded inside a div ; this is
        // defined in the pivot controller. To keep the same style, we keep
        // the same dom here.

        // TODO: this is clearly a hack ; the renderer should be the only
        // widget defining its own dom (not its controller).
        var self = this;
        return this._super.apply(this, arguments).then(function () {
            self.$el.wrap($('<div>', {
                class: 'o_pivot',
            }));
            self.setElement(self.$el.parent());
        });
    },
});

});
