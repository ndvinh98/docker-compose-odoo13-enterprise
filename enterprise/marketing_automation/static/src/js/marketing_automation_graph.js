odoo.define('marketing_automation.activity_graph', function (require) {
'use strict';

var AbstractField = require('web.AbstractField');
var registry = require('web.field_registry');

var ActivityGraph = AbstractField.extend({
    className: 'o_ma_activity_graph',
    jsLibs: [
        '/web/static/lib/Chart/Chart.js',
    ],

    /**
     * @private
     * @override _init to set data
     */
    init: function () {
        this._super.apply(this, arguments);
        this._isInDOM = false;
        this.chart = null;
        this.chartId =  _.uniqueId('chart');
        this.data = JSON.parse(this.value);
    },

    start: function () {
        var $canvasContainer = $('<div/>', {class: 'o_graph_canvas_container'});
        this.$canvas = $('<canvas/>').attr('id', this.chartId);
        $canvasContainer.append(this.$canvas);
        this.$el.append($canvasContainer);
        return this._super.apply(this, arguments);
    },

    on_attach_callback: function () {
        this._isInDOM = true;
        this._render();
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @private
     * @override
     */
    _render: function () {
        if (!this._isInDOM) {
            return;
        }
        if(!this.data || !_.isArray(this.data)){
            return;
        }

        function hexToRGBA (hex, opacity) {
            var result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
            var rgb = result.slice(1, 4).map(function (n) {
                    return parseInt(n, 16);
                }).join(',');
            return 'rgba(' + rgb + ',' + opacity + ')';
        }

        var labels = this.data[0].points.map(function (point) {
            return point.x;
        });

        var datasets = this.data.map(function (group) {
            var borderColor = hexToRGBA(group.color, 1);
            var fillColor = hexToRGBA(group.color, 0.6);
            return {
                label: group.label,
                data: group.points,
                fill: 'origin',
                backgroundColor: fillColor,
                borderColor: borderColor,
                borderWidth: 2,
                pointBackgroundColor: 'rgba(0, 0, 0, 0)',
                pointBorderColor: borderColor,
            };
        });

        Chart.defaults.global.elements.line.tension = 0;

        var ctx = document.getElementById(this.chartId);
        this.chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: datasets,
            },
            options: {
                layout: {
                    padding: {left: 25, right: 20, top: 5, bottom: 20}
                },
                legend: {
                    display: false,
                },
                maintainAspectRatio: false,
                scales: {
                    yAxes: [{
                        type: 'linear',
                        display: false,
                        ticks: {
                            beginAtZero: true,
                        },
                    }],
                    xAxes: [{
                        ticks: {
                            maxRotation: 0,
                        },
                    }],
                },
                tooltips: {
                    mode: 'index',
                    intersect: false,
                    bodyFontColor: 'rgba(0,0,0,1)',
                    titleFontSize: 13,
                    titleFontColor: 'rgba(0,0,0,1)',
                    backgroundColor: 'rgba(255,255,255,0.6)',
                    borderColor: 'rgba(0,0,0,0.2)',
                    borderWidth: 2,
                    callbacks: {
                        labelColor: function (tooltipItem, chart) {
                            var dataset = chart.data.datasets[tooltipItem.datasetIndex];
                            var tooltipBorderColor = chart.tooltip._model.backgroundColor;
                            return {
                                borderColor: tooltipBorderColor,
                                backgroundColor: dataset.backgroundColor,
                            };
                        },
                    }
                }
            }
        });
    },
});

registry.add('marketing_activity_graph', ActivityGraph);

return ActivityGraph;

});
