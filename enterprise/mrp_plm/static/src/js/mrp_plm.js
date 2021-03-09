odoo.define('mrp_plm.update_kanban', function (require) {
"use strict";


var core = require('web.core');
var KanbanRecord = require('web.KanbanRecord');
var QWeb = core.qweb;


KanbanRecord.include({
    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @override
     * @private
     */
    _onKanbanActionClicked: function (ev) {
        var self = this;
        if (this.modelName === 'mrp.eco' && $(ev.currentTarget).data('type') === 'set_cover') {
            ev.preventDefault();
            this._rpc({
                    model: 'mrp.document',
                    method: 'search_read',
                    fields: ['id', 'name', 'ir_attachment_id'],
                    domain: [['res_model', '=', 'mrp.eco'], ['res_id', '=', this.id], ['mimetype', 'ilike', 'image']],
                })
                .then(function (attachment_ids) {
                    var $cover_modal = $(QWeb.render("mrp_plm.SetCoverModal", {
                        widget: self,
                        attachment_ids: attachment_ids,
                    }));

                    $cover_modal.appendTo($('body'));
                    $cover_modal.modal('toggle');
                    $cover_modal.on('click', 'img', function (ev) {
                        self._updateRecord({
                            displayed_image_id: {
                                id: $(ev.currentTarget).data('id'),
                            },
                        });
                        $cover_modal.modal('toggle');
                        $cover_modal.remove();
                    });
                });
        } else {
            this._super.apply(this, arguments);
        }
    },
});

});
