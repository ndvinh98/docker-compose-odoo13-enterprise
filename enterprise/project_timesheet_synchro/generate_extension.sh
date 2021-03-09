#!/bin/bash

# Odoo extension creation tool, allow you to create an extension directory which can be imported directly in chrome

odoo_path=${1:-../../odoo}

[ -d extension/project_timesheet_synchro ] || mkdir -p extension/project_timesheet_synchro

lessc static/src/less/import.less > static/src/css/project_timesheet.css

cp -r static extension/project_timesheet_synchro
cp manifest.json extension
cp views/timesheet.html extension

[ -d extension/web/static/src/js ] || mkdir -p extension/web/static/src/js
cp $odoo_path/addons/web/static/src/js/boot.js extension/web/static/src/js

[ -d extension/web/static/src/js/core ] || mkdir extension/web/static/src/js/core
cp $odoo_path/addons/web/static/src/js/core/abstract_service.js extension/web/static/src/js/core
cp $odoo_path/addons/web/static/src/js/core/ajax.js extension/web/static/src/js/core
cp $odoo_path/addons/web/static/src/js/core/bus.js extension/web/static/src/js/core
cp $odoo_path/addons/web/static/src/js/core/class.js extension/web/static/src/js/core
cp $odoo_path/addons/web/static/src/js/core/concurrency.js extension/web/static/src/js/core
cp $odoo_path/addons/web/static/src/js/core/context.js extension/web/static/src/js/core
cp $odoo_path/addons/web/static/src/js/core/local_storage.js extension/web/static/src/js/core
cp $odoo_path/addons/web/static/src/js/core/mixins.js extension/web/static/src/js/core
cp $odoo_path/addons/web/static/src/js/core/py_utils.js extension/web/static/src/js/core
cp $odoo_path/addons/web/static/src/js/core/qweb.js extension/web/static/src/js/core
cp $odoo_path/addons/web/static/src/js/core/ram_storage.js extension/web/static/src/js/core
cp $odoo_path/addons/web/static/src/js/core/registry.js extension/web/static/src/js/core
cp $odoo_path/addons/web/static/src/js/core/rpc.js extension/web/static/src/js/core
cp $odoo_path/addons/web/static/src/js/core/service_mixins.js extension/web/static/src/js/core
cp $odoo_path/addons/web/static/src/js/core/session.js extension/web/static/src/js/core
cp $odoo_path/addons/web/static/src/js/core/time.js extension/web/static/src/js/core
cp $odoo_path/addons/web/static/src/js/core/translation.js extension/web/static/src/js/core
cp $odoo_path/addons/web/static/src/js/core/utils.js extension/web/static/src/js/core
cp $odoo_path/addons/web/static/src/js/core/widget.js extension/web/static/src/js/core
cp $odoo_path/addons/web/static/src/js/core/service_mixins.js extension/web/static/src/js/core
cp $odoo_path/addons/web/static/src/js/core/ram_storage.js extension/web/static/src/js/core

[ -d extension/web/static/src/js/libs ] || mkdir extension/web/static/src/js/libs
cp $odoo_path/addons/web/static/src/js/libs/content-disposition.js extension/web/static/src/js/libs
cp $odoo_path/addons/web/static/src/js/libs/download.js extension/web/static/src/js/libs

[ -d extension/web/static/src/js/services ] || mkdir extension/web/static/src/js/services
cp $odoo_path/addons/web/static/src/js/services/ajax_service.js extension/web/static/src/js/services
cp $odoo_path/addons/web/static/src/js/services/config.js extension/web/static/src/js/services
cp $odoo_path/addons/web/static/src/js/services/core.js extension/web/static/src/js/services
cp $odoo_path/addons/web/static/src/js/services/session.js extension/web/static/src/js/services
cp $odoo_path/addons/web/static/src/js/services/config.js extension/web/static/src/js/services

[ -d extension/web/static/lib ] || mkdir extension/web/static/lib
cp -r $odoo_path/addons/web/static/lib/fontawesome extension/web/static/lib
cp -r $odoo_path/addons/web/static/lib/jquery extension/web/static/lib
cp -r $odoo_path/addons/web/static/lib/jquery.ba-bbq extension/web/static/lib
cp -r $odoo_path/addons/web/static/lib/moment extension/web/static/lib
cp -r $odoo_path/addons/web/static/lib/py.js extension/web/static/lib
cp -r $odoo_path/addons/web/static/lib/qweb extension/web/static/lib
cp -r $odoo_path/addons/web/static/lib/underscore extension/web/static/lib
cp -r $odoo_path/addons/web/static/lib/underscore.string extension/web/static/lib

[ -d extension/web/static/lib/bootstrap/css ] || mkdir -p extension/web/static/lib/bootstrap/css
sassc $odoo_path/addons/web/static/lib/bootstrap/scss/bootstrap.scss > extension/web/static/lib/bootstrap/css/bootstrap.min.css

[ -d extension/web/static/lib/bootstrap/js ] || mkdir -p extension/web/static/lib/bootstrap/js
cp $odoo_path/addons/web/static/lib/bootstrap/js/modal.js extension/web/static/lib/bootstrap/js

echo "Extension created"
