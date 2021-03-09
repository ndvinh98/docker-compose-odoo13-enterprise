odoo.define('web_map.view_view_tests', function (require) {
    'use strict';
    var MapView = require('web_map.MapView');
    var MapModel = require('web_map.MapModel');
    var testUtils = require('web.test_utils');
    var createView = testUtils.createAsyncView;
    QUnit.module('mapView', {
        beforeEach: function () {
            this.data = {

                'project.task': {
                    fields: {
                        display_name: { string: "name", type: "char" },
                        sequence: { string: "sequence", type: 'integer' },
                        partner_id: { string: "partner", type: "many2one", relation: 'res.partner' },
                        another_partner_id: { string: "another relation", type: "many2one", relation: 'res.partner}'},
                    },
                    records: [
                        { id: 1, display_name: "project", partner_id: [1] }
                    ],
                    oneRecord: {
                        records: [
                            {id: 1, display_name: "Foo", partner_id: [1]}
                        ],
                        length: 1
                    },

                    twoRecords: {
                        records: [
                            {id: 1, display_name: "FooProject", sequence: 1, partner_id: [1]},
                            {id: 2, display_name: 'BarProject', sequence: 2, partner_id: [2]},
                        ],
                        length: 2
                    },

                    threeRecords: {
                        records: [
                            {id: 1, display_name: "FooProject", sequence: 1, partner_id: [1]},
                            {id: 2, display_name: 'BarProject', sequence: 2, partner_id: [2]},
                            {id: 1, display_name: "FooBarProject", sequence: 3, partner_id: [1]}
                        ],
                        length: 3
                    },

                    twoRecordOnePartner: {
                        records: [
                            {id: 1, display_name: "FooProject", partner_id: [1]},
                            {id: 2, display_name: 'BarProject', partner_id: [1]},
                        ],
                        length: 2
                    },
                    noRecord: {
                        records: [],
                        length: 0
                    },
                    recordWithouthPartner: {
                        records: [
                            {id: 1, display_name: "Foo", partner_id: []}
                        ],
                        length: 1
                    },
                    anotherPartnerId: {
                        records: [
                            {id: 1, display_name: "FooProject", another_partner_id: [1]},
                        ],
                        length: 1
                    }
                },

                'res.partner': {
                    fields: {
                        name: {string: "Customer", type: "char"},
                        'partner_latitude': {string: "Latitude", type: "float"},
                        'partner_longitude': {string: "Longitude", type: "float"},
                        'contact_address_complete': {string: 'Address', type: "char"},
                        'task_ids': {
                            string: 'Task',
                            type: "one2many",
                            relation: "project.task",
                            relation_field: "partner_id"
                        },
                        sequence: {string: 'sequence', type: 'integer'}
                    },

                    records: [
                        {
                            id: 1, name: 'Foo', 'partner_latitude': 10.0, 'partner_longitude': 10.5,
                            'contact_address_complete': 'Chaussée de Namur 40, 1367, Ramillies', sequence: 1
                        },
                        {
                            id: 2, name: 'Foo', 'partner_latitude': 10.0, 'partner_longitude': 10.5,
                            'contact_address_complete': 'Chaussée de Namur 40, 1367, Ramillies', sequence: 3
                        },

                    ],

                    coordinatesNoAddress: [
                        {
                            id: 1, name: 'Foo', 'partner_latitude': 10.0, 'partner_longitude': 10.5
                        }
                    ],

                    oneLocatedRecord: [

                        {
                            id: 1, name: 'Foo', 'partner_latitude': 10.0, 'partner_longitude': 10.5,
                            'contact_address_complete': 'Chaussée de Namur 40, 1367, Ramillies', sequence: 1
                        },

                    ],

                    wrongCoordinatesNoAddress: [
                        {
                            id: 1, name: 'Foo', 'partner_latitude': 10000.0, 'partner_longitude': 100000.5
                        }
                    ],

                    noCoordinatesGoodAddress: [
                        {
                            id: 1, name: 'Foo', 'partner_latitude': 0, 'partner_longitude': 0,
                            'contact_address_complete': 'Chaussée de Namur 40, 1367, Ramillies'
                        }
                    ],

                    emptyRecords: [],

                    twoRecordsAddressNoCoordinates:
                        [
                            {
                                id: 2, name: 'Foo',
                                'contact_address_complete': 'Chaussée de Namur 40, 1367, Ramillies', sequence: 3
                            },
                            {
                                id: 1, name: 'Bar',
                                'contact_address_complete': 'Chaussée de Louvain 94, 5310 Éghezée', sequence: 1
                            },
                        ],
                    twoRecordsAddressCoordinates:
                        [
                            {
                                id: 2, name: 'Foo', 'partner_latitude': 10.0, 'partner_longitude': 10.5,
                                'contact_address_complete': 'Chaussée de Namur 40, 1367, Ramillies', sequence: 3
                            },
                            {
                                id: 1, name: 'Bar', 'partner_latitude': 10.0, 'partner_longitude': 10.5,
                                'contact_address_complete': 'Chaussée de Louvain 94, 5310 Éghezée', sequence: 1
                            },
                        ],
                    twoRecordsOneUnlocated:
                        [
                            {
                                id: 1, name: 'Foo',
                                'contact_address_complete': 'Chaussée de Namur 40, 1367, Ramillies', sequence: 3
                            },
                            {
                                id: 2, name: 'Bar',
                            },
                        ],

                    unlocatedRecords:
                        [
                            {id: 1, name: 'Foo'},
                        ],

                    noCoordinatesWrongAddress:
                        [
                            {
                                id: 1, name: 'Foo',
                                'contact_address_complete': 'Cfezfezfefes'
                            }
                        ],
                }
            };
            testUtils.mock.patch(MapView, {});
            testUtils.mock.patch(MapModel, {

                _fetchCoordinatesFromAddressMB: function (record) {
                    if (this.data.mapBoxToken !== 'token') {
                        return Promise.reject({status: 401});
                    }
                    var coordinates = [];
                    coordinates[0] = 10.0;
                    coordinates[1] = 10.5;
                    var geometry = {coordinates: coordinates};
                    var features = [];
                    features[0] = {geometry: geometry};
                    var successResponse = {features: features};
                    var failResponse = {features: []};
                    switch (record.contact_address_complete) {
                        case 'Cfezfezfefes':
                            return Promise.resolve(failResponse);
                        case '':
                            return Promise.resolve(failResponse);
                    }
                    return Promise.resolve(successResponse);
                },

                _fetchCoordinatesFromAddressOSM: function (record) {
                    var coordinates = [];
                    coordinates[0] = {lat: 10.0, lon: 10.5};
                    switch (record.contact_address_complete) {
                        case 'Cfezfezfefes':
                            return Promise.resolve([]);
                        case '':
                            return Promise.resolve([]);
                    }
                    return Promise.resolve(coordinates);
                },

                _fetchRoute: function () {
                    if (this.data.mapBoxToken !== 'token') {
                        return Promise.reject({status: 401});
                    }
                    var legs = [];
                    for (var i = 1; i < this.data.records.length; i++) {
                        var coordinates = [];
                        coordinates[0] = [10, 10.5];
                        coordinates[1] = [10, 10.6];
                        var geometry = {coordinates: coordinates};
                        var steps = [];
                        steps[0] = {geometry: geometry};
                        legs.push({steps: steps});
                    }
                    var routes = [];
                    routes[0] = {legs: legs};
                    return Promise.resolve({routes: routes});
                }
            });

        },
        afterEach: function () {
            testUtils.mock.unpatch(MapModel);
        }
    }, function () {

        //---------------------------------------------------------------
        //testing data fetching
        //--------------------------------------------------------------

        /**
         * data: no record
         * should display a map with the minimum level of zoom
         * Should have no record
         * Should have no marker
         * Should have no route
         */

        QUnit.test('Create a view with no record', async function (assert) {
            assert.expect(8);
            var map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map res_partner="partner_id"  routing="true">' +
                    '<marker-popup>' +
                    '<field name="name" string="Project: "/>' +
                    '</marker-popup>' +
                    '</map>',
                mockRPC: function (route, args) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            assert.strictEqual(args.model, 'project.task', 'The model should be project.task');
                            assert.strictEqual(args.fields[0], 'partner_id');
                            assert.strictEqual(args.fields[1], 'display_name');
                            return Promise.resolve(this.data['project.task'].noRecord);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            assert.ok(false, 'should not search_read the partners if there are no partner')
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: 'token'
                },
            });
            assert.strictEqual(map.model.resPartnerField, 'partner_id', 'the resPartnerField should be set');

            assert.strictEqual(map.renderer.state.records.length, 0, 'There should be no records');
            assert.notOk(map.$('img.leaflet-marker-icon').length, 'No marker should be on a the map.');
            assert.notOk(map.$('.leaflet-overlay-pane').find('path').length, 'No route should be shown');
            assert.strictEqual(map.renderer.leafletMap.getZoom(), 2, 'The map should at its minimum zoom level(2)');
            map.destroy();
        });
        /**
         * data: one record that has no partner linked to it
         * The record should be kept and displayed in the list of records in gray (no clickable)
         * should have no marker
         * Should have no route
         * Map should be at his minimum zoom level
         */
        QUnit.test('Create a view with one record that has no partner', async function (assert) {
            assert.expect(6);
            var map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map res_partner="partner_id"  routing="true">' +
                    '</map>',
                mockRPC: function (route) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            return Promise.resolve(this.data['project.task'].recordWithouthPartner);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            return Promise.resolve(this.data['res.partner'].emptyRecords);
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: 'token'
                },
            });
            assert.strictEqual(map.renderer.state.records.length, 1, 'There should be no records');
            assert.notOk(map.$('img.leaflet-marker-icon').length, 'No marker should be on a the map.');
            assert.notOk(map.$('.leaflet-overlay-pane').find('path').length, 'No route should be shown');
            assert.strictEqual(map.renderer.leafletMap.getZoom(), 2, 'The map should at its minimum level of zoom(2)');
            assert.containsOnce(map,'.o_pin_list_container .o_pin_list_details li');
            assert.containsOnce(map,'.o_pin_list_container .o_pin_list_details li span');
            map.destroy();
        });

        /**
         * data: one record that has a partner which has coordinates but no address
         * One record
         * One marker
         * no route
         * Map should not be at his minimum zoom level
         *
         */

        QUnit.test('Create a view with one record and a partner located by coordinates', async function (assert) {
            assert.expect(3);
            var map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map res_partner="partner_id"  routing="true">' +
                    '</map>',
                mockRPC: function (route) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            return Promise.resolve(this.data['project.task'].oneRecord);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            return Promise.resolve(this.data['res.partner'].coordinatesNoAddress);
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: 'token'
                },
            });
            assert.strictEqual(map.renderer.state.records.length, 1, 'There should be one records');
            assert.strictEqual(map.$('div.leaflet-marker-icon').length, 1, 'There should be one marker on the map');
            assert.strictEqual(map.$('.leaflet-overlay-pane').find('path').length, 0, 'There should be no route on the map');
            map.destroy();
        });

        /**
         * data: one record linked to one partner with no address and wrong coordinates
         * api: MapBox
         * record should be kept and displayed in the list
         * no route
         * no marker
         * map should be at its minimum zoom level
         */
        QUnit.test('Create view with one record linked to a partner with wrong coordinates with MB', async function (assert) {
            assert.expect(5);
            var map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map res_partner="partner_id"  routing="true">' +
                    '</map>',
                mockRPC: function (route) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            return Promise.resolve(this.data['project.task'].oneRecord);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            return Promise.resolve(this.data['res.partner'].wrongCoordinatesNoAddress);
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: 'token'
                },
            });
            assert.strictEqual(map.renderer.state.records.length, 1, 'There should be one records');
            assert.strictEqual(map.$('img.leaflet-marker-icon').length, 0, 'There should be np marker on the map');
            assert.strictEqual(map.$('.leaflet-overlay-pane').find('path').length, 0, 'There should be no route on the map');
            assert.containsOnce(map,'.o_pin_list_container .o_pin_list_details li');
            assert.containsOnce(map,'.o_pin_list_container .o_pin_list_details li span');
            map.destroy();
        });

        /**
         * data: one record linked to one partner with no address and wrong coordinates
         * api: OpenStreet Map
         * record should be kept
         * no route
         * no marker
         * map should be at its minimum zoom level
         */
        QUnit.test('Create view with one record linked to a partner with wrong coordinates with OSM', async function (assert) {
            assert.expect(3);
            var map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map res_partner="partner_id"  routing="true">' +
                    '</map>',
                mockRPC: function (route) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            return Promise.resolve(this.data['project.task'].oneRecord);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            return Promise.resolve(this.data['res.partner'].wrongCoordinatesNoAddress);
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: ''
                },
            });
            assert.strictEqual(map.renderer.state.records.length, 1, 'There should be one records');
            assert.strictEqual(map.$('div.leaflet-marker-icon').length, 0, 'There should be no marker on the map');
            assert.strictEqual(map.$('.leaflet-overlay-pane').find('path').length, 0, 'There should be no route on the map');
            map.destroy();
        });
        /**
         * data: one record linked to one partner with no coordinates and good address
         * api: OpenStreet Map
         * caching RPC called, assert good args
         * one record
         * no route
         */

        QUnit.test('Create View with one record linked to a partner with no coordinates and right address OSM', async function (assert) {
            assert.expect(7);
            var map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map res_partner="partner_id"  routing="true">' +
                    '</map>',
                mockRPC: function (route, args) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            return Promise.resolve(this.data['project.task'].oneRecord);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            return Promise.resolve(this.data['res.partner'].noCoordinatesGoodAddress);
                        case '/web/dataset/call_kw/res.partner/update_latitude_longitude':
                            assert.strictEqual(args.model, "res.partner", 'The model should be "res.partner"');
                            assert.strictEqual(args.method, "update_latitude_longitude");
                            assert.strictEqual(args.args[0].length, 1, 'There should be one record needing caching');
                            assert.strictEqual(args.args[0][0].id, 1, 'The records\'s id should be 1');
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: ''
                },
            });
            assert.strictEqual(map.renderer.state.records.length, 1, 'There should be one records');
            assert.strictEqual(map.$('div.leaflet-marker-icon').length, 1, 'There should be one marker on the map');
            assert.strictEqual(map.$('.leaflet-overlay-pane').find('path').length, 0, 'There should be no route on the map');
            map.destroy();
        });

        /**
         * data: one record linked to one partner with no coordinates and good address
         * api: MapBox
         * caching RPC called, assert good args
         * one record
         * no route
         */

        QUnit.test('Create View with one record linked to a partner with no coordinates and right address MB', async function (assert) {
            assert.expect(7);
            var map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map res_partner="partner_id" routing="true">' +
                    '</map>',
                mockRPC: function (route, args) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            return Promise.resolve(this.data['project.task'].oneRecord);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            return Promise.resolve(this.data['res.partner'].noCoordinatesGoodAddress);
                        case '/web/dataset/call_kw/res.partner/update_latitude_longitude':
                            assert.strictEqual(args.model, "res.partner", 'The model should be "res.partner"');
                            assert.strictEqual(args.method, "update_latitude_longitude");
                            assert.strictEqual(args.args[0].length, 1, 'There should be one record needing caching');
                            assert.strictEqual(args.args[0][0].id, 1, 'The records\'s id should be 1');
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: 'token'
                },
            });
            assert.strictEqual(map.renderer.state.records.length, 1, 'There should be one records');
            assert.strictEqual(map.$('div.leaflet-marker-icon').length, 1, 'There should be one marker on the map');
            assert.strictEqual(map.$('.leaflet-overlay-pane').find('path').length, 0, 'There should be no route on the map');
            map.destroy();
        });

        /**
         * data: one record linked to a partner with no coordinates and no address
         * api: MapBox
         * 1 record
         * no route
         * no marker
         * min level of zoom
         */

        QUnit.test('Create view with no located record', async function (assert) {
            assert.expect(4);
            var map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map res_partner="partner_id"  routing="true">' +
                    '</map>',
                mockRPC: function (route) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            return Promise.resolve(this.data['project.task'].oneRecord);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            return Promise.resolve(this.data['res.partner'].unlocatedRecords);
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: 'token'
                }
            });
            assert.strictEqual(map.renderer.state.records.length, 1, 'There should be one records');
            assert.notOk(map.$('img.leaflet-marker-icon').length, 'No marker should be on a the map.');
            assert.notOk(map.$('.leaflet-overlay-pane').find('path').length, 'No route should be shown');
            assert.strictEqual(map.renderer.leafletMap.getZoom(), 2, 'The map should at its minimum zoom level(2)');
            map.destroy();
        });

        /**
         * data: one record linked to a partner with no coordinates and no address
         * api: OSM
         * one record
         * no route
         * no marker
         * min level of zoom
         */

        QUnit.test('Create view with no located record OSM', async function (assert) {
            assert.expect(4);
            var map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map res_partner="partner_id"  routing="true">' +
                    '</map>',
                mockRPC: function (route) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            return Promise.resolve(this.data['project.task'].oneRecord);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            return Promise.resolve(this.data['res.partner'].unlocatedRecords);
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: ''
                }
            });
            assert.strictEqual(map.renderer.state.records.length, 1, 'There should be one records');
            assert.notOk(map.$('img.leaflet-marker-icon').length, 'No marker should be on a the map.');
            assert.notOk(map.$('.leaflet-overlay-pane').find('path').length, 'No route should be shown');
            assert.strictEqual(map.renderer.leafletMap.getZoom(), 2, 'The map should at its minimum zoom level(2)');
            map.destroy();
        });

        /**
         * data: one record linked to a partner with no coordinates and wrong address
         * api: OSM
         * one record
         * no route
         * no marker
         * min level zoom
         */

        QUnit.test('Create view with no badly located record OSM', async function (assert) {
            assert.expect(4);
            var map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map res_partner="partner_id"  routing="true">' +
                    '</map>',
                mockRPC: function (route) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            return Promise.resolve(this.data['project.task'].oneRecord);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            return Promise.resolve(this.data['res.partner'].noCoordinatesWrongAddress);
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: ''
                }
            });
            assert.strictEqual(map.renderer.state.records.length, 1, 'There should be one records');
            assert.notOk(map.$('img.leaflet-marker-icon').length, 'No marker should be on a the map.');
            assert.notOk(map.$('.leaflet-overlay-pane').find('path').length, 'No route should be shown');
            assert.strictEqual(map.renderer.leafletMap.getZoom(), 2, 'The map should at its minimum zoom level(2)');
            map.destroy();
        });

        /**
         * data: one record linked to a partner with no coordinates and wrong address
         * api: mapbox
         * one record
         * no route
         * no marker
         * min level zoom
         */

        QUnit.test('Create view with no badly located record MB', async function (assert) {
            assert.expect(4);
            var map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map res_partner="partner_id"  routing="true">' +
                    '</map>',
                mockRPC: function (route) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            return Promise.resolve(this.data['project.task'].oneRecord);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            return Promise.resolve(this.data['res.partner'].noCoordinatesWrongAddress);
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: 'token'
                }
            });
            assert.strictEqual(map.renderer.state.records.length, 1, 'There should be one records');
            assert.notOk(map.$('img.leaflet-marker-icon').length, 'No marker should be on a the map.');
            assert.notOk(map.$('.leaflet-overlay-pane').find('path').length, 'No route should be shown');
            assert.strictEqual(map.renderer.leafletMap.getZoom(), 2, 'The map should at its minimum zoom level(2)');
            map.destroy();
        });

        /**
         * data: 2 records linked to the same partner
         * 2 records
         * 2 markers
         * no route
         * same partner object
         * 1 caching request
         */
        QUnit.test('Create a view with two located records same partner', async function (assert) {
            assert.expect(4);
            var map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map res_partner="partner_id"  routing="true">' +
                    '</map>',
                mockRPC: function (route) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            return Promise.resolve(this.data['project.task'].twoRecordOnePartner);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            return Promise.resolve(this.data['res.partner'].oneLocatedRecord);
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: 'token'
                },
            });
            assert.strictEqual(map.renderer.state.records.length, 2, 'There should be no records');
            assert.strictEqual(map.$('div.leaflet-marker-icon').length, 2, 'There should be 2 markers');
            assert.strictEqual(map.$('.leaflet-overlay-pane').find('path').length, 1, 'There should be one route showing');
            assert.equal(map.renderer.state.records[0].partner, map.renderer.state.records[1].partner, 'The records should have the same partner object as a property');
            map.destroy();
        });
        /**
         * data: 2 records linked to differnet partners
         * 2 records
         * 1 route
         * different partner object.
         * 2 caching
         */

        QUnit.test('Create a a view with two located records different partner', async function (assert) {
            assert.expect(5);
            var map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map res_partner="partner_id"  routing="true">' +
                    '</map>',
                mockRPC: function (route, args) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            return Promise.resolve(this.data['project.task'].twoRecords);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            return Promise.resolve(this.data['res.partner'].twoRecordsAddressNoCoordinates);
                        case '/web/dataset/call_kw/res.partner/update_latitude_longitude':
                            assert.strictEqual(args.args[0].length, 2, 'Should have 2 record needing caching');
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: 'token'
                },
            });
            assert.strictEqual(map.renderer.state.records.length, 2, 'There should be no records');
            assert.strictEqual(map.$('div.leaflet-marker-icon').length, 2, 'There should be 2 markers');
            assert.strictEqual(map.$('.leaflet-overlay-pane').find('path').length, 1, 'There should be one route showing');
            assert.notEqual(map.renderer.state.records[0].partner, map.renderer.state.records[1].partner, 'The records should have the same partner object as a property');
            map.destroy();
        });
        /**
         * data: 2 valid res.partner records
         * test the case where the model is res.partner and the "res.partner" field is the id
         * should have 2 records,
         * 2 markers
         * no route
         */
        QUnit.test('Create a view with res.partner', async function (assert) {
            assert.expect(8);
            this.data['res.partner'].recordsPrimary = {
                records: [
                    {
                        id: 2, name: 'Foo',
                        'contact_address_complete': 'Chaussée de Namur 40, 1367, Ramillies', sequence: 3
                    },
                    {
                        id: 1, name: 'FooBar',
                        'contact_address_complete': 'Chaussée de Louvain 94, 5310 Éghezée', sequence: 1
                    }
                ], length: 2
            };
            var map = await createView({
                View: MapView,
                model: 'res.partner',
                data: this.data,
                arch: '<map res_partner="id">' +
                    '</map>',
                mockRPC: function (route, args) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            assert.strictEqual(args.model, 'res.partner', 'The model should be res.partner');
                            assert.strictEqual(args.fields[0], 'id');
                            return Promise.resolve(this.data['res.partner'].recordsPrimary);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            assert.strictEqual(args.model, 'res.partner', 'The model should be res.partner as well');
                            assert.strictEqual(args.kwargs.domain[1][2][0], 2);
                            assert.strictEqual(args.kwargs.domain[1][2][1], 1);
                            return Promise.resolve(this.data['res.partner'].twoRecordsAddressNoCoordinates);
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: 'token'
                },
            });
            assert.strictEqual(map.renderer.state.records.length, 2, 'There should be two records');
            assert.strictEqual(map.$('img.leaflet-marker-icon').length, 2, 'There should be 2 markers');
            assert.strictEqual(map.$('.leaflet-overlay-pane').find('path').length, 0, 'There should be no route showing');
            map.destroy();
        });

        /**
         * data: 3 records linked to one located partner and one unlocated
         * test if only the 2 located records are displayed
         */

        QUnit.test('Create a view with 2 located records and 1 unlocated', async function (assert) {
            assert.expect(4);
            var map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map res_partner="partner_id" routing="true">' +
                    '</map>',
                mockRPC: function (route) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            return Promise.resolve(this.data['project.task'].threeRecords);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            return Promise.resolve(this.data['res.partner'].twoRecordsOneUnlocated);
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: 'token'
                },
            });
            assert.strictEqual(map.renderer.state.records.length, 3);
            assert.strictEqual(map.renderer.state.records[0].partner.id, 1, 'The partner\'s id should be 1');
            assert.strictEqual(map.renderer.state.records[1].partner.id, 2, 'The partner\'s id should be 2');
            assert.strictEqual(map.renderer.state.records[2].partner.id, 1, 'The partner\'s id should be 1');
            map.destroy();
        });


        //-----------------------------------------
        //renderer testing
        //------------------------------------------

        QUnit.test('Google Maps redirection', async function (assert) {
            assert.expect(2);
            var map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map res_partner="partner_id" >' +
                    '</map>',
                mockRPC: function (route) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            return Promise.resolve(this.data['project.task'].twoRecords);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            return Promise.resolve(this.data['res.partner'].twoRecordsAddressNoCoordinates);
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: 'token'
                },
            });
            assert.strictEqual(map.$('a.btn.btn-primary').attr('href'), 'https://www.google.com/maps/dir/?api=1&waypoints=10.5,10', 'The link\'s URL should contain the right sets of coordinates');
            await testUtils.dom.click(map.$('img.leaflet-marker-icon').eq(1));
            assert.strictEqual(map.$('div.leaflet-popup').find('a.btn.btn-primary').attr('href'), 'https://www.google.com/maps/dir/?api=1&destination=10.5,10', 'The link\'s URL should the right set of coordinates');
            map.destroy();
        });

        QUnit.test('Unicity of coordinates in Google Maps url', async function(assert){
            assert.expect(2);
            var map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map res_partner="partner_id" >' +
                    '</map>',
                mockRPC: function (route) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            return Promise.resolve(this.data['project.task'].twoRecordOnePartner);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            return Promise.resolve(this.data['res.partner'].twoRecordsAddressNoCoordinates);
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: 'token'
                },
            });

            assert.strictEqual(map.$('a.btn.btn-primary').attr('href'), 'https://www.google.com/maps/dir/?api=1&waypoints=10.5,10', 'The link\'s URL should contain unqiue sets of coordinates');
            await testUtils.dom.click(map.$('img.leaflet-marker-icon').eq(1));
            assert.strictEqual(map.$('div.leaflet-popup').find('a.btn.btn-primary').attr('href'), 'https://www.google.com/maps/dir/?api=1&destination=10.5,10', 'The link\'s URL should only contain unqiue sets of coordinates');
            map.destroy();
        });

        QUnit.test('testing the size of the map', async function (assert) {
            assert.expect(1);
            var map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map>' +
                    '</map>',
                mockRPC: function () {
                    return Promise.resolve();
                },
                session: {
                    map_box_token: ''
                },
            });

            assert.strictEqual($('.o_map_container').height(), $('.o_content').height(), 'The map should be the same height as the content div');

            map.destroy();
        });

        QUnit.test('test the position of pin', async function (assert) {
            assert.expect(5);
            var map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map res_partner="partner_id" >' +
                    '</map>',
                mockRPC: function (route) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            return Promise.resolve(this.data['project.task'].twoRecords);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            return Promise.resolve(this.data['res.partner'].twoRecordsAddressNoCoordinates);
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: ''
                },
            });
            assert.strictEqual(map.renderer.markers.length, 2, 'Should have two markers created');
            assert.strictEqual(map.renderer.markers[0].getLatLng().lat, 10, 'The latitude should be the same as the record');
            assert.strictEqual(map.renderer.markers[0].getLatLng().lng, 10.5, 'The longitude should be the same as the record');
            assert.strictEqual(map.renderer.markers[1].getLatLng().lat, 10, 'The latitude should be the same as the record');
            assert.strictEqual(map.renderer.markers[1].getLatLng().lng, 10.5, 'The longitude should be the same as the record');
            map.destroy();
        });

        /**
         * data: two located records
         * Create an empty map
         */
        QUnit.test('Create of a empty map', async function (assert) {
            assert.expect(10);
            var map = await createView({
                View: MapView,
                model: 'res.partner',
                data: this.data,
                arch: '<map>' + '</map>',
                mockRPC: function (route) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            return Promise.resolve(this.data['project.task'].twoRecords);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            return Promise.resolve(this.data['res.partner'].twoRecordsAddressNoCoordinates);
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: ''
                }
            });
            assert.notOk(map.model.resPartnerField, 'the resPartnerField should not be set');

            assert.strictEqual(map.$('.o_map_view').length, 1, '1 div should have the class "o_map_view"');
            assert.ok(map.$('.leaflet-map-pane').length, "If the map exists this div should exist");
            assert.ok(map.renderer.leafletMap, 'If the map exists this property should be initialized');
            assert.ok(map.$('.leaflet-pane .leaflet-tile-pane').children().length, 'The map tiles should have been happened to the DOM');
            assert.ok(map.renderer.isInDom, 'the map should be in the DOM');
            assert.ok(map.renderer.mapIsInit, 'the map should be initialized');

            assert.strictEqual(map.renderer.polylines.length, 0, 'Should have no polylines');
            assert.strictEqual(map.$('.leaflet-overlay-pane').children().length, 0, 'Should have no showing route');
            assert.strictEqual(map.renderer.leafletMap.getZoom(), 2, 'The level of zoom should should be at it\'s minimum');
            map.destroy();
        });

        /**
         * two located records
         * without routing or default_order
         * normal marker icon
         * test the click on them
         */

        QUnit.test('Create view with normal marker icons', async function (assert) {
            assert.expect(6);
            var map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map res_partner="partner_id">' +
                    '</map>',
                mockRPC: function (route) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            return Promise.resolve(this.data['project.task'].twoRecords);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            return Promise.resolve(this.data['res.partner'].twoRecordsAddressNoCoordinates);
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: 'token'
                },
            });
            assert.notOk(map.renderer.numbering, 'the numbering option should not be enabled');
            assert.notOk(map.model.routing, 'The routing option should not be enabled');

            assert.strictEqual(map.$('img.leaflet-marker-icon').length, 2, 'There should be 2 markers');
            assert.strictEqual(map.$('.leaflet-overlay-pane').find('path').length, 0, 'There should be no route showing');

            await testUtils.dom.click(map.$('img.leaflet-marker-icon').eq(0)[0]);
            assert.strictEqual(map.$('.leaflet-popup-pane').children().length, 1, 'Should have one showing popup');

            await testUtils.dom.click(map.$('div.leaflet-container'));
            assert.notOk(map.renderer.markers[0].isPopupOpen(), 'The marker\'s popup should be close');
            map.destroy();
        });

        /**
         * two located records
         * with default_order
         * no numbered icon
         * test click on them
         * asserts that the rpc receive the right parameters
         */

        QUnit.test('Create a view with default_order', async function (assert) {
            assert.expect(6);
            var map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map res_partner="partner_id" default_order="name">' +
                    '</map>',
                mockRPC: function (route, args) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            assert.strictEqual(args.sort, 'name ASC', 'The sorting order should be on the field name in a ascendant way');
                            return Promise.resolve(this.data['project.task'].twoRecords);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            return Promise.resolve(this.data['res.partner'].twoRecordsAddressNoCoordinates);
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: ''
                },
            });
            assert.ok(map.renderer.numbering === false, 'the numbering option should not be enabled');
            assert.notOk(map.model.routing, 'The routing option should not be enabled');
            assert.strictEqual(map.$('img.leaflet-marker-icon').length, 2, 'There should be 2 markers');
            assert.strictEqual(map.$('.leaflet-popup-pane').children().length, 0, 'Should have no showing popup');
            await testUtils.dom.click(map.$('img.leaflet-marker-icon').eq(1));
            assert.strictEqual(map.$('.leaflet-popup-pane').children().length, 1, 'Should have one showing popup');
            map.destroy();
        });

        /**
         * two locted records
         * with routing enabled
         * numbered icon
         * test click on route
         */

        QUnit.test('Create a view with routing', async function (assert) {
            assert.expect(10);
            var map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map res_partner="partner_id" routing="true">' +
                    '</map>',
                mockRPC: function (route) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            return Promise.resolve(this.data['project.task'].twoRecords);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            return Promise.resolve(this.data['res.partner'].twoRecordsAddressNoCoordinates);
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: 'token'
                },
            });
            assert.ok(map.renderer.numbering, 'the numbering option should be enabled');
            assert.ok(map.model.routing, 'The routing option should be enabled');

            assert.strictEqual(map.model.numberOfLocatedRecords, 2, 'Should have 2 located Records');
            assert.strictEqual(map.renderer.state.route.routes.length, 1, 'Should have 1 computed route');
            assert.strictEqual(map.$('div.leaflet-marker-icon').eq(0).children().text(), "1", 'The first marker should display 1');
            assert.strictEqual(map.$('div.leaflet-marker-icon').eq(1).children().text(), "2", 'The second marker should display 2');
            assert.strictEqual(map.$('path.leaflet-interactive').attr('stroke'), 'blue', 'The route should be blue if it has not been clicked');
            assert.strictEqual(map.$('path.leaflet-interactive').attr('stroke-opacity'), '0.3', 'The opacity of the polyline should be 0.3');
            map.renderer.polylines[0].fire('click');
            assert.strictEqual(map.$('path.leaflet-interactive').attr('stroke'), 'darkblue', 'The route should be darkblue after being clicked');
            assert.strictEqual(map.$('path.leaflet-interactive').attr('stroke-opacity'), '1', 'The opacity of the polyline should be 1');
            map.destroy();
        });

        /**
         * routing with token and one located record
         * No route
         */

        QUnit.test('create a view with routing and one located record', async function (assert) {
            assert.expect(2);
            var map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map res_partner="partner_id"  routing="true">' +
                    '</map>',
                mockRPC: function (route) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            return Promise.resolve(this.data['project.task'].oneRecord);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            return Promise.resolve(this.data['res.partner'].oneLocatedRecord);
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: 'token'
                },
            });
            assert.ok(map.model.routing, 'The routing option should be enabled');
            assert.strictEqual(map.renderer.state.route.routes.length, 0, 'Should have no computed route');
            map.destroy();
        });

        /**
         * no mapbox token
         * assert that the view uses the right api and routes
         */

        QUnit.test('CreateView with empty mapbox token setting', async function (assert) {
            assert.expect(3);
            var map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map res_partner="partner_id">' +
                    '</map>',
                mockRPC: function (route) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            return Promise.resolve(this.data['project.task'].recordWithouthPartner);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            return Promise.resolve(this.data['res.partner'].emptyRecords);
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: ''
                },
            });
            assert.strictEqual(map.model.data.mapBoxToken, '', 'The token should be an empty string');
            assert.strictEqual(map.renderer.apiTilesRoute, 'https://a.tile.openstreetmap.org/{z}/{x}/{y}.png',
                'With no token the route for fetching tiles should be "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png"');
            assert.strictEqual(map.renderer.mapBoxToken, '', 'The token should be an empty string');
            map.destroy();
        });

        /**
         * wrong mapbox token
         * assert that the view uses the openstreetmap api
         */

        QUnit.test('Create a view with wrong map box setting', async function (assert) {
            assert.expect(3);
            var map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map res_partner="partner_id"  routing="true">' +
                    '</map>',
                mockRPC: function (route) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            return Promise.resolve(this.data['project.task'].twoRecords);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            return Promise.resolve(this.data['res.partner'].twoRecordsAddressNoCoordinates);
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: 'vrve'
                },
            });
            assert.strictEqual(map.model.data.mapBoxToken, '', 'The token should be an empty string');
            assert.strictEqual(map.renderer.apiTilesRoute, 'https://a.tile.openstreetmap.org/{z}/{x}/{y}.png',
                'With no token the route for fetching tiles should be "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png"');
            assert.strictEqual(map.renderer.mapBoxToken, '', 'The token should be an empty string');
            map.destroy();
        });

        /**
         * wrong mapbox token fails at catch at route computing
         *
         */

        QUnit.test('create a view with wrong map box setting and located records', async function (assert) {
            assert.expect(3);
            var map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map res_partner="partner_id"  routing="true">' +
                    '</map>',
                mockRPC: function (route) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            return Promise.resolve(this.data['project.task'].twoRecords);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            return Promise.resolve(this.data['res.partner'].twoRecordsAddressCoordinates);
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: 'frezfre'
                },
            });
            assert.strictEqual(map.model.data.mapBoxToken, '', 'The token should be an empty string');
            assert.strictEqual(map.renderer.apiTilesRoute, 'https://a.tile.openstreetmap.org/{z}/{x}/{y}.png',
                'With no token the route for fetching tiles should be "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png"');
            assert.strictEqual(map.renderer.mapBoxToken, '', 'The token should be an empty string');
            map.destroy();
        });

        /**
         * create view with right map box token
         * assert that the view uses the map box api
         */

        QUnit.test('Create a view with the right map box token', async function (assert) {
            assert.expect(3);
            var map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map res_partner="partner_id"  routing="true">' +
                    '</map>',
                mockRPC: function (route) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            return Promise.resolve(this.data['project.task'].recordWithouthPartner);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            return Promise.resolve(this.data['res.partner'].emptyRecords);
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: 'token'
                },
            });
            assert.strictEqual(map.model.data.mapBoxToken, 'token',
                'The token should be the right token');
            assert.strictEqual(map.renderer.apiTilesRoute, 'https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token={accessToken}',
                'With no token the route for fetching tiles should be "https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token={accessToken}"');
            assert.strictEqual(map.renderer.mapBoxToken, 'token'
                , 'The token should be the right token');
            map.destroy();
        });

        /**
         * data: two located records
         */

        QUnit.test('Click on pin shows popup, click on another shuts the first and open the other', async function (assert) {
            assert.expect(5);
            var map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map res_partner="partner_id"  routing="true">' +
                    '</map>',
                mockRPC: function (route) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            return Promise.resolve(this.data['project.task'].twoRecords);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            return Promise.resolve(this.data['res.partner'].twoRecordsAddressNoCoordinates);
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: 'token'
                },
            });
            assert.notOk(map.$('.leaflet-pane .leaflet-popup-pane').children().length, 'The popup div should be empty');
            await testUtils.dom.click(map.$('div.leaflet-marker-icon').eq(0));
            assert.ok(map.renderer.markers[0].isPopupOpen(), 'The marker\'s popup should be open');
            assert.strictEqual(map.$('.leaflet-popup-pane').children().length, 1, 'The popup div should contain one element');

            await testUtils.dom.click(map.$el.find('.leaflet-map-pane'));

            assert.notOk(map.renderer.markers[0].isPopupOpen(), 'The marker\'s popup should be close');

            await testUtils.dom.click(map.$('div.leaflet-marker-icon').eq(1));

            assert.ok(map.renderer.markers[1].isPopupOpen());


            map.destroy();
        });

        /**
         * data: two located records
         * asserts that all the records are shown on the map
         */

        QUnit.test('assert that all the records are shown on the map', async function (assert) {
            assert.expect(4);
            var map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map res_partner="partner_id"  routing="true">' +
                    '</map>',
                mockRPC: function (route) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            return Promise.resolve(this.data['project.task'].twoRecords);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            return Promise.resolve(this.data['res.partner'].twoRecordsAddressNoCoordinates);
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: 'token'
                },
            });
            var mapX = map.$('.leaflet-map-pane')[0]._leaflet_pos.x;
            var mapY = map.$('.leaflet-map-pane')[0]._leaflet_pos.y;
            assert.ok(mapX - map.$('div.leaflet-marker-icon').eq(0)[0]._leaflet_pos.x < 0, 'If the marker is currently shown on the map, the subtraction of latitude should be under 0');
            assert.ok(mapY - map.$('div.leaflet-marker-icon').eq(0)[0]._leaflet_pos.y < 0);
            assert.ok(mapX - map.$('div.leaflet-marker-icon').eq(1)[0]._leaflet_pos.x < 0);
            assert.ok(mapY - map.$('div.leaflet-marker-icon').eq(1)[0]._leaflet_pos.y < 0);
            map.destroy();
        });

        /**
         * data: two located records
         * asserts that the right fields are shown in the popup
         */

        QUnit.test('Content of the marker popup with one field', async function (assert) {
            assert.expect(7);
            var map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map res_partner="partner_id"  routing="true">' +
                    '<marker-popup>' +
                    '<field name="display_name" string="Name: "/>' +
                    '</marker-popup>' +
                    '</map>',
                viewOptions: {
                    actionViews: [{type: 'form'}]
                },
                mockRPC: function (route, args) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            assert.ok(args.fields.includes('display_name'));
                            return Promise.resolve(this.data['project.task'].twoRecords);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            return Promise.resolve(this.data['res.partner'].twoRecordsAddressNoCoordinates);
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: 'token'
                },
            });
            assert.strictEqual(map.renderer.fieldsMarkerPopup[0].fieldName, "display_name");
            await testUtils.dom.click(map.$('div.leaflet-marker-icon').eq(0)[0]);
            assert.strictEqual(map.renderer.fieldsMarkerPopup.length, 1, 'fieldsMarkerPopup should contain one field');
            assert.strictEqual(map.$('tbody').children().children().length, 3, 'The popup should have one field');
            assert.strictEqual(map.$('tbody').children().children().eq(0).prop("innerText"), 'Name:',
                'The first element of the table should \'Name: \'');
            assert.strictEqual(map.$('tbody').children().children().eq(2).prop("innerText"), 'FooProject',
                'The second element of the table should \'Foo\'');
            assert.strictEqual(map.$('div.center').children().length, 3, 'The popup should contain 2 buttons and one divider');
            map.destroy();
        });

        /**
         * data: two located records
         * asserts that no field is shown in popup
         */

        QUnit.test('Content of the marker with no field', async function (assert) {
            assert.expect(2);
            var map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map res_partner="partner_id"  routing="true">' +
                    '</map>',
                viewOptions: {
                    actionViews: [{type: 'form'}]
                },
                mockRPC: function (route) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            return Promise.resolve(this.data['project.task'].twoRecords);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            return Promise.resolve(this.data['res.partner'].twoRecordsAddressNoCoordinates);
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: 'token'
                },
            });
            await testUtils.dom.click(map.$('div.leaflet-marker-icon').eq(0)[0]);
            assert.strictEqual(map.$('tbody').children().length, 0, 'The popup should have only the button');
            assert.strictEqual(map.$('div.center').children().length, 3, 'The popup should contain 2 buttons and one divider');
            map.destroy();
        });

        QUnit.test('Pager', async function (assert) {
            assert.expect(4);

            const map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map res_partner="partner_id"/>',
                mockRPC: route => {
                    switch (route) {
                        case '/web/dataset/search_read':
                            return Promise.resolve({
                                length: 101,
                                records: _.range(1, 101).map(i => {return {id: i, name: 'project', partner_id: [i]}})
                            });
                        case '/web/dataset/call_kw/res.partner/search_read':
                            return Promise.resolve(_.range(1, 101).map(i => {
                                return {id: i, name: 'Foo', 'partner_latitude': 10.0, 'partner_longitude': 10.5};
                            }));
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: 'token'
                },
            });

            assert.isVisible(map.pager);
            assert.strictEqual(map.pager.$('.o_pager_value').text(), "1-80",
                "current pager value should be 1-20");
            assert.strictEqual(map.pager.$('.o_pager_limit').text(), "101",
                "current pager limit should be 21");

            await testUtils.dom.click(map.pager.$('.o_pager_next'));

            assert.strictEqual(map.pager.$('.o_pager_value').text(), "81-101",
                "pager value should be 21-40");

            map.destroy();
        });

        QUnit.test('New domain', async function (assert) {
            this.data['project.task'].records = [
                {id: 1, name: "FooProject", sequence: 1, partner_id: 1},
                {id: 2, name: 'BarProject', sequence: 2, partner_id: 2},
            ];
            assert.expect(18);
            var map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map res_partner="partner_id" routing ="true">' +
                    '</map>',
                mockRPC: function (route) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            return this._super.apply(this, arguments);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            return Promise.resolve(this.data['res.partner'].twoRecordsAddressNoCoordinates);
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: 'token'
                },
            });
            assert.strictEqual(map.model.data.records.length, 2, 'There should be 2 records');
            assert.strictEqual(map.$('.leaflet-overlay-pane').find('path').length, 1, 'There should be one route displayed');
            assert.strictEqual(map.$('div.leaflet-marker-icon').length, 2, 'There should be 2 markers displayed'),

                await map.update({domain: [['name', '=', 'FooProject']]});

            assert.strictEqual(map.model.data.records.length, 1, 'There should be 1 record');
            assert.strictEqual(map.renderer.polylines.length, 0, 'There should be no road computed');
            assert.strictEqual(map.$('.leaflet-overlay-pane').find('path').length, 0, 'There should be no route on the map');
            assert.strictEqual(map.renderer.markers.length, 1, 'There should be 1 marker generated');
            assert.strictEqual(map.$('div.leaflet-marker-icon').length, 1, 'There should be 1 marker on the map');

            await map.update({domain: [['name', '=', 'Foofezfezf']]});

            assert.strictEqual(map.model.data.records.length, 0, 'There should be no record');
            assert.strictEqual(map.renderer.polylines.length, 0, 'There should be no road computed');
            assert.strictEqual(map.$('.leaflet-overlay-pane').find('path').length, 0, 'There should be no route on the map');
            assert.strictEqual(map.renderer.markers.length, 0, 'There should be no marker generated');
            assert.strictEqual(map.$('div.leaflet-marker-icon').length, 0, 'There should be 0 marker on the map');

            await map.update({domain: [['name', 'like', 'Project']]});

            assert.strictEqual(map.model.data.records.length, 2, 'There should be 2 record');
            assert.strictEqual(map.renderer.polylines.length, 1, 'There should be one road computed');
            assert.strictEqual(map.$('.leaflet-overlay-pane').find('path').length, 1, 'There should be 1 route on the map');
            assert.strictEqual(map.renderer.markers.length, 2, 'There should be 2 marker generated');
            assert.strictEqual(map.$('div.leaflet-marker-icon').length, 2, 'There should be 2 marker on the map');

            map.destroy();
        });

        //----------------------------------
        //controller testing
        //---------------------------------

        QUnit.test('Click on open button switches to form view', async function (assert) {
            assert.expect(7);
            var map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map res_partner="partner_id"  routing="true">' +
                    '</map>',
                viewOptions: {
                    actionViews: [{type: 'form'}]
                },
                mockRPC: function (route) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            return Promise.resolve(this.data['project.task'].oneRecord);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            return Promise.resolve(this.data['res.partner'].oneLocatedRecord);
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: 'token'
                },
            });
            testUtils.mock.intercept(map, 'switch_view', function (event) {
                assert.strictEqual(event.name, 'switch_view', 'The custom event should be \'switch_view\'');
                assert.strictEqual(event.data.view_type, 'form', 'The view switched to should be form');
                assert.strictEqual(event.data.res_id, 1, 'The record\'s id should be 1');
                assert.strictEqual(event.data.mode, 'readonly', 'The mode should be readonly');
                assert.strictEqual(event.data.model, 'project.task', 'The form view should be on the \'res.partner\' model');
            });
            testUtils.mock.intercept(map, 'open_clicked', function (event) {
                assert.strictEqual(event.data.id, 1, 'The record\'s id should be 1');

            }, true);
            await testUtils.dom.click(map.$('div.leaflet-marker-icon').eq(0));
            await testUtils.dom.click(map.$('div.center').children().eq(0));
            assert.ok(map.$('div.leaflet-popup-pane').find('button.btn.btn-primary.open'), 'the button should be present in the dom');

            map.destroy();
        });

        QUnit.test('Test the lack of open button', async function (assert) {
            assert.expect(1);
            var map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map res_partner="partner_id">' +
                    '</map>',
                mockRPC: function (route) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            return Promise.resolve(this.data['project.task'].oneRecord);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            return Promise.resolve(this.data['res.partner'].oneLocatedRecord);
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: 'token'
                },
            });
            await testUtils.dom.click(map.$('img.leaflet-marker-icon').eq(0));
            assert.notOk(map.$('div.leaflet-popup-pane').find('button.btn.btn-primary.open').length, 'The button should not be present in the dom');
            map.destroy();
        });

        QUnit.test('attribute panel_title on the arch should display in the pin list', async function (assert) {
            assert.expect(1);
            var map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map res_partner="partner_id" panel_title="AAAAAAAAAAAAAAAAA">' +
                    '</map>',
                mockRPC: function (route) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            return Promise.resolve(this.data['project.task'].oneRecord);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            return Promise.resolve(this.data['res.partner'].oneLocatedRecord);
                    }
                    return Promise.resolve();
                },
                session: {
                },
            });
            assert.strictEqual(map.$('.o_pin_list_container .o_pin_list_header span').text(), 'AAAAAAAAAAAAAAAAA');
            map.destroy();
        });

        QUnit.test('Test using a field other than partner_id for the map view', async function (assert) {
            assert.expect(1);
            var map = await createView({
                View: MapView,
                model: 'project.task',
                data: this.data,
                arch: '<map res_partner="another_partner_id">' +
                    '</map>',
                mockRPC: function (route) {
                    switch (route) {
                        case '/web/dataset/search_read':
                            return Promise.resolve(this.data['project.task'].anotherPartnerId);
                        case '/web/dataset/call_kw/res.partner/search_read':
                            return Promise.resolve(this.data['res.partner'].oneLocatedRecord);
                    }
                    return Promise.resolve();
                },
                session: {
                    map_box_token: 'token'
                },
            });
            await testUtils.dom.click(map.$('img.leaflet-marker-icon').eq(0));
            assert.notOk(map.$('div.leaflet-popup-pane').find('button.btn.btn-primary.open').length, 'The button should not be present in the dom');
            map.destroy();
        });
    });
});
