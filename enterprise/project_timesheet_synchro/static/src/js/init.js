$(function(){
  	odoo.define('project_timesheet.project_timesheet', function(require){
	    var TimesheetApp = require('project_timeshee.ui');
	    var app = new TimesheetApp();
	    app.appendTo("body");
	});
});