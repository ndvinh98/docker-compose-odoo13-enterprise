odoo.define('documents.test_utils', function (require) {
"use strict";

const AbstractStorageService = require('web.AbstractStorageService');
const RamStorage = require('web.RamStorage');
const {createView} = require('web.test_utils');

async function createDocumentsKanbanView(params) {
    params.archs = params.archs || {};
    var searchArch = params.archs[`${params.model},false,search`] || '<search></search>';
    var searchPanelArch = `
        <searchpanel>
            <field name="folder_id" string="Workspace"/>
            <field name="tag_ids" select="multi" groupby="facet_id"/>
            <field name="res_model" select="multi" string="Attached To"/>
        </searchpanel>
    `;
    searchArch = searchArch.split('</search>')[0] + searchPanelArch + '</search>';
    params.archs[`${params.model},false,search`] = searchArch;
    if (!params.services || !params.services.local_storage) {
        // the searchPanel uses the localStorage to store/retrieve default
        // active category value
        params.services = params.services || {};
        const RamStorageService = AbstractStorageService.extend({
            storage: new RamStorage(),
        });
        params.services.local_storage = RamStorageService;
    }
    return createView(params);
}

return {
    createDocumentsKanbanView,
};

});
