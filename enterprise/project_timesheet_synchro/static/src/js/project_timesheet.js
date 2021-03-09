odoo.define('project_timeshee.ui', function (require ) {
    "use strict";

    var ajax = require('web.ajax');
    var Context = require('web.Context');
    var core = require('web.core');
    var session = require('web.session');
    var Widget = require('web.Widget');
    var time_module = require('web.time');
    var local_storage = require('web.local_storage');
    var ServiceProviderMixin = require('web.ServiceProviderMixin');

    var MAX_AGE = 21; // Age limit in days for activities before they are removed from the app
    var DEFAULT_TIME_UNIT = 0.25;
    var MOTIVATION_MESSAGES = [
            "Have a great day!",
            "Wishing you an awesome day.",
            "Don't forget that you are beautiful, talented and one of a kind.",
            "Think about all you will be able to achieve today!",
            "Our daily advice: just do it!",
            "Opportunities don't happen, you create them.",
            "You can do anything, but not everything.",
    ];
    var SANITIZERREGEX = /\./g; // Since it will be used in a loop, we don't want to compile the regex at each iteration.
    var MODULE_KEY = '__import__.'; // Xml_id prefix.

    // Mobile device detection
    // Awesome Timesheet is used in Android/iOS native app.
    var isMobile = navigator.userAgent.match(/Android/i) ||
                   navigator.userAgent.match(/webOS/i) ||
                   navigator.userAgent.match(/iPhone/i) ||
                   navigator.userAgent.match(/iPad/i) ||
                   navigator.userAgent.match(/iPod/i) ||
                   navigator.userAgent.match(/BlackBerry/i) ||
                   navigator.userAgent.match(/Windows Phone/i);
    // Desktop detection
    // In Odoo, Awesome Timesheet is embedded inside an iframe.
    var isDesktop = !isMobile && window.location.origin.indexOf("chrome-extension://") === -1;
    // Because of the iframe src (/project_timesheet_synchro/timesheet_app),
    // the current path location is 'project_timesheet_synchro' instead of the root path.
    // We need to know the root path to load assets which is the parent folder of
    // 'project_timesheet_synchro' in this case.
    // Must keep the absolute pathname for tests (to avoid 'segmentation fault').
    var rootPath = '';
    if (window.location.pathname.indexOf('project_timesheet_synchro') !== -1) {
        rootPath = isDesktop ? '..' : '.';
    }

    //Main widget to instantiate the app
    var ProjectTimesheet = Widget.extend(ServiceProviderMixin, {
        template: "app",
        xmlDependencies: ['/project_timesheet_synchro/static/src/xml/project_timesheet.xml'],
        jsLibs: [
            rootPath + '/web/static/lib/Chart/Chart.js'
        ],
        custom_events: {
            get_session: function (event) {
                if (event.data.callback) {
                    event.data.callback(session);
                }
            },
        },
        init: function(parent) {
            var self = this;
            this._super(parent);
            ServiceProviderMixin.init.call(this);

            if (isDesktop) {
                $('body').css({'width': '100%', 'height': '100%'}); // Necessary for app embedding
            }

            // Listeners
            core.bus.on('change_screen', this, this.go_to_screen);
            core.bus.on('sync', this, this.sync);
            core.bus.on('reset', this, this.reset_app);
            core.bus.on('after_sync', this, this.after_sync);

            self.session = session; // This makes session accessible in QWEB templates.
            self.syncable = false; // Sync flag. Enabled if the user has a valid session with a server where the appropiate sync module is installed.
            self.sync_in_progress = false;
            self.sync_fail = false;
        },
        /**
         * Reloads the browser session and retrieves user data if the app is started from the browser
         * Otherwise retrives user data based on last user connected, if any.
         */
        willStart: function() {
            var self = this;
            var defs = [
                ajax.loadLibs(this)
            ];
            if(isDesktop) {
                defs.push(session.session_reload().then(function() {
                    self.user = session.username;
                    self.server = session.origin;
                    self.get_user_data(self.user, self.server);
                    self.sanitize_all_ids();
                }));
            }
            else {
                self.user = local_storage.getItem('pt_current_user') ? local_storage.getItem('pt_current_user') : "$no_user$";
                self.server = local_storage.getItem('pt_current_server') ? local_storage.getItem('pt_current_server') : "$no_server$";
                self.get_user_data(self.user, self.server);
                self.sanitize_all_ids();
            }
            defs.push(this._super.apply(this, arguments));
            return Promise.all(defs);
        },
        start: function() {
            var self = this;
            var screen_defs = [];
            var sync_defs = [];

            this.drawer_menu = new DrawerMenu(this);
            this.activities_screen = new Activities_screen(this);
            this.day_planner_screen = new Day_planner_screen(this);
            this.settings_screen = new Settings_screen(this);
            this.edit_activity_screen = new Edit_activity_screen(this);
            this.stats_screen = new Stats_screen(this);
            this.sync_screen = new Sync_screen(this);

            // Setting the ids as in the template
            this.map_ids_to_widgets = {
                'activities': this.activities_screen,
                'edit_activity': this.edit_activity_screen,
                'day_plan': this.day_planner_screen,
                'stats': this.stats_screen,
                'sync': this.sync_screen,
                'settings': this.settings_screen,
            };

            // Defaults: append menu and activities screen
            screen_defs.push(this.drawer_menu.appendTo(this.$el));
            screen_defs.push(this.activities_screen.appendTo(document.createDocumentFragment()));

            // Append ASAP for best UX;
            // Don't wait for sync to load.
            Promise.all(screen_defs).then(function () {
                self.current_screen = self.activities_screen;
                self.go_to_screen({"id": "activities"});
            });

            if (self.server !== "$no_server$" && self.user) {
                session.origin = self.server;
                session.setup(self.server, {use_cors : true});
                session.session_reload().then(function(){
                    // Check if the sync module is installed in the backend and set the syncable flag accordingly
                    sync_defs.push(session.rpc('/web/session/modules').then(function(response){
                        if (response.length > 0 && _.contains(response, 'project_timesheet_synchro')) {
                            self.syncable = true;
                            self.sync({
                                callback : function(){
                                    core.bus.trigger('after_sync');
                                }
                            });
                        }
                    }));
                });
            }
            // Interval for automatic synchronization every hour.
            this.auto_sync = setInterval(function(){
                core.bus.trigger('sync');
            } , 3600*1000);

            // backbutton handler for mobile
            $(document).on("backbutton", function(e) {
                e.preventDefault();
                if (self.current_screen != self.activities_screen) {
                    core.bus.trigger('change_screen', {
                        id : 'activities',
                    });
                }
                else {
                    navigator.app.exitApp();
                }
            });

            return Promise.all(sync_defs);
        },
        /**
         * Attempts to restore the data of the user related to the username and server address given.
         * If no data is available for the user, creates a minimal data object for the user to be able to use the app
         * If the parameter keep_data is true, the data from the previous user will be moved to the data of the new user,
         * which is useful when going from a guest session to a real session.
         */
        get_user_data: function(username, server_address, keep_data) {
            var self = this;

            // Keep the data if necessary, to include it later in the user's data.
            var guest_data = {};
            if(keep_data) {
                guest_data.projects = self.data.projects;
                guest_data.tasks = self.data.tasks;
                guest_data.account_analytic_lines = self.data.account_analytic_lines;
                self.data.projects = [];
                self.data.tasks = [];
                self.data.account_analytic_lines = [];
                self.save_user_data();
            }

            local_storage.setItem('pt_current_user', username);
            // All data
            self.users_data = JSON.parse(local_storage.getItem('pt_data'));
            // User specific data
            self.user_local_data = _.findWhere(self.users_data, {session_user : username, server_address : server_address});
            if (self.user_local_data) {
                self.data = self.user_local_data.data;
            } else {
                var timestamp = (new Date()).getTime();
                var startup_data = {
                    'session_user': username,
                    'server_address': server_address,
                    'data': {
                        'next_aal_id': 1,
                        'next_project_id': 1,
                        'next_task_id': 1,
                        'original_timestamp': timestamp,
                        'settings': {
                            'default_project_id': undefined,
                            'minimal_duration': 0,
                            'time_unit': DEFAULT_TIME_UNIT
                        },
                        'projects': [],
                        'tasks': [],
                        'account_analytic_lines': [],
                    }
                };
                self.data = startup_data.data;
                if (self.users_data) {
                    self.users_data.push(startup_data);
                } else {
                    self.users_data = [startup_data];
                }
            }
            if(keep_data) {
                self.data.projects = self.data.projects.concat(guest_data.projects);
                self.data.tasks = self.data.tasks.concat(guest_data.tasks);
                self.data.account_analytic_lines = self.data.account_analytic_lines.concat(guest_data.account_analytic_lines);
            }
            self.save_user_data();
        },
        save_user_data: function() {
            local_storage.setItem("pt_data", JSON.stringify(this.users_data));
        },
        go_to_screen: function(args) {
            var self = this;
            var next_screen = this.map_ids_to_widgets[args.id];
            this.current_screen.detach();
            var def;
            if (next_screen.has_been_loaded === false) {
                def = next_screen.appendTo(document.createDocumentFragment());
            }
            Promise.resolve(def).then(function () {
                next_screen.attach(self.$el, args.options);
                self.current_screen = next_screen;
            });
        },
        // Data management methods

        // Options should only contain a callback function.
        // If there is a callback, it is always called even if the sync failed or was skipped.
        sync: function(options) {
            if (!this.syncable || this.sync_in_progress) {
                if (options && options.callback) {
                    options.callback();
                }
                return;
            }
            var self = this;
            var defer = new Promise(function (resolve, reject) {
                self.$('.pt_nav_sync a').addClass('pt_sync_in_progress');
                self.sync_in_progress = true;

                // Before syncing, we must ensure that the xml_ids on the server and in the app are appropriate.
                // If they are not, we try to clean them on the server and locally.
                //
                var always = function() {
                    self._rpc({
                            model: 'account.analytic.line',
                            method: 'export_data_for_ui',
                            args: [],
                        })
                        .then(function(sv_data) {
                        // SV => LS sync
                        var sv_aals = sv_data.aals.datas;
                        var sv_tasks = sv_data.tasks.datas;
                        var sv_projects = sv_data.projects.datas;

                        _.each(sv_projects, function(sv_project) {
                            self.clean_export_data_id(sv_project);

                            // Check if the project exists in LS.
                            // If it does we simply update the name, otherwise we copy the project in LS.
                            var ls_project = _.findWhere(self.data.projects, {id : sv_project[0]});
                            if (_.isUndefined(ls_project)) {
                                self.data.projects.push({
                                    id : sv_project[0],
                                    name : sv_project[1]
                                });
                            }
                            else {
                                ls_project.name = sv_project[1];
                            }
                        });
                        self.save_user_data();

                        _.each(sv_tasks, function(sv_task) {
                            self.clean_export_data_id(sv_task);

                            var ls_task = _.findWhere(self.data.tasks, {id : sv_task[0]});
                            if (_.isUndefined(ls_task)) {
                                self.data.tasks.push({
                                    id : sv_task[0],
                                    project_id : sv_task[1],
                                    name : sv_task[3]
                                });
                            }
                            else {
                                ls_task.name = sv_task[3];
                            }
                        });
                        self.save_user_data();

                        _.each(sv_aals, function(sv_aal) {
                            self.clean_export_data_id(sv_aal);

                            // First, check that the aal is related to a project. If not we don't import it.
                            if (!_.isUndefined(sv_aal[8])) {
                                var ls_aal = _.findWhere(self.data.account_analytic_lines, {id : sv_aal[0]});
                                // When unit amount is empty on the server it defaults to false. We want it to default to 0 :
                                if (!sv_aal[6]) {
                                    sv_aal[6] = 0;
                                }

                                // Create case
                                if (_.isUndefined(ls_aal)) {
                                    self.data.account_analytic_lines.push({
                                        id : sv_aal[0],
                                        task_id : sv_aal[1],
                                        desc : sv_aal[3],
                                        date : sv_aal[5],
                                        unit_amount : sv_aal[6],
                                        write_date : sv_aal[7],
                                        sheet_state: sv_aal[8],
                                        project_id : sv_aal[9],
                                    });
                                }
                                else {
                                    //Update case
                                    if (time_module.str_to_datetime(ls_aal.write_date) < time_module.str_to_datetime(sv_aal[7])) {
                                        ls_aal.project_id = sv_aal[9];
                                        ls_aal.task_id = sv_aal[1];
                                        ls_aal.desc = sv_aal[3];
                                        ls_aal.date = sv_aal[5];
                                        ls_aal.unit_amount = sv_aal[6];
                                        ls_aal.write_date = sv_aal[7];
                                    }
                                    // Always update the sheet state as a blocked timesheet should not be editable in the UI.
                                    ls_aal.sheet_state =  sv_aal[8];
                                }
                            }
                        });
                        self.save_user_data();

                        //LS => SV sync
                        var context = new Context({default_is_timesheet : true});
                        // For the aals that need to be synced, update unit_amount with minimal duration or round with time_unit.
                        //This feature is currently enabled. It might need to be moved to the backend.
                        _.each(self.data.account_analytic_lines, function(aal) {
                            if (aal.to_sync) {
                                //
                                if (aal.unit_amount < self.data.settings.minimal_duration) {
                                    aal.unit_amount = self.data.settings.minimal_duration;
                                }
                                else if (self.data.settings.time_unit > 0) {
                                    var round_to = 1 / self.data.settings.time_unit;
                                    aal.unit_amount = (Math.ceil(aal.unit_amount * round_to) / round_to).toFixed(2);
                                }
                            }
                        });
                        var sync_time = new Date();
                        self._rpc({
                                model: 'account.analytic.line',
                                method: 'import_ui_data',
                                args: [self.data.account_analytic_lines , self.data.tasks, self.data.projects],
                                context: context,
                            })
                            .then(function(sv_response) {
                            // The entries that have been removed in the backend must be removed from the LS
                            if (sv_response.projects_to_remove.length) {
                                _.each(sv_response.projects_to_remove, function(project_to_remove_id) {
                                    self.data.projects = _.filter(self.data.projects, function(project) {
                                        return project.id != project_to_remove_id;
                                    });
                                });
                            }
                            if (sv_response.tasks_to_remove.length) {
                                _.each(sv_response.tasks_to_remove, function(task_to_remove_id) {
                                    self.data.tasks = _.filter(self.data.tasks, function(task) {
                                        return task.id != task_to_remove_id;
                                    });
                                });
                            }
                            if (sv_response.aals_to_remove.length) {
                                _.each(sv_response.aals_to_remove, function(aal_to_remove_id) {
                                    self.data.account_analytic_lines = _.filter(self.data.account_analytic_lines, function(aal) {
                                        return aal.id != aal_to_remove_id;
                                    });
                                });
                            }
                            // Set to_sync to false for further syncs, except if womething went wrong, in which case we handle the error.
                            // Also marks aals as problematic if the project or task related has been removed or could not be imported
                            _.each(self.data.account_analytic_lines, function(aal) {
                                var aal_project = _.findWhere(self.data.projects, { id : aal.project_id});
                                var aal_task = undefined;
                                if (aal.task_id) {
                                    aal_task = _.findWhere(self.data.tasks, { id : aal.task_id});
                                }
                                if (_.isUndefined(aal_project) || (aal.task_id && _.isUndefined(aal_task))) {
                                    aal.to_sync = true;
                                    aal.sync_problem = true;
                                }
                                else if (time_module.str_to_datetime(aal.write_date) > sync_time) {
                                    // aal has been created after the synchronisation
                                    aal.to_sync = true;
                                    aal.sync_problem = false;
                                }
                                else if(sv_response.aals_errors.failed_records.indexOf(aal.id) < 0 ) {
                                    aal.to_sync = false;
                                    aal.sync_problem = false;
                                }
                                else {
                                    aal.to_sync = true;
                                    aal.sync_problem = true;
                                }
                            });
                            _.each(self.data.tasks, function(task) {
                                if (sv_response.task_errors.failed_records.indexOf(task.id) < 0) {
                                    task.to_sync = false;
                                    task.sync_problem = false;
                                }
                                else {
                                    task.sync_problem = true;
                                    task.to_sync = true;
                                    self.flush_task(task.id);
                                }
                            });
                            _.each(self.data.projects, function(project) {
                                if (sv_response.project_errors.failed_records.indexOf(project.id) < 0) {
                                    project.to_sync = false;
                                    project.sync_problem = false;
                                }
                                else {
                                    project.sync_problem = true;
                                    project.to_sync = true;
                                    self.flush_project(project.id);
                                }
                            });
                            self.sync_time = sync_time;
                            self.$('.pt_nav_sync a').removeClass('pt_sync_in_progress');
                            self.sync_in_progress = false;
                            self.flush_activities(MAX_AGE);
                            self.save_user_data();
                            self.sync_fail = false;
                            resolve();
                            if (options && options.callback) {
                                options.callback();
                            }
                        });
                    });
                };
                self.clean_xml_ids().then(always).guardedCatch(function() {
                    self.$('.pt_nav_sync a').removeClass('pt_sync_in_progress');
                    self.sync_in_progress = false;
                    self.sync_fail = true;
                    resolve();
                    if (options && options.callback) {
                        options.callback();
                    }
                    always();
                });

            });

            return defer;
        },
        /*
        * Called after a synchronization
        * It triggers a refresh of the current screen, only if the current screen is the Activities screen.
        * This is useful to display new synchronized activities.
        * If the user is on a different screen, a refresh is not as useful, and can even be troubling,
        * e.g. if the user is editing or creating an activity.
        */
        after_sync: function() {
            if (this.current_screen === this.activities_screen) {
                core.bus.trigger('change_screen', {
                    id : 'activities'
                });
            }
        },
        // Remove the activities that are older than a certain threshold.
        // Age is the max number of days old an activity can be to be kept in the app
        flush_activities: function(max_age) {
            var self = this;
            self.data.account_analytic_lines = _.filter(self.data.account_analytic_lines, function(aal) {
                var delta = moment(aal.date, 'YYYYMMDD').diff(moment(new Date()), 'days');
                return (Math.abs(delta) < max_age);
            });
        },
        flush_task: function(task_id) {
            var self = this;
            var task = _.findWhere(self.data.tasks, {id : task_id});
            if (task) {
                var some_aal = _.findWhere(self.data.account_analytic_lines, {task_id : task_id});
                if (!some_aal) {
                    self.data.tasks.splice(_.indexOf(self.data.tasks), 1);
                }
            }
        },
        flush_project: function(project_id) {
            var self = this;
            var project = _.findWhere(self.data.projects, {id : project_id});
            if (project) {
                var some_aal = _.findWhere(self.data.account_analytic_lines, {project_id : project_id});
                var some_task = _.findWhere(self.data.tasks, {project_id : project_id});
                if (!(some_aal || some_task)) {
                    self.data.projects.splice(_.indexOf(self.data.projects, project), 1);
                }
            }
        },
        reset_app : function() {
            local_storage.clear();
        },
        // Odoo XML ids require a specific format : module.id.
        // This function removes any extra dot contained in an id string
        sanitize_xml_id: function(xml_id) {
            return xml_id.replace(SANITIZERREGEX, '');
        },
        // Cleans ids that were created earlier with a wrong format and module key.
        fix_id: function(id) {
            if(id && id.indexOf('Project_timesheet_UI') >= 0) {
                id = id.replace(SANITIZERREGEX, '');
                id = '__export__.' + id.replace(/Project_timesheet_UI/, '');
            }
            return id;
        },
        // Some ids that were created earlier do not respect the conventions.
        // This method ensures that all ids are valid.
        sanitize_all_ids: function() {
            var self = this;
            _.each(self.data.projects, function(project) {
                project.id = self.fix_id(project.id);
            });
            _.each(self.data.tasks, function(task) {
                task.id = self.fix_id(task.id);
                task.project_id = self.fix_id(task.project_id);
            });
            _.each(self.data.account_analytic_lines, function(aal) {
                aal.id = self.fix_id(aal.id);
                aal.task_id = self.fix_id(aal.task_id);
                aal.project_id = self.fix_id(aal.project_id);
            });
            self.save_user_data();
        },
        process_all_ids: function(process_function) {
            var self = this;
            _.each(self.data.projects, function(project) {
                project.id = process_function(project.id);
            });
            _.each(self.data.tasks, function(task) {
                task.id = process_function(task.id);
                task.project_id = process_function(task.project_id);
            });
            _.each(self.data.account_analytic_lines, function(aal) {
                aal.id = process_function(aal.id);
                aal.task_id = process_function(aal.task_id);
                aal.project_id = process_function(aal.project_id);
            });
            self.save_user_data();
        },
        convert_module_to_export: function(id) {
            if (id && id.indexOf('project_timesheet_synchro') >= 0) {
                id = id.replace('project_timesheet_synchro', '__export__');
            }
            return id;
        },
        /**
         * Ensure that the xml id contains a dot.
         * This is required because the 'export_data' Python method
         * doesn't prefix the xml_id by dot if the module name is
         * an empty string.
         */
        clean_export_data_id: function(sv_data) {
            if (sv_data[0].indexOf('.') === -1) {
                // Convert 'project_project_x' to '.project_project_x'
                sv_data[0] = '.'.concat(sv_data[0]);
            }
        },
        clean_xml_ids: function() {
            var self = this;
            return new Promise(function (resolve, reject) {
                if (self.data.data_version === 1) {
                    resolve(); // Cleanup has already been performed.
                } else {
                    var always = function(res) {
                        if (res === true) {
                            // Everything went fine, any local xml_ids with project_timesheet_synchro can be converted
                            self.process_all_ids(self.convert_module_to_export);
                            self.data.data_version = 1;
                            resolve();
                        } else {
                            var domain = [
                                ['module', '=', 'project_timesheet_synchro'],
                                ['model', 'in', [
                                    'mail.alias',
                                    'account.analytic.account',
                                    'project.project',
                                    'project.task',
                                    'account.analytic.line'
                                ]]
                            ];
                            self._rpc({
                                    model: 'ir.model.data',
                                    method: 'search',
                                    args: [domain],
                                })
                                .then(function (ids) {
                                    if (ids.length === 0) { // there are no dirty ids on the server
                                        self.process_all_ids(self.convert_module_to_export);
                                        self.data.data_version = 1;
                                        resolve();
                                    } else {
                                        // Show a warning to the user, once a day
                                        if (!self.data.warning_date || (self.data.warning_date && moment(self.data.warning_date).diff(new Date(), 'days') !== 0)) {
                                            alert('The code on your Odoo server is not up to date and an important update has been released. You or your system administrator should consider retrieving it as soon as possible.');
                                            self.data.warning_date = new Date();
                                        }
                                        resolve();
                                    }
                                }).guardedCatch(function (err) {
                                    resolve();
                                });
                        }
                    };
                    self._rpc({
                        model: 'account.analytic.line',
                        method: 'clean_xml_ids',
                        args: [],
                    }).then(always).guardedCatch(always);
                }
            });
        },
    });

    var DrawerMenu = Widget.extend({
        template: "drawer_menu",
        events: {
            "click ul.pt_links_list li" : "on_menu_item_click",
            "click" : "on_close_menu_by_click",
            "touchstart .pt_drawer_menu,.pt_drawer_menu_wrapper,.pt_drawer_menu_shade" : "on_menu_touch_start",
            "touchmove .pt_drawer_menu,.pt_drawer_menu_wrapper,.pt_drawer_menu_shade" : "on_touchmove",
        },
        init: function(parent) {
            this._super(parent);
            core.bus.on('show_menu', this, this.toggle_drawer_menu);
        },
        on_menu_item_click: function(ev) {
            core.bus.trigger('change_screen', {
                id: $(ev.currentTarget).data('menu-id'),
                options: ($(ev.currentTarget).data('options')),
            });
            this.$el.removeClass('shown');
        },
        on_close_menu_by_click: function(ev) {
            if ($(ev.target).hasClass('pt_drawer_menu_shade')) {
                this.toggle_drawer_menu();
            }
        },
        toggle_drawer_menu: function() {
            this.$el.toggleClass('shown');
        },
        on_touchmove: function(event) {
            var touch;
            if (event.originalEvent.touches && event.originalEvent.touches[0]) {
                touch = event.originalEvent.touches[0];
            }
            else if (event.originalEvent.changedTouches && event.originalEvent.changedTouches[0]) {
                touch = event.originalEvent.changedTouches[0];
            }
            if (touch) {
                var final_touch_X = touch.pageX;
                var deltaX = this.initial_touch_X - final_touch_X;
                if (deltaX > 5) {
                    this.toggle_drawer_menu();
                }
                this.initial_touch_X = undefined;
            }
        },
        on_menu_touch_start: function(event) {
            var touch;
            if (event.originalEvent.touches && event.originalEvent.touches[0]) {
                touch = event.originalEvent.touches[0];
                this.initial_touch_X = touch.pageX;
            } else if (event.originalEvent.changedTouches && event.originalEvent.changedTouches[0]) {
                touch = event.originalEvent.changedTouches[0];
                this.initial_touch_X = touch.pageX;
            }
        },
    });

    var BasicScreenWidget = Widget.extend({
        events: {
            "click .pt_burger_menu_open": "on_open_menu",
        },
        // ----------------------------------------------------------
        // Screen widget lifecyle
        // ----------------------------------------------------------
        init: function(parent) {
            this._super(parent);
            this.time_module = time_module;  // Makes the time_module accessible inside qweb templates
            this.has_been_loaded = false;

            Object.defineProperty(this, 'today', {
                get: function () {
                    return time_module.date_to_str(new Date());
                }
            });
        },
        start: function() {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                self.has_been_loaded = true;
            });
        },
        /**
         * Part of the lifecyle of basic screen widget, this method updates `this.options`
         * and calls `renderElement` before appending itself to the `el` argument.
         * @param {options}
         * @param {el}
         */
        attach: function (el, options) {
            if (options) {
                this.options = options;
            }
            this.renderElement();
            this.$el.appendTo(el);
        },
        /**
         * Part of the lifecyle of basic screen widget, this method detach the widget from
         * the DOM and run the `didDetach` method.
         */
        detach: function () {
            this.$el.detach();
            this.didDetach();
        },
        didDetach: function() {
            return;
        },
        // ----------------------------------------------------------
        // Common helpers
        // ----------------------------------------------------------
        on_open_menu: function() {
            core.bus.trigger('show_menu');
        },
        get_project_name: function(project_id) {
            var project = _.findWhere(this.getParent().data.projects, {id : project_id});
            return project ? project.name : "No project";
        },
        get_task_name: function(task_id) {
            var task = _.findWhere(this.getParent().data.tasks, {id : task_id});
            return task ? task.name : "No task";
        },
        get_project_name_from_task_id: function(task_id) {
            var self = this;
            var task = _.findWhere(self.getParent().data.tasks, {id : task_id});
            if (!_.isUndefined(task)) {
                var project = _.findWhere(self.getParent().data.projects, {id : task.project_id});
                if (!_.isUndefined(project)) {
                    return project.name;
                }
                else {
                    return undefined;
                }
            }
        },
        // Method used to count the number of synchronization errors that remain.
        // This number is shown in the footer of the app.
        count_sync_errors: function() {
            var data = this.getParent().data;
            var sync_errors_count = 0;
            _.each([data.tasks, data.projects, data.account_analytic_lines], function(list) {
                _.each(list, function(item) {
                    if (item.sync_problem) {
                        sync_errors_count++;
                    }
                });
            });
            this.getParent().sync_errors_count = sync_errors_count;
        },
        // Utility methods to format and validate time
        // Takes a decimal hours and converts it to hh:mm string representation
        // e.g. 1.5 => "01:30"
        unit_amount_to_hours_minutes: function(unit_amount) {
            if (_.isUndefined(unit_amount) || unit_amount === 0) {
                return "00:00";
            }

            var minutes = Math.round((unit_amount % 1) * 60);
            var hours = Math.floor(unit_amount);

            return this.zero_fill(hours) + ":" + this.zero_fill(minutes);
        },
        // Takes a string as input and tries to parse it as a hh:mm duration/ By default, strings without ":" are considered to be hh.
        // We use % 1 to avoid accepting NaN as an integer.
        validate_duration: function(hh_mm) {
            var time = hh_mm.split(":");
            var hours;
            // Decimal input case (1.5)
            if (time.length === 1) {
                hours = parseFloat(time[0]);
                if (isNaN(hours)) {
                    return undefined;
                }
                else {
                    return hours.toString();
                }
            }
            // hhmm input case (01:30)
            else if (time.length === 2) {
                hours = parseInt(time[0]);
                var minutes = parseInt(time[1]);
                if ((hours % 1 === 0) && (minutes % 1 === 0) && minutes < 61) {
                    return this.zero_fill(hours) + ":" + this.zero_fill(minutes);
                }
                else {
                    return undefined;
                }
            } else {
                return undefined;
            }
        },
        hh_mm_to_unit_amount: function(hh_mm) {
            var time = hh_mm.split(":");
            if (time.length === 1) {
                return parseFloat(time[0]);
            } else if (time.length === 2) {
                var hours = parseInt(time[0]);
                var minutes = parseInt(time[1]);
                return Math.round((hours + (minutes / 60 )) * 100) / 100;
            } else {
                return undefined;
            }
        },
        zero_fill : function(number) {
            return (number < 10) ? "0" + number.toString() : number.toString();
        },
    });

    var Activities_screen = BasicScreenWidget.extend({
        template: "activities_screen",
        init: function(parent) {
            var self = this;
            this._super(parent);
            this.motivation_text = this.get_motivation_text();
            // Flags to select daily or weekly view
            this.show_week = false;
            this.show_today = true;
            // Events specific to this screen
            _.extend(self.events,
                {
                    "click .pt_button_plus_activity":"create_activity",
                    "click .pt_activity":"edit_activity",
                    "click .pt_btn_start_timer":"start_timer",
                    "click .pt_btn_stop_timer":"stop_timer",
                    "click .pt_quick_add_time" : "quick_add_time",
                    "click .pt_quick_subtract_time" : "quick_subtract_time",
                    "mouseover .pt_duration" : "on_duration_over",
                    "mouseout .pt_duration" : "on_duration_out",
                    "click .pt_duration_continue":"on_continue_activity",
                    "click .pt_btn_interrupt_activity":"on_interrupt_activity",
                    "click .pt_delete_activity" : "delete_activity"
                }
            );

            // Checks if there is a timer in progress at startup
            // Checks if the timer is linked to a scpecific activity, if needed.
            this.current_activity = false;
            this.timer_on = false;
            if (local_storage.getItem("pt_start_timer_time")) {
                this.start_timer_time = JSON.parse(local_storage.getItem("pt_start_timer_time"));
                var start_amount = 0;

                if (local_storage.getItem("pt_timer_activity_id")) {
                    var current_activity_id = JSON.parse(local_storage.getItem("pt_timer_activity_id"));
                    this.current_activity = _.findWhere(self.getParent().data.account_analytic_lines , {id : current_activity_id});
                    start_amount = this.current_activity.unit_amount;
                }
                this.timer_start = setInterval(function() {self.refresh_timer(self.start_timer_time, start_amount);},500);
                this.timer_on = true;
            }

            this.make_activities_list();
        },
        get_motivation_text: function() {
            return MOTIVATION_MESSAGES[Math.floor((Math.random() * MOTIVATION_MESSAGES.length))];
        },
        attach: function(el, options) {
            if (options && options.show_today) {
                this.show_today = true;
                this.show_week = false;
            } else if (options && options.show_week) {
                this.show_today = false;
                this.show_week = true;
            }
            this.make_activities_list();
            return this._super.apply(this, arguments);
        },
        // Prepares the list of activities that will be rendered on the activities page, based on the viewing mode : day or week.
        make_activities_list: function() {
            var self = this;
            self.activities_list = [];
            _.each(self.getParent().data.account_analytic_lines, function(aal) {
                if(aal.to_remove) return;
                if(self.show_today && aal.date === self.today){
                    self.activities_list.push(aal);
                }
                else if(self.show_week) {
                    var delta = moment(aal.date, 'YYYYMMDD').diff(moment(self.today, 'YYYYMMDD').startOf('week'), 'days');
                    if (delta <= 7 && delta >= 0){
                        self.activities_list.push(aal);
                    }
                }
            });
            // For the the weekly view, we sort the list by date, in descending order
            if(self.show_week) {
                self.activities_list = _.sortBy(self.activities_list, function(aal) {
                    return - moment(aal.date, 'YYYYMMDD').valueOf();
                })
            }

        },
        create_activity: function(event, unit_amount) {
            core.bus.trigger('change_screen', {
                id : 'edit_activity',
                options : {
                    unit_amount : unit_amount,
                },
            });
        },
        edit_activity: function(event) {
            core.bus.trigger('change_screen', {
                id : 'edit_activity',
                options : {
                    activity_id : event.currentTarget.dataset.activity_id,
                },
            });
        },
        refresh_timer: function(start_time, start_amount) {
            var ms = moment(moment(new Date()).add(start_amount,"hours")).diff(moment(start_time));
            var d = moment.duration(ms);
            var hours = Math.floor(d.asHours());
            if (hours < 10) {
                hours = "0" + hours;
            }
            this.$(".pt_timer_clock_hh_mm").text(hours + moment.utc(d.asMilliseconds()).format(":mm"));
            this.$(".pt_timer_clock_ss").text(moment.utc(d.asMilliseconds()).format(":ss"));
        },
        start_timer: function() {
            var self = this;
            self.timer_on = true;
            self.start_timer_time = new Date();
            if(window.chrome && window.chrome.storage) {
                window.chrome.storage.local.set({ "isTimerOn": true }, function () {});
            }
            local_storage.setItem("pt_start_timer_time", JSON.stringify(self.start_timer_time));
            this.timer_start = setInterval(function() {self.refresh_timer(self.start_timer_time, 0);},500);
            core.bus.trigger('change_screen', {
                id : 'activities'
            });
            // First timer refresh before interval to avoid delay
            self.refresh_timer(self.start_timer_time, 0);
        },
        on_continue_activity: function(event) {
            var activity = _.findWhere(this.getParent().data.account_analytic_lines , {id : event.currentTarget.dataset.activity_id});
            var self = this;
            this.current_activity = activity;
            this.timer_on = true;
            this.start_timer_time = new Date();
            local_storage.setItem("pt_start_timer_time", JSON.stringify(self.start_timer_time));
            local_storage.setItem("pt_timer_activity_id", JSON.stringify(activity.id));
            this.timer_start = setInterval(function() {self.refresh_timer(self.start_timer_time, self.current_activity.unit_amount);},500);
            core.bus.trigger('change_screen', {
                id : 'activities'
            });
            // First timer refresh before interval to avoid delay
            self.refresh_timer(self.start_timer_time, self.current_activity.unit_amount);
        },
        on_interrupt_activity: function() {
            var self = this;
            var activity_id = JSON.parse(local_storage.getItem("pt_timer_activity_id"));
            var activity = _.findWhere(this.getParent().data.account_analytic_lines , {id : activity_id});
            clearInterval(this.timer_start);
            this.$(".pt_timer_clock").text("");
            var start_time = new Date(JSON.parse(local_storage.getItem("pt_start_timer_time")));
            var ms = moment(moment(new Date()).add(activity.unit_amount,"hours")).diff(moment(start_time));
            var d = moment.duration(ms);
            var hours = Math.floor(d.asHours());
            var hh_mm_value = hours + moment.utc(d.asMilliseconds()).format(":mm");
            activity.unit_amount = this.hh_mm_to_unit_amount(hh_mm_value);
            activity.write_date = time_module.datetime_to_str(new Date());
            activity.date = self.today;
            activity.to_sync = true;

            this.getParent().data.account_analytic_lines.sort(function(a,b) {
                return time_module.str_to_datetime(b.write_date) - time_module.str_to_datetime(a.write_date);
            });
            this.current_activity = false;
            this.timer_on = false;
            this.getParent().save_user_data();
            local_storage.removeItem("pt_start_timer_time");
            local_storage.removeItem("pt_timer_activity_id");
            core.bus.trigger('change_screen', {
                id : 'activities'
            });
        },
        stop_timer: function() {
            var unit_amount = this.hh_mm_to_unit_amount(moment.utc(new Date() - new Date(JSON.parse(local_storage.getItem("pt_start_timer_time")))).format("HH:mm"));
            this.create_activity(undefined, unit_amount);
        },
        clear_timer: function() {
            this.timer_on = false;
            clearInterval(this.timer_start);
            this.current_activity = false;
            local_storage.removeItem("pt_start_timer_time");
        },
        quick_add_time: function(event) {
            var activity = _.findWhere(this.getParent().data.account_analytic_lines,  {id: event.currentTarget.dataset.activity_id});
            if (_.isUndefined(this.getParent().data.settings.time_unit)) {
                activity.unit_amount = parseFloat(activity.unit_amount) + DEFAULT_TIME_UNIT;
            } else {
                activity.unit_amount = parseFloat(activity.unit_amount) + this.getParent().data.settings.time_unit;
            }
            activity.write_date = time_module.datetime_to_str(new Date());
            activity.to_sync = true;
            this.getParent().save_user_data();
            this.renderElement();
        },
        quick_subtract_time: function(event) {
            var self = this;
            var activity = _.findWhere(this.getParent().data.account_analytic_lines,  {id: event.currentTarget.dataset.activity_id});
            if (activity.unit_amount <= 0) {
                self.modal_activity = activity;
                self.$('.pt_deletion_from_list_modal').modal();
            } else {
                if (_.isUndefined(this.getParent().data.settings.time_unit)) {
                    activity.unit_amount = parseFloat(activity.unit_amount) - DEFAULT_TIME_UNIT;
                }
                else {
                    activity.unit_amount = parseFloat(activity.unit_amount) - this.getParent().data.settings.time_unit;
                }
                if (activity.unit_amount < 0) {
                    activity.unit_amount = 0;
                }
                activity.write_date = time_module.datetime_to_str(new Date());
                activity.to_sync = true;
                this.getParent().save_user_data();
                this.renderElement();
            }
        },
        delete_activity: function() {
            this.modal_activity.to_remove = true;
            this.getParent().save_user_data();
            core.bus.trigger('change_screen', {
                id : 'activities',
            });
        },
        on_duration_over: function(event) {
            if (local_storage.getItem("pt_start_timer_time") === null) {
                var duration_box = this.$(event.currentTarget);
                duration_box.addClass("pt_duration_continue");
                duration_box.children(".pt_duration_time").addClass('d-none');
                duration_box.children(".pt_continue_activity_btn").removeClass('d-none');
            }
        },
        on_duration_out: function(event) {
            var duration_box = this.$(event.currentTarget);
            duration_box.removeClass("pt_duration_continue");
            duration_box.children(".pt_duration_time").removeClass('d-none');
            duration_box.children(".pt_continue_activity_btn").addClass('d-none');
        },
        get_total_time: function() {
            var total_time = 0;
            _.each(this.activities_list, function(activity) {
                var unit_amount = parseFloat(activity.unit_amount);
                if (!isNaN(unit_amount) && !activity.to_remove) {
                    total_time += unit_amount;
                }
            });
            return total_time;
        },
    });

    var Day_planner_screen = BasicScreenWidget.extend({
        template: "day_planner_screen",
        init: function(parent) {
            var self = this;
            this._super.apply(this, arguments);
            // Intentionnally left empty to make startup faster.
            this.day_plan_list = [];
            _.extend(self.events, {
                "click tr.pt_day_plan_add" : "quick_create",
                "click .pt_today_link" : "go_to_today",
            });
        },
        attach: function(el, options) {
            this.make_day_plan_list();
            return this._super.apply(this, arguments);
        },
        // Populates the list of projects and tasks displayed in the day planner.
        // Each entry of the list is a [project, task] pair, where task might be false.
        make_day_plan_list: function() {
            var self = this;
            var today = this.today;
            var aals = self.getParent().data.account_analytic_lines;
            self.day_plan_list = [];
            _.each(aals, function(aal) {
                if(!aal.to_remove) {
                    var to_add = true;
                    _.each(self.day_plan_list, function(list_entry) {
                        if (!aal.task_id || aal.task_id === 'false') {
                            aal.task_id = false; // Uniformize the false values, in case the value was something falsy but not false
                        }
                        if (list_entry[0] == aal.project_id && list_entry[1] == aal.task_id) {
                            to_add =false;
                        }
                    });
                    if (to_add && !_.findWhere(aals, {project_id : aal.project_id, task_id : aal.task_id, date : today})) {
                        self.day_plan_list.push([aal.project_id, aal.task_id]);
                    }
                }
            });
        },
        // Creates an activity for the project or project/task selected, with a duration of 0.
        // Uses list.unshift to make sure the new activity appears on top of the list without having to sort everything.
        quick_create: function(event) {
            var self = this;

            var task_id = false;
            if (event.currentTarget.dataset.task_id && event.currentTarget.dataset.task_id !== 'false') {
                task_id = event.currentTarget.dataset.task_id;
            }

            var activity = {
                id : MODULE_KEY + self.getParent().sanitize_xml_id(self.getParent().user + self.getParent().data.original_timestamp + "_aal_" + self.getParent().data.next_aal_id),
                project_id : event.currentTarget.dataset.project_id,
                task_id : task_id,
                date : self.today,
                unit_amount : 0,
                desc : " ",
                to_sync : true,
                write_date : time_module.datetime_to_str(new Date()),
            };
            self.getParent().data.next_aal_id++;
            self.getParent().data.account_analytic_lines.unshift(activity);
            self.getParent().save_user_data();
            this.$('.pt_day_plan_message').show(0).delay(2000).hide(0);
            $(event.currentTarget).addClass('pt_checked').removeClass('pt_day_plan_add');
        },
        go_to_today: function() {
            core.bus.trigger('change_screen', {
                id : 'activities',
                options : {
                    show_today : true,
                },
            });
        },
    });

    var Settings_screen = BasicScreenWidget.extend({
        template: "settings_screen",
        init: function(parent) {
            var self = this;
            this._super(parent);
            _.extend(self.events,
                {
                    "change input.pt_minimal_duration":"on_change_minimal_duration",
                    "change input.pt_time_unit":"on_change_time_unit",
                    "change input.pt_default_project_select2":"on_change_default_project",
                }
            );
        },
        attach: function(el, options) {
            this._super.apply(this, arguments);
            this.initialize_project_selector();
        },
        didDetach: function() {
            // Avoids a leak as select2 elements are not properly detached with the widget.
            $("[class|='select2']").remove();
        },
        initialize_project_selector: function() {
            var self = this;
            // Initialization of select2 for projects
            function format(item) {return item.name;}
            function formatRes(item) {
                if (item.isNew) {
                    return "Create Project : " + item.name;
                }
                else {
                    return item.name;
                }
            }
            this.$('.pt_default_project_select2').select2({
                data: {results : self.getParent().data.projects , text : 'name'},
                formatSelection: format,
                formatResult: formatRes,
                createSearchChoicePosition : 'bottom',
                placeholder: "No default project",
                allowClear: true,
                containerCss: {"display":"block"},
                createSearchChoice: function(user_input, new_choice) {
                    //Avoid duplictate projects
                    var duplicate = _.find(self.getParent().data.projects, function(project) {
                        return (project.name.toUpperCase() === user_input.trim().toUpperCase());
                    });
                    if (duplicate) {
                        return undefined;
                    }
                    var res = {
                        id : MODULE_KEY + self.getParent().sanitize_xml_id(self.getParent().user + self.getParent().data.original_timestamp + "_project_" + self.getParent().data.next_project_id),
                        name : user_input.trim(),
                        isNew: true,
                    };
                    return res;
                },
                initSelection : function(element, callback) {
                    var data = {id: self.getParent().data.settings.default_project_id, name : self.get_project_name(self.getParent().data.settings.default_project_id)};
                    callback(data);
                }
            }).select2('val',[]);
        },
        on_change_default_project: function(event) {
            var self = this;
            // "cleared" case
            if (_.isUndefined(event.added)) {
                self.getParent().data.settings.default_project_id = undefined;
            }
            // "Select" case
            else {
                var selected_project = {
                    name : event.added.name,
                    id : event.added.id
                };
                if (event.added.isNew) {
                    self.getParent().data.next_project_id++;
                    selected_project.to_sync = true;
                    self.getParent().data.projects.push(selected_project);
                }
                self.getParent().data.settings.default_project_id = selected_project.id;
            }
            self.getParent().save_user_data();
        },
        on_change_minimal_duration: function() {
            var min_duration = parseInt(this.$("input.pt_minimal_duration").val(), 10);
            if (min_duration >= 0) {
                this.getParent().data.settings.minimal_duration = min_duration / 60;
                this.getParent().save_user_data();
                core.bus.trigger('change_screen', {
                    id : 'settings',
                });
            } else {
                this.$('.pt_settings_alert').show(0).delay(5000).hide(0);
                this.$("div.pt_duration_fg").addClass('o_has_error').find('.form-control, .custom-select').addClass('is-invalid');
                this.$("input.pt_minimal_duration").val('').focus();
            }
        },
        on_change_time_unit: function() {
            var time_unit = parseInt(this.$("input.pt_time_unit").val(), 10);
            if (time_unit >= 0) {
                this.getParent().data.settings.time_unit = time_unit / 60;
                this.getParent().save_user_data();
                core.bus.trigger('change_screen', {
                    id : 'settings',
                });
            } else {
                this.$('.pt_settings_alert').show(0).delay(5000).hide(0);
                this.$("div.pt_time_unit_fg").addClass('o_has_error').find('.form-control, .custom-select').addClass('is-invalid');
                this.$("input.pt_time_unit").val('').focus();
            }
        },
    });

    var Edit_activity_screen = BasicScreenWidget.extend({
        template: "edit_activity_screen",
        init: function(parent) {
            var self = this;
            this._super(parent);
            _.extend(self.events,
                {
                    "change input.pt_activity_duration":"on_change_duration",
                    "change input.pt_activity_duration_hh":"on_change_duration",
                    "change input.pt_activity_duration_mm":"on_change_duration",
                    "change textarea.pt_description":"on_change_description",
                    "change input.pt_activity_project":"on_change_project",
                    "change input.pt_activity_task":"on_change_task",
                    "click .pt_discard_changes":"discard_changes",
                    "click .pt_validate_edit_btn" : "save_changes",
                    "click .pt_delete_activity" : "delete_activity",
                }
            );
            this.isMobile = isMobile;
            this.reset_activity();
        },
        attach: function(el, options) {
            // Edit case
            if (options.activity_id) {
                this.activity = _.clone(_.findWhere(this.getParent().data.account_analytic_lines,  {id:options.activity_id}));
            }
            // Create case
            else {
                this.reset_activity();
                if (options.unit_amount) {
                    this.activity.unit_amount = options.unit_amount;
                }
            }
            this._super.apply(this, arguments);
            this.initialize_project_selector();
            this.initialize_task_selector();
        },
        didDetach: function() {
            // Avoids a leak as select2 elements are not properly detached with the widget.
            $("[class|='select2']").remove();
        },
        initialize_project_selector: function() {
            var self = this;
            // Initialization of select2 for projects
            function format(item) {return item.name;}
            function formatRes(item) {
                if (item.isNew) {
                    return "Create Project : " + item.name;
                }
                else {
                    return item.name;
                }
            }
            this.$('.pt_activity_project').select2({
                data: {results : self.getParent().data.projects , text : 'name'},
                formatSelection: format,
                formatResult: formatRes,
                createSearchChoicePosition : 'bottom',
                containerCss: {"display":"block"},
                createSearchChoice: function(user_input, new_choice) {
                    //Avoid duplictate projects in one project
                    var duplicate = _.find(self.getParent().data.projects, function(project) {
                        return (project.name.toUpperCase() === user_input.trim().toUpperCase());
                    });
                    if (duplicate) {
                        return undefined;
                    }
                    var res = {
                        id : MODULE_KEY + self.getParent().sanitize_xml_id(self.getParent().user + self.getParent().data.original_timestamp + "_project_" + self.getParent().data.next_project_id),
                        name : user_input.trim(),
                        isNew: true,
                    };
                    return res;
                },
                initSelection : function(element, callback) {
                    var data = {id: self.activity.project_id, name : self.get_project_name(self.activity.project_id)};
                    callback(data);
                }
            });
        },
        // Initialization of select2 for tasks
        initialize_task_selector: function() {
            var self = this;
            function format(item) {return item.name;}
            function formatRes(item) {
                if (item.isNew) {
                    return "Create Task : " + item.name;
                }
                else {
                    return item.name;
                }
            }
            self.task_list = _.where(self.getParent().data.tasks, {project_id : self.activity.project_id});
            this.$('.pt_activity_task').select2({
                data: {results : self.task_list , text : 'name'},
                formatSelection: format,
                formatResult: formatRes,
                allowClear : true,
                placeholder: "No task selected",
                createSearchChoicePosition : 'bottom',
                containerCss: {"display":"block"},
                createSearchChoice: function(user_input, new_choice) {
                    //Avoid duplictate tasks in one project
                    var duplicate = _.find(self.task_list, function(task) {
                        return (task.name.toUpperCase() === user_input.trim().toUpperCase());
                    });
                    if (duplicate) {
                        return undefined;
                    }
                    var res = {
                        id : MODULE_KEY + self.getParent().sanitize_xml_id(self.getParent().user + self.getParent().data.original_timestamp + "_task_" + self.getParent().data.next_task_id),
                        name : user_input.trim(),
                        isNew: true,
                        project_id: self.activity.project_id
                    };
                    return res;
                },
                initSelection : function(element, callback) {
                    var data = {id: self.activity.task_id, name : self.get_task_name(self.activity.task_id)};
                    callback(data);
                }
            }).select2('val',[]);
        },
        on_change_project: function(event) {
            var self = this;
            var selected_project = {
                name : event.added.name,
                id : event.added.id
            };
            if (event.added.isNew) {
                self.getParent().data.next_project_id++;
                selected_project.to_sync = true;
                self.getParent().data.projects.push(selected_project);
                self.getParent().save_user_data();
            }
            self.activity.project_id = selected_project.id;
            // If the project has been changed, we reset the task.
            self.activity.task_id = false;
            self.renderElement();
            self.initialize_project_selector();
            self.initialize_task_selector();
        },
        on_change_task: function(event) {
            var self = this;
            if (_.isUndefined(event.added)) {
                self.activity.task_id = undefined;
            } else {
                var selected_task = {
                    name : event.added.name,
                    id : event.added.id,
                    project_id: event.added.project_id
                };
                if (event.added.isNew) {
                    self.getParent().data.next_task_id++;
                    selected_task.to_sync = true;
                    self.getParent().data.tasks.push(selected_task);
                    self.task_list.push(selected_task);
                    self.getParent().save_user_data();
                }
                self.activity.task_id = selected_task.id;
            }
        },
        on_change_duration: function(event) {
            var self = this;
            var duration;
            // Mobile version handling, where we have two input field with type number
            if (self.isMobile) {
                var hh = this.$("input.pt_activity_duration_hh").val();
                if (!hh) {hh = "0";}
                var mm = this.$("input.pt_activity_duration_mm").val();
                if (!mm) {mm = "0";}
                duration = self.validate_duration(hh + ':' + mm);
                if (_.isUndefined(duration)) {
                    this.$("input.pt_activity_duration_hh").val("00");
                    this.$("input.pt_activity_duration_mm").val("00");
                    this.$("p.pt_duration_input_msg").text("Please enter a valid duration!");
                 }
                else {
                    this.activity.unit_amount = self.hh_mm_to_unit_amount(duration);
                    var duration_array = this.unit_amount_to_hours_minutes(this.activity.unit_amount).split(':');
                    this.$("input.pt_activity_duration_hh").val(duration_array[0]);
                    this.$("input.pt_activity_duration_mm").val(duration_array[1]);
                    this.$("p.pt_duration_input_msg").text("");
                }
            }
            // Chrome extension & desktop handling; Only one input field
            else {
                duration = self.validate_duration(this.$("input.pt_activity_duration").val());
                if (_.isUndefined(duration)) {
                    this.$("input.pt_activity_duration").val("00:00");
                    this.$("p.pt_duration_input_msg").text("Please enter a valid duration in the hh:mm format, such as 01:30, or 1.5");
                }
                else {
                    this.activity.unit_amount = self.hh_mm_to_unit_amount(duration);
                    this.$("input.pt_activity_duration").val(this.unit_amount_to_hours_minutes(this.activity.unit_amount));
                    this.$("p.pt_duration_input_msg").text("");
                }
            }
        },
        on_change_description: function(event) {
            this.activity.desc = this.$("textarea.pt_description").val();
            // The description field must not be empty
            if (this.activity.desc.length < 1) {
                this.activity.desc = " ";
            }
        },

        // Saves the changes made on an activity in th edition screen
        // If the activity preexisted, it will be updated.
        // Otherwise, a new activity is created with the appropriate values.
        // The only required field is "project_id".
        save_changes: function() {
            this.clear_timer();
            if(window.chrome && window.chrome.storage) {
                window.chrome.storage.local.set({ "isTimerOn": false }, function () {});
            }
            var self = this;
            // Validation step
            if (_.isUndefined(this.activity.project_id)) {
                // TODO Might be better if we find a way to style select2 fields
                this.$('.pt_edit_alert').show(0).delay(5000).hide(0);
                return;
            }
            this.activity.unit_amount = this.activity.unit_amount >= 0 ?  this.activity.unit_amount : 0;

            var stored_activity = _.findWhere(this.getParent().data.account_analytic_lines,  {id:this.activity.id});

            // Create operations
            if (_.isUndefined(stored_activity)) {
                this.getParent().data.account_analytic_lines.unshift({
                    id : MODULE_KEY + self.getParent().sanitize_xml_id(self.getParent().user + self.getParent().data.original_timestamp + "_aal_" + self.getParent().data.next_aal_id)
                });
                stored_activity = this.getParent().data.account_analytic_lines[0];
                stored_activity.date = this.activity.date;
                self.getParent().data.next_aal_id++;
            }

            // Update operations
            _.extend(stored_activity , self.activity);
            stored_activity.write_date = time_module.datetime_to_str(new Date());
            stored_activity.to_sync = true;
            // Normalization of false values.
            stored_activity.task_id = stored_activity.task_id ? stored_activity.task_id : false;

            this.getParent().data.account_analytic_lines.sort(function(a,b) {
                return time_module.str_to_datetime(b.write_date) - time_module.str_to_datetime(a.write_date);
            });
            this.getParent().save_user_data();
            core.bus.trigger('change_screen', {
                id : 'activities',
            });

            core.bus.trigger('sync', {
                callback : function() {
                    core.bus.trigger('after_sync');
                },
            });

        },
        discard_changes: function() {
            this.clear_timer();
            if(window.chrome && window.chrome.storage) {
                window.chrome.storage.local.set({ "isTimerOn": false }, function () {});
            }
            core.bus.trigger('change_screen', {
                id : 'activities',
            });
        },
        reset_activity: function() {
            var self = this;
            this.activity = {
                project_id: undefined,
                task_id: false,
                desc:" ",
                unit_amount: 0,
                date: self.today,
            };

            if (!_.isUndefined(self.getParent().data.settings.default_project_id)) {
                this.activity.project_id = self.getParent().data.settings.default_project_id;
            }
        },

        delete_activity: function() {
            var self = this;
            this.clear_timer();
            if(window.chrome && window.chrome.storage) {
                window.chrome.storage.local.set({ "isTimerOn": false }, function () {});
            }
            if (!_.isUndefined(this.activity.id)) {
                var aal_to_remove = _.findWhere(this.getParent().data.account_analytic_lines, {id : this.activity.id});
                aal_to_remove.to_remove = true;
                self.getParent().save_user_data();
            }
            this.reset_activity();
            core.bus.trigger('change_screen', {
                id : 'activities',
            });
        },
        clear_timer: function() {
            this.getParent().activities_screen.clear_timer();
        },
    });

    var Stats_screen = BasicScreenWidget.extend({
        template: "stats_screen",
        init: function(parent) {
            var self = this;
            this._super(parent);
            this.projects_stats = [];
            this.start_of_week = moment(new Date()).startOf('week');

            self.chart = null;
            self.chartConfig = {
                type: 'bar',
                options: {
                    layout: {
                        padding: {left: 15, right: 15}
                    },
                    legend: {
                        display: false,
                    },
                    maintainAspectRatio: false,
                    scales: {
                        yAxes: [{
                            display: true,
                            type: 'linear',
                            ticks: {
                                beginAtZero: true,
                                callback: this.unit_amount_to_hours_minutes.bind(this),
                            },
                        }],
                    },
                    tooltips: {
                        enabled: false,
                    }
                }
            };

            _.extend(self.events,
                {
                    "click .pt_next_week" : "go_to_next_week",
                    "click .pt_prev_week" : "go_to_previous_week",
                }
            );
        },
        attach: function(el, options) {
            if (options) {
                this.set_week(options.date);
            } else {
                this.set_week();
            }
            this.get_project_stats();
            this._super.apply(this, arguments);
            this.drawStats();
        },
        set_week: function(date) {
            var self = this;
            self.week = [];
            if (!date) {
                self.start_of_week = moment(new Date()).startOf('week');
            } else {
                self.start_of_week = moment(date).startOf('week');
            }
            for (var i = 0 ; i < 7; i++) {
                self.week.unshift(time_module.date_to_str(moment(self.start_of_week).add(i, 'days').toDate()));
            }
        },
        drawStats: function() {
            var self = this;
            self.weekTotal = 0;
            //
            // Args : Week : An array containing date objects. Ideally 7.
            // Returns :  an object with keys 'labels' and 'datasets'.
            // Side effect: sets the value of weekTotal used in the widget.

            function prepareData(week) {
                var labels = [];
                var dataset = {
                    label: "Working time per week",
                    data: [],
                    backgroundColor: "#875A7B",
                };
                for (var i = 0; i < week.length ; i++) {
                    var timeWorked = 0;
                    var dayName = moment(time_module.str_to_date(week[i])).format("ddd");
                    var activitiesPerDay = _.where(self.getParent().data.account_analytic_lines, {date : week[i]});
                    _.each(activitiesPerDay, function(activity) {
                        timeWorked += parseFloat(activity.unit_amount);
                    });
                    dataset.data.unshift(timeWorked);
                    labels.unshift(dayName);
                    self.weekTotal += timeWorked;
                }
                return {
                    labels: labels,
                    datasets: [dataset],
                };
            }

            if (this.chart) {
                this.chart.destroy();
            }

            this.$('div .o_canvas_container').css({position: 'relative'});
            var ctx = this.$('canvas').get(0).getContext('2d');
            this.chartConfig.data = prepareData(this.week);
            this.chart = new Chart(ctx, this.chartConfig);

            self.$('.pt_total_time').text(self.unit_amount_to_hours_minutes(self.weekTotal));
        },
        get_project_stats: function() {
            var self = this;
            self.projects_stats = [];

            _.each(self.getParent().data.projects, function(project) {
                var project_stat = {
                    name : self.get_project_name(project.id),
                    total_time : 0,
                };
                _.each(self.week, function(day) {
                    var activities = _.where(self.getParent().data.account_analytic_lines , {project_id : project.id, date : day});
                    _.each(activities, function(activity) {
                        project_stat.total_time += parseFloat(activity.unit_amount);
                    });
                });
                if (project_stat.total_time > 0) {
                    self.projects_stats.push(project_stat);
                }
            });
            self.projects_stats.sort(function(a,b) {
                return b.total_time - a.total_time;
            });
        },
        go_to_next_week: function() {
            var date = this.start_of_week.add(7, 'days').toDate();
            core.bus.trigger('change_screen', {
                id : 'stats',
                options : {
                    date : date,
                },
            });
        },
        go_to_previous_week: function() {
            var date = this.start_of_week.subtract(7, 'days').toDate();
            core.bus.trigger('change_screen', {
                id : 'stats',
                options : {
                    date : date,
                },
            });
        },
    });

    var Sync_screen = BasicScreenWidget.extend({
        template: "sync_screen",
        init: function(parent) {
            var self = this;
            this._super(parent);
            _.extend(self.events,
                {
                    "click .pt_sync_btn" : "sync_now",
                    "click .pt_send_login" : "send_login",
                    "click .pt_send_logout" : "send_logout",
                    "click .pt_odoo_login_link" : "select_odoo_login",
                    "click .pt_premise_login_link" : "show_premise_login_url_screen",
                    "click .pt_create_account_link" : "show_account_creation_screen",
                    "click .pt_reset_app" : "reset_app",
                    "click .pt_keep_data" : "on_keep_data",
                    "click .pt_discard_data" : "on_discard_data",
                }
            );
            this.session = session;
            core.bus.on('go_to_sign_in', this, this.show_login_screen);
        },
        select_odoo_login: function() {
            var self = this;
            self.server = 'https://www.odoo.com';
            session.origin = self.server;
            session.setup(self.server, {use_cors : true});
            var always = function() {
                if (session.uid) {
                    self.show_db_selector_screen();
                }
                else {
                    self.show_login_screen();
                }
            }
            session.session_reload().then(always).guardedCatch(always);
        },
        show_login_screen: function() {
            this.odoo_login_screen = new Odoo_login_screen(this);
            this.$('div.pt_sync_screen').empty();
            this.odoo_login_screen.appendTo(this.$('div.pt_sync_screen'));
        },
        show_db_selector_screen: function() {
            this.db_selector_screen = new Db_selector_screen(this);
            this.$('div.pt_sync_screen').empty();
            this.db_selector_screen.appendTo(this.$('div.pt_sync_screen'));
        },
        show_account_creation_screen: function() {
            this.account_creation_screen = new Account_creation_screen(this);
            this.$('div.pt_sync_screen').empty();
            this.account_creation_screen.appendTo(this.$('div.pt_sync_screen'));
        },
        show_premise_login_url_screen: function() {
            this.premise_login_url_screen = new Premise_login_url_screen(this);
            this.$('div.pt_sync_screen').empty();
            this.premise_login_url_screen.appendTo(this.$('div.pt_sync_screen'));
        },
        show_premise_login_form_screen: function() {
            this.premise_login_form_screen = new Premise_login_form_screen(this);
            this.$('div.pt_sync_screen').empty();
            this.premise_login_form_screen.appendTo(this.$('div.pt_sync_screen'));
        },
        show_successful_login_screen: function() {
            this.successful_login_screen = new Successful_login_screen(this);
            this.$('div.pt_sync_screen').empty();
            this.successful_login_screen.appendTo(this.$('div.pt_sync_screen'));
        },
        send_login: function() {
            var self = this;
            var login = this.$(".pt_login").val();
            var password = this.$(".pt_password").val();
            var db_name = this.$(".pt_db_name").val();
            var server_address = this.$(".pt_server_address").val();
            var protocol = this.$(".pt_protocol").val();
            session.origin = protocol + server_address;
            session.setup(protocol + server_address, {use_cors : true});
            session._session_authenticate(db_name, login, password).then(function() {
                local_storage.setItem('pt_current_server', session.origin);
                self.renderElement();
                self.getParent().get_user_data(session.username, session.server);
            }).guardedCatch(function(error) {
                if (error && error.code == -32098) {
                    alert("Could not reach the server. Please check that you have an internet connection, that the server address you entered is valid, and that the server is online.");
                }
                else {
                    alert("Could not login. Please check that the information you entered is correct.");
                }
            });
        },
        send_logout: function() {
            var self = this;
            session.session_logout().then(function() {
                session.uid = undefined;
                session.username = undefined;
                local_storage.removeItem('pt_current_user');
                local_storage.removeItem('pt_current_server');
                self.getParent().get_user_data("$no_user$", "$no_server$");
                self.renderElement();
                console.log("Logout Successful");
            });
        },
        on_successful_login: function() {
            var self = this;
            session.rpc('/web/session/modules').then(function(response){
                if (response.length > 0 && _.contains(response, 'project_timesheet_synchro')) {
                    self.getParent().syncable = true;
                    self.$('.pt_keep_guest_data').modal();
                } else {
                    self.getParent().syncable = false;
                    session.rpc('/jsonrpc',  { method : 'server_version' , service : 'db', args : []}).then(function(result) {
                        if (result && result.endsWith('e')) {
                            alert("The server does not support timesheet synchronization. You should contact your administrator in order to install the module \"Synchronization with the external timesheet application\"");
                        } else if (result) {
                            alert("Timesheet Synchronization is available in Odoo Enterprise Edition. You should consider upgrading your Odoo version if you would like to use it.");
                        } else {
                            alert("The server does not support timesheet synchronization. It requires Odoo Enterprise Edition version 9 or newer.");
                        }
                    })
                    self.on_keep_data();
                }
            });
        },
        on_keep_data: function() {
            this.getParent().get_user_data(session.username, session.server, true);
            core.bus.trigger('change_screen', {
                id : 'activities',
            });
            core.bus.trigger('sync', {
                callback : function(){
                    core.bus.trigger('after_sync');
                }
            });
        },
        on_discard_data: function() {
            this.getParent().get_user_data(session.username, session.server);
            core.bus.trigger('change_screen', {
                id : 'activities',
            });
            core.bus.trigger('sync', {
                callback : function(){
                    core.bus.trigger('after_sync');
                }
            });
        },
        sync_now: function() {
            var self = this;
            core.bus.trigger('change_screen', {
                id : 'activities',
            });
            core.bus.trigger('sync', {
                callback : function(){
                    core.bus.trigger('after_sync');
                }
            });
        },
        reset_app: function() {
            core.bus.trigger('reset', {});
        },
    });

    var Odoo_login_screen = Widget.extend({
        template : "odoo_saas_login",
        events: {
            "click .pt_send_odoo_login" : "send_odoo_login",
        },
        send_odoo_login: function() {
            var self = this;
            var login = this.$(".pt_odoo_login").val();
            var password = this.$(".pt_odoo_password").val();
            var db_name = 'openerp';
            var server_address = 'https://www.odoo.com';
            session.origin = server_address;
            session.setup(server_address, {use_cors : true});
            session._session_authenticate(db_name, login, password).then(function() {
                self.getParent().show_db_selector_screen();
            }).guardedCatch(function(error) {
                if (error && error.code == -32098) {
                    alert("Could not reach the server. Please check that you have an internet connection, that the server address you entered is valid, and that the server is online.");
                }
                else {
                    alert("Could not login. Please check that the information you entered is correct.");
                }
            });
        },
    });

    var Db_selector_screen = Widget.extend({
        template : "db_selector",
        events:{
            "click .pt_db_select": "db_selected",
        },
        willStart: function() {
            var self = this;
            return this._rpc({
                    model: 'openerp.enterprise.database',
                    method: 'get_instances',
                })
                .then(function(res) {
                    self.instances = {};
                    _.each(res, function(item) {
                        if(item.url){
                            self.instances[item.url] = item;
                        }
                    });
                }).guardedCatch(function(res) {
                    alert('Something went wrong.');
                });
        },

        db_selected: function(event) {
            var self = this;
            $('.pt_nav_sync a').addClass('pt_sync_in_progress');
            var url = event.target.dataset.url;

            this._rpc({
                    model: 'auth.oauth2.token',
                    method: 'get_token',
                    args: [{client_id: self.instances[url].uuid, scope: "userinfo"}],
                })
                .then(function(res) {
                    var state =  JSON.stringify({
                        'd': self.instances[url].db_name,
                        'p':1, // 1 is the code to use Odoo as provider
                    });
                    var token = res.access_token;
                    $.ajax({
                        url : url.concat(
                            '/auth_oauth/signin',
                            '?access_token=' + token,
                            '&scope=userinfo',
                            '&state=' + state,
                            '&expires_in=3600',
                            '&token_type=Bearer'
                        ),
                    }).then(function(response){
                        self.server = url;
                        session.origin = self.server;
                        session.setup(self.server, {use_cors : true});
                        var always = function() {
                            if (session.uid) {
                                self.getParent().on_successful_login();
                                local_storage.setItem('pt_current_server', session.origin);
                                local_storage.setItem('pt_current_user', session.username);
                            }
                            else {
                                alert('Odoo login failed');
                            }
                        }
                        session.session_reload().then(always).guardedCatch(always);
                    }).guardedCatch(function(res) {
                        session.origin = url;
                        session.setup(url, {use_cors : true});
                        self.getParent().db_list = [url.substring(8, url.length -9)]
                        self.getParent().show_premise_login_form_screen();
                    });
                });
        },
    });

    var Premise_login_url_screen = Widget.extend({
        template : "premise_login_url_screen",
        events : {
            "click .pt_validate_url" : "validate_url",
        },
        validate_url: function() {
            var self = this;
            var server_address = this.$(".pt_premise_url").val();
            var protocol = this.$(".pt_premise_protocol").val();
            if (server_address === "odoo.com" || server_address === "www.odoo.com") {
                server_address = "www.odoo.com";
                self.protocol = "https://";
            }
            session.origin = protocol + server_address;
            session.setup(protocol + server_address, {use_cors : true});

            if (server_address === "www.odoo.com") {
                self.getParent().db_list = ["openerp"];
                self.getParent().show_premise_login_form_screen();
                return;
            } else if (this.$(".pt_premise_db") && this.$(".pt_premise_db").val()) {
                self.getParent().db_list = [this.$(".pt_premise_db").val()];
                self.getParent().show_premise_login_form_screen();
                return;
            }

            session.rpc('/web/database/list').then(function(result) {
                self.getParent().db_list = result;
                self.getParent().show_premise_login_form_screen();
            }).guardedCatch(function(error) {
                if (error && error.code == -32098) {
                    alert("Could not reach the server. Please check that you have an internet connection, that the server address you entered is valid, and that the server is online.");
                } else if (self.url) {
                    alert("Could not find server. Please check that the url you entered is correct.");
                } else {
                    // Re render the form with a field allowing to enter a database name. Useful for servers that don't allow listing databases.
                    self.use_https = (protocol === 'https://');
                    self.url = server_address;
                    self.show_db_field = true;
                    self.renderElement();
                }
            });
        },
    });

    var Premise_login_form_screen = Widget.extend({
        template: "premise_login_form_screen",
        events : {
            "click .pt_send_premise_login" : "send_premise_login",
            "click .show_password": "show_password",
        },
        send_premise_login: function() {
            var self = this;
            var login = this.$(".pt_premise_login").val();
            var password = this.$(".pt_premise_password").val();
            var db_name = this.$(".pt_premise_db").val();
            var server_address = this.$(".pt_premise_url").val();
            var protocol = this.$(".pt_premise_protocol").val();
            session._session_authenticate(db_name, login, password).then(function() {
                local_storage.setItem('pt_current_server', session.origin);
                self.getParent().on_successful_login();
            }).guardedCatch(function(error) {
                if (error && error.code == -32098) {
                    alert("Could not reach the server. Please check that you have an internet connection, that the server address and database name you entered is valid, and that the server is online.");
                } else {
                    alert("Could not login. Please check that the information you entered is correct.");
                }
            });
        },
        show_password: function(ev) {
            var type = this.$('.pt_premise_password').attr('type') === 'password' ? 'text': 'password';
            this.$('.pt_premise_password').attr('type', type);
            $(ev.target).toggleClass('fa-eye-slash');
        },
    });

    // Account creation system commented
    var Account_creation_screen = Widget.extend({
        template : "account_creation",
        events:{
            "click .pt_sign_in_link": "go_to_sign_in",
        },
        init: function(parent) {
            this._super(parent);
            this.show_iframe = true;
            self.odoo_is_online = false;
            window.addEventListener("message", this.received_message, false);
            core.bus.on('db_created', this, this.on_db_creation_success);
        },
        /**
         * We perform a quick check (before rendering the widget) to see if Odoo is reachable. If not, we don't display an iframe with an ugly 404 message.
         * ALL the parameters of the ajax requests ARE required for it to work properly in as many situations as possible.
        */
        willStart: function() {
            var self = this;
            return new Promise(function (resolve, reject) {
                $.ajax({
                    url: 'https://www.odoo.com/fr_FR/trial',
                    type: 'HEAD',
                    cache: false,
                    timeout: 5000,
                    error: function() {
                        self.odoo_is_online = false;
                        resolve();
                    },
                    success: function() {
                        self.odoo_is_online = true;
                        resolve();
                    },
                });
            });
        },
        received_message: function(event) {
            if (event.origin === 'https://www.odoo.com' && event.data === 'success') {
                core.bus.trigger('db_created'); // We use the bus as we want to have access to the widget to re-render it, and here 'this' refers to 'window'.
            }
        },
        on_db_creation_success: function(event) {
            this.show_iframe = false;
            this.show_success_message = true;
            this.renderElement();
        },
        go_to_sign_in: function() {
            core.bus.trigger('go_to_sign_in');
        },
    });

    var Successful_login_screen = Widget.extend({
        template : "successful_login_screen",
    });

    return ProjectTimesheet;
});
