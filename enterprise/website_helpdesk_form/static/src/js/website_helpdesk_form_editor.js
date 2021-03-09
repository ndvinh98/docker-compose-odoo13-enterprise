odoo.define('website_helpdesk_form.form', function (require) {
'use strict';

var core = require('web.core');
var FormEditorRegistry = require('website_form.form_editor_registry');

var _t = core._t;

FormEditorRegistry.add('create_ticket', {
    defaultTemplateName: 'website_helpdesk_form.default_ticket_form',
    defaultTemplatePath: '/website_helpdesk_form/static/src/xml/website_helpdesk_form.xml',
    fields: [{
        name: 'team_id',
        type: 'many2one',
        relation: 'helpdesk.team',
        string: _t('Helpdesk Team'),
    }],
    successPage: '/your-ticket-has-been-submitted',
});

});
