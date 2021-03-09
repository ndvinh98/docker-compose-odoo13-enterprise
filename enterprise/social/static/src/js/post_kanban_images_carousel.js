odoo.define('social.social_post_kanban_images_carousel', function (require) {
"use strict";

var core = require('web.core');
var Dialog = require('web.Dialog');
var _t = core._t;

/**
 * Simple Dialog extension for the social.stream.post kanban that shows a bootstrap carousel with
 * the specified options.images
 */
var PostKanbanImagesCarousel = Dialog.extend({
    template: 'social.PostKanbanImagesCarousel',

    init: function (parent, options) {
        options = _.defaults(options || {}, {
            title: _t('Post Images'),
            renderFooter: false,
            dialogClass: 'p-0 bg-900'
        });

        this.images = options.images;
        this.activeIndex = options.activeIndex || 0;

        this._super.apply(this, arguments);
    }
});

return PostKanbanImagesCarousel;

});
