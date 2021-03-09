# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json

from odoo import http, _
from odoo.http import request
from odoo.tools.misc import xlwt


class WebCohort(http.Controller):

    @http.route('/web/cohort/export', type='http', auth='user')
    def export_xls(self, data, token):
        result = json.loads(data)

        workbook = xlwt.Workbook()
        worksheet = workbook.add_sheet(result['title'])
        xlwt.add_palette_colour('gray_lighter', 0x21)
        workbook.set_colour_RGB(0x21, 224, 224, 224)
        style_highlight = xlwt.easyxf('font: bold on; pattern: pattern solid, fore_colour gray_lighter; align: horiz centre;')
        style_normal = xlwt.easyxf('align: horiz centre;')
        row = 0

        def write_data(report, row, col):
            # Headers
            columns_length = len(result[report]['rows'][0]['columns'])
            if result['timeline'] == 'backward':
                header_sign = ''
                col_range = range(-(columns_length - 1), 1)
            else:
                header_sign = '+'
                col_range = range(columns_length)

            worksheet.write_merge(row, row, col + 2, columns_length + 1,
                _('%s - By %s') % (result['date_stop_string'], result['interval_string']), style_highlight)
            row += 1
            worksheet.write(row, col, result['date_start_string'], style_highlight)
            col += 1
            worksheet.write(row, col, result['measure_string'], style_highlight)
            col += 1
            for n in col_range:
                worksheet.write(row, col, '%s%s' % (header_sign, n), style_highlight)
                col += 1

            # Rows
            row += 1
            for res in result[report]['rows']:
                col = 0
                worksheet.write(row, col, res['date'], style_normal)
                col += 1
                worksheet.write(row, col, res['value'], style_normal)
                col += 1
                for i in res['columns']:
                    worksheet.write(row, col, i['percentage'] == '-' and i['percentage'] or str(i['percentage']) + '%', style_normal)
                    col += 1
                row += 1

            # Total
            col = 0
            worksheet.write(row, col, _('Average'), style_highlight)
            col += 1
            worksheet.write(row, col, '%.1f' % result[report]['avg']['avg_value'], style_highlight)
            col += 1
            total = result[report]['avg']['columns_avg']
            for n in range(columns_length):
                if total[str(n)]['count']:
                    worksheet.write(row, col, '%.1f' % float(total[str(n)]['percentage'] / total[str(n)]['count']) + '%', style_highlight)
                else:
                    worksheet.write(row, col, '-', style_highlight)
                col += 1

            return row

        report_length = len(result['report']['rows'])
        comparison_report = result.get('comparisonReport', False)
        if comparison_report:
            comparison_report_length = len(comparison_report['rows'])

        if comparison_report:
            if report_length:
                row = write_data('report', row, 0)
                if comparison_report_length:
                    write_data('comparisonReport', row + 2, 0)
            elif comparison_report_length:
                write_data('comparisonReport', row, 0)
        else:
            row = write_data('report', row, 0)

        response = request.make_response(
            None,
            headers=[('Content-Type', 'application/vnd.ms-excel'), ('Content-Disposition', 'attachment; filename=%sCohort.xls' % result['title'])],
            cookies={'fileToken': token}
        )
        workbook.save(response.stream)
        return response
