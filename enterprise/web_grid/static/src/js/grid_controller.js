odoo.define('web_grid.GridController', function (require) {
"use strict";

var AbstractController = require('web.AbstractController');
var config = require('web.config');
var core = require('web.core');
var dialogs = require('web.view_dialogs');
var utils = require('web.utils');
var concurrency = require('web.concurrency');

var qweb = core.qweb;
var _t = core._t;

var GridController = AbstractController.extend({
    custom_events: _.extend({}, AbstractController.prototype.custom_events, {
        'cell_edited': '_onCellEdited',
    }),
    events: {
        'click .o_grid_cell_information': '_onClickCellInformation',
        'focus .o_grid_input': '_onGridInputFocus',
    },

    /**
     * @override
     */
    init: function (parent, model, renderer, params) {
        this._super.apply(this, arguments);
        this.context = params.context;
        this.navigationButtons = params.navigationButtons;
        this.ranges = params.ranges;
        this.currentRange = params.currentRange;
        this.formViewID = params.formViewID;
        this.listViewID = params.listViewID;
        this.adjustment = params.adjustment;
        this.adjustName = params.adjustName;
        this.canCreate = params.activeActions.create;
        this.mutex = new concurrency.Mutex();
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @override
     * @param {jQueryElement} $node
     */
    renderButtons: function ($node) {
        this.$buttons = $(qweb.render('grid.GridArrows', { widget: {
            _ranges: this.ranges,
            _buttons: this.navigationButtons,
            allowCreate: this.canCreate,
        },
            isMobile: config.device.isMobile
        }));
        this.$buttons.appendTo($node);
        this._updateButtons();
        this.$buttons.on('click', '.o_grid_button_add', this._onAddLine.bind(this));
        this.$buttons.on('click', '.grid_arrow_previous', this._onPaginationChange.bind(this, 'prev'));
        this.$buttons.on('click', '.grid_button_initial', this._onPaginationChange.bind(this, 'initial'));
        this.$buttons.on('click', '.grid_arrow_next', this._onPaginationChange.bind(this, 'next'));
        this.$buttons.on('click', '.grid_arrow_range', this._onRangeChange.bind(this));
        this.$buttons.on('click', '.grid_arrow_button', this._onButtonClicked.bind(this));
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {Object} cell
     * @param {number} newValue
     * @returns {Promise}
     */
    _adjust: function (cell, newValue) {
        var difference = newValue - cell.value;
        // 1e-6 is probably an overkill, but that way milli-values are usable
        if (Math.abs(difference) < 1e-6) {
            // cell value was set to itself, don't hit the server
            return Promise.resolve();
        }
        // convert row values to a domain, concat to action domain
        var state = this.model.get();
        var domain = this.model.domain.concat(cell.row.domain);

        var self = this;
        return this.mutex.exec(function () {
            return self._rpc({
                model: self.modelName,
                method: self.adjustName,
                args: [ // args for type=object
                    [],
                    domain,
                    state.colField,
                    cell.col.values[state.colField][0],
                    state.cellField,
                    difference
                ],
                context: self.model.getContext()
            }).then(function () {
                return self.model.reload();
            }).then(function () {
                var state = self.model.get();
                return self.renderer.updateState(state, {});
            }).then(function () {
                self._updateButtons(state);
            });
        });
    },
    /**
     * @override
     * @private
     * @returns {Promise}
     */
    _update: function () {
        return this._super.apply(this, arguments)
            .then(this._updateButtons.bind(this));
    },
    /**
     * @private
     */
    _updateButtons: function () {
        if (this.$buttons) {
            var state = this.model.get();
            this.$buttons.find('.grid_arrow_previous').toggleClass('d-none', !state.prev);
            this.$buttons.find('.grid_arrow_next').toggleClass('d-none', !state.next);
            this.$buttons.find('.grid_button_initial').toggleClass('d-none', !state.initial);
            this.$buttons.find('.grid_arrow_range').removeClass('active');
            this.$buttons.find('.grid_arrow_range[data-name=' + this.currentRange + ']').addClass('active');
        }
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {MouseEvent} event
     */
    _onAddLine: function (event) {
        event.preventDefault();

        var context = this.model.getContext();
        var formContext = _.extend({}, context, {view_grid_add_line: true});
        // TODO: document quick_create_view (?) context key
        var formViewID = context.quick_create_view || this.formViewID || false;
        new dialogs.FormViewDialog(this, {
            res_model: this.modelName,
            res_id: false,
            context: formContext,
            view_id: formViewID,
            title: _t("Add a Line"),
            disable_multiple_selection: true,
            on_saved: this.reload.bind(this, {}),
        }).open();
    },
    /**
     * @private
     * @param {OdooEvent} e
     */
    _onCellEdited: function (event) {
        var state = this.model.get();
        this._adjust({
            row: utils.into(state, event.data.row_path),
            col: utils.into(state, event.data.col_path),
            value: utils.into(state, event.data.cell_path).value,
        }, event.data.value)
        .then(function () {
            if (event.data.doneCallback !== undefined) {
                event.data.doneCallback();
            }
        })
        .guardedCatch(function () {
            if (event.data.doneCallback !== undefined) {
                event.data.doneCallback();
            }
        })
    },
    /**
     * @private
     * @param {MouseEvent} e
     */
    _onButtonClicked: function (e) {
        var self = this;
        e.stopPropagation();
        // TODO: maybe allow opting out of getting ids?
        var button = this.navigationButtons[$(e.target).attr('data-index')];
        var actionData = _.extend({}, button, {
            context: this.model.getContext(button.context),
        });
        this.model.getIds().then(function (ids) {
            self.trigger_up('execute_action', {
                action_data: actionData,
                env: {
                    context: self.model.getContext(),
                    model: self.modelName,
                    resIDs: ids,
                },
                on_closed: self.reload.bind(self, {}),
            });
        });
    },
    /**
     * @private
     * @param {MouseEvent} e
     */
    _onClickCellInformation: function (e) {
        var self = this;
        var $target = $(e.target);
        var cell_path = $target.parent().attr('data-path').split('.');
        var row_path = cell_path.slice(0, -3).concat(['rows'], cell_path.slice(-2, -1));
        var state = this.model.get();
        var cell = utils.into(state, cell_path);
        var row = utils.into(state, row_path);

        var groupFields = state.groupBy.slice(_.isArray(state) ? 1 : 0);
        var label = _.map(groupFields, function (g) {
            return row.values[g][1] || _t('Undefined');
        }).join(': ');

        // pass group by, section and col fields as default in context
        var cols_path = cell_path.slice(0, -3).concat(['cols'], cell_path.slice(-1));
        var col = utils.into(state, cols_path);
        var column_value = col.values[state.colField][0];
        if(!column_value)
        {
            column_value = false;
        }
        else if(!_.isNumber(column_value))
        {
            column_value = column_value.split("/")[0]
        }
        var ctx = _.extend({}, this.context);

        var sectionField = _.find(this.renderer.fields ,function(res) {
            return self.model.sectionField === res.name;
        });
        if (this.model.sectionField && state.groupBy && state.groupBy[0] === this.model.sectionField) {
            var value = state[parseInt(cols_path[0])].__label;
            ctx['default_' + this.model.sectionField] = _.isArray(value) ? value[0] : value;
        }
        _.each(groupFields, function (field) {
            ctx['default_'+field] = row.values[field][0] || false;
        });

        ctx['default_'+state.colField] = column_value;

        ctx['create'] = !cell.readonly
        ctx['edit'] = !cell.readonly
        this.do_action({
            type: 'ir.actions.act_window',
            name: label,
            res_model: this.modelName,
            views: [
                [this.listViewID, 'list'],
                [this.formViewID, 'form']
            ],
            domain: cell.domain,
            context: ctx,
        });
    },
    /**
     * @private
     * @param {MouseEvent} e
     */
    _onGridInputFocus: function (e) {
        var selection = window.getSelection();
        var range = document.createRange();
        range.selectNodeContents(e.target);
        selection.removeAllRanges();
        selection.addRange(range);
    },
    /**
     * @private
     * @param {string} dir either 'prev', 'initial' or 'next
     */
    _onPaginationChange: function (dir) {
        var state = this.model.get();
        this.update({pagination: state[dir]});
    },
    /**
     * @private
     * @param {MouseEvent} e
     */
    _onRangeChange: function (e) {
        e.stopPropagation();
        var $target = $(e.target);
        if (config.device.isMobile) {
            $target.closest(".dropdown-menu").prev().dropdown("toggle");
        }
        if ($target.hasClass('active')) {
            return;
        }
        this.currentRange = $target.attr('data-name');
        this.update({range: this.currentRange});
    },
});

return GridController;

});
