from math import copysign

from odoo import _
from odoo.tools.float_utils import float_is_zero
from .abstract import AbstractBuilder


class ComparisonBuilder(AbstractBuilder):
    # OVERRIDES
    def _get_params(self, period_ids: list, options: dict, line_id: str = None) -> dict:
        chart_ids = self.env['consolidation.chart'].search([('period_ids', 'in', period_ids)]).ids
        cols_amount = len(period_ids)
        include_percentage = cols_amount == 2
        params = super()._get_params(period_ids, options, line_id)
        params.update({
            'chart_ids': chart_ids,
            'cols_amount': cols_amount,
            'include_percentage': include_percentage,
        })
        return params

    def _output_will_be_empty(self, period_ids: list, options: dict, line_id: str = None) -> bool:
        return len(period_ids) == 0

    def _compute_account_totals(self, account_id: int, **kwargs) -> list:
        domain = [
            ('account_id', '=', account_id),
            ('period_id', 'in', kwargs.get('period_ids', []))
        ]
        groupby = ('period_id',)
        total_lines = self.env['consolidation.journal.line'].read_group(domain, ('total:sum(amount)',), groupby)
        if len(total_lines) == 0:
            return []
        totals = []
        total_dict = {line['period_id'][0]: line['total'] for line in total_lines}
        # Need to keep the order of periods as nothing in DB can order them
        for period_id in kwargs.get('period_ids', []):
            totals.append(total_dict[period_id])
        return totals

    def _get_default_line_totals(self, options: dict, **kwargs) -> list:
        return kwargs.get('cols_amount', len(kwargs.get('period_ids', []))) * [0.0]

    def _format_account_line(self, account, level: int, totals: list, options: dict, **kwargs) -> dict:
        account_line = super()._format_account_line(account, level, totals, options, **kwargs)
        if kwargs.get('include_percentage', False):
            account_line['columns'].append(self._build_percentage_column(*totals))
        return account_line

    def _build_section_line(self, section, level: int, options: dict, **kwargs):
        section_totals, section_lines = super()._build_section_line(section, level, options, **kwargs)
        if kwargs.get('include_percentage', False):
            section_lines[0]['columns'].append(self._build_percentage_column(*section_totals))
        return section_totals, section_lines

    def _build_total_line(self, totals: list, options: dict, **kwargs) -> dict:
        total_line = super()._build_total_line(totals, options, **kwargs)
        if kwargs.get('include_percentage', False):
            total_line['columns'].append(self._build_percentage_column(*totals))
        return total_line

    @staticmethod
    def _build_percentage_column(orig_value: float, now_value: float) -> dict:
        """
        Build the percentage column based on the two given values
        :param orig_value: the original value
        :type orig_value: float
        :param now_value: the value of now
        :type now_value: float
        :return: a formatted dict containing the percentage increase between the two given values and ready to be added
        as a column inside a report line
        :rtype: dict
        """
        if not float_is_zero(orig_value, 6):
            res = round((now_value - orig_value) / orig_value * 100, 1)
            classes = ['number']

            if float_is_zero(res, precision_rounding=0.1):
                val = 0.0
            elif (res > 0) == (orig_value > 0):
                classes.append('color-green')
                val = copysign(res, 1)
            else:
                classes.append('color-red')
                val = copysign(res, -1)
            return {
                'name': ('%s%%' % val),
                'no_format_name': val,
                'class': ' '.join(classes)
            }
        # res > 0
        # orig > 0 :: GREEN
        # orig < 0 :: RED
        # res < 0
        # orig < 0 :: GREEN
        # orig > 0 :: RED

        else:
            return {'name': _('n/a')}
