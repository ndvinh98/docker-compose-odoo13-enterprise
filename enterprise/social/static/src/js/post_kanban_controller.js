odoo.define('social.social_post_kanban_controller', function (require) {
"use strict";

var KanbanController = require('web.KanbanController');
var PostKanbanImagesCarousel = require('social.social_post_kanban_images_carousel');

var PostKanbanController = KanbanController.extend({
    events: {
        'click .o_social_stream_post_image_more, .o_social_stream_post_image_click': '_onClickMoreImages'
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Shows a bootstrap carousel starting at the clicked image's index
     *
     * @param {MouseEvent} ev
     */
    _onClickMoreImages: function (ev) {
        ev.stopPropagation();
        var $target = $(ev.currentTarget);

        new PostKanbanImagesCarousel(
            this, {
                'activeIndex': $target.data('currentIndex'),
                'images': $target.closest('.o_social_stream_post_image').data('images')
            }
        ).open();
    },
});

return PostKanbanController;

});
