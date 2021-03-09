# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime
import base64
from lxml import etree

from odoo import api, fields, models, _

from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round

EMPLOYER_ONSS = 0.2714

CODES_281_10 = [
    'A1020', 'F2008', 'F2009', 'F2018', 'F2112', 'F2029', 'F2019', 'F2020', 'F2021', 'F2022',
    'F2023', 'F2024', 'F2026', 'F2027', 'F10_2031', 'F10_2034', 'F10_2035', 'F10_2036',
    'F10_2041', 'F10_2042', 'F10_2045', 'F10_2055', 'F10_2056', 'F10_2058', 'F10_2059', 'F10_2060',
    'F10_2061', 'F10_2062', 'F10_2063', 'F10_2064', 'F10_2065', 'F10_2066', 'F10_2067', 'F10_2068',
    'F10_2069', 'F10_2070', 'F10_2071', 'F10_2072', 'F10_2073', 'F10_2040', 'F10_2037', 'F10_2039',
    'F10_2074', 'F10_2075', 'F10_2076', 'F10_2077', 'F10_2078', 'F10_2079', 'F10_2080', 'F10_2081',
    'F10_2082', 'F10_2083', 'F10_2084', 'F10_2085', 'F10_2086', 'F10_2087', 'F10_2088', 'F10_2090',
    'F10_2093', 'F10_2095', 'F10_2113', 'F10_2115', 'F10_2116', 'F10_2117', 'F10_2118', 'F10_2119',
    'F10_2120', 'F10_2121', 'F10_2122', 'F10_2123', 'F10_2124', 'F10_2125', 'F10_2126', 'F10_2127',
    'F10_2097', 'F10_2099', 'F10_2100', 'F10_2101', 'F10_2102', 'F10_2109', 'F10_2110', 'F10_2111',
    'F10_2128', 'F10_2129', 'F10_2130', 'F10_2131', 'F10_2132', 'F10_2133', 'F10_2165', 'F10_2166',
    'F10_2134', 'F10_2135', 'F10_2136', 'F10_2137', 'F10_2138', 'F10_2141', 'F10_2142', 'F10_2143',
    'F10_2167', 'F10_2168', 'F10_2169', 'F10_2170', 'F10_2176', 'F10_2177', 'F10_2178', 'F10_2179',
]

STRUCT_BLACKLIST_281_10 = [
    'l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_departure_n1_holidays',
    'l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_departure_n_holidays',
    'l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_termination_fees'
]


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    spouse_fiscal_status = fields.Selection([
        ('without income', 'Without Income'),
        ('with income', 'With Income')
    ], string='Tax status for spouse', groups="hr.group_hr_user")
    disabled = fields.Boolean(string="Disabled", help="If the employee is declared disabled by law", groups="hr.group_hr_user")
    disabled_spouse_bool = fields.Boolean(string='Disabled Spouse', help='if recipient spouse is declared disabled by law', groups="hr.group_hr_user")
    disabled_children_bool = fields.Boolean(string='Disabled Children', help='if recipient children is/are declared disabled by law', groups="hr.group_hr_user")
    resident_bool = fields.Boolean(string='Nonresident', help='if recipient lives in a foreign country', groups="hr.group_hr_user")
    disabled_children_number = fields.Integer('Number of disabled children', groups="hr.group_hr_user")
    dependent_children = fields.Integer(compute='_compute_dependent_children', string='Considered number of dependent children', groups="hr.group_hr_user")
    other_dependent_people = fields.Boolean(string="Other Dependent People", help="If other people are dependent on the employee", groups="hr.group_hr_user")
    other_senior_dependent = fields.Integer('# seniors (>=65)', help="Number of seniors dependent on the employee, including the disabled ones", groups="hr.group_hr_user")
    other_disabled_senior_dependent = fields.Integer('# disabled seniors (>=65)', groups="hr.group_hr_user")
    other_juniors_dependent = fields.Integer('# people (<65)', help="Number of juniors dependent on the employee, including the disabled ones", groups="hr.group_hr_user")
    other_disabled_juniors_dependent = fields.Integer('# disabled people (<65)', groups="hr.group_hr_user")
    dependent_seniors = fields.Integer(compute='_compute_dependent_people', string="Considered number of dependent seniors", groups="hr.group_hr_user")
    dependent_juniors = fields.Integer(compute='_compute_dependent_people', string="Considered number of dependent juniors", groups="hr.group_hr_user")
    spouse_net_revenue = fields.Float(string="Spouse Net Revenue", help="Own professional income, other than pensions, annuities or similar income", groups="hr.group_hr_user")
    spouse_other_net_revenue = fields.Float(string="Spouse Other Net Revenue",
        help='Own professional income which is exclusively composed of pensions, annuities or similar income', groups="hr.group_hr_user")

    start_notice_period = fields.Date("Start notice period", groups="hr.group_hr_user", copy=False, tracking=True)
    end_notice_period = fields.Date("End notice period", groups="hr.group_hr_user", copy=False, tracking=True)
    first_contract_in_company = fields.Date("First contract in company", groups="hr.group_hr_user", copy=False)

    language_code = fields.Selection([
        ('dutch', 'Dutch'),
        ('french', 'French'),
        ('german', 'German'),
        ], default='french', string='Language', groups="hr.group_hr_user")
    nif_country_code = fields.Integer(string="NIF Country Code", default=0, groups="hr.group_hr_user", help="Fiscal Identification Number")
    has_bicycle = fields.Boolean(string="Bicycle to work", default=False, groups="hr.group_hr_user",
        help="Use a bicycle as a transport mode to go to work")

    @api.constrains('spouse_fiscal_status', 'spouse_net_revenue', 'spouse_other_net_revenue')
    def _check_spouse_revenue(self):
        for employee in self:
            if employee.spouse_fiscal_status == 'with income' and not employee.spouse_net_revenue and not employee.spouse_other_net_revenue:
                raise ValidationError(_("The revenue for the spouse can't be equal to zero is the fiscal status is 'With Income'."))

    @api.onchange('spouse_fiscal_status')
    def _onchange_spouse_fiscal_status(self):
        self.spouse_net_revenue = 0.0
        self.spouse_other_net_revenue = 0.0

    @api.onchange('disabled_children_bool')
    def _onchange_disabled_children_bool(self):
        self.disabled_children_number = 0

    @api.onchange('other_dependent_people')
    def _onchange_other_dependent_people(self):
        self.other_senior_dependent = 0.0
        self.other_disabled_senior_dependent = 0.0
        self.other_juniors_dependent = 0.0
        self.other_disabled_juniors_dependent = 0.0

    @api.depends('disabled_children_bool', 'disabled_children_number', 'children')
    def _compute_dependent_children(self):
        for employee in self:
            if employee.disabled_children_bool:
                employee.dependent_children = employee.children + employee.disabled_children_number
            else:
                employee.dependent_children = employee.children

    @api.depends('other_dependent_people', 'other_senior_dependent',
        'other_disabled_senior_dependent', 'other_juniors_dependent', 'other_disabled_juniors_dependent')
    def _compute_dependent_people(self):
        for employee in self:
            employee.dependent_seniors = employee.other_senior_dependent + employee.other_disabled_senior_dependent
            employee.dependent_juniors = employee.other_juniors_dependent + employee.other_disabled_juniors_dependent

    def _generate_281_10_form(self, basic_info, file_types=['xml', 'pdf']):
        """
            This method creates the 281.10 sheet.
            1. It calls the method that checks all the necessary information.
            2. It calls the method that creates the dictionary.
            3. It will create the file names.
            4. It calls the method to create the XML file.
            5. It calls the method to create the PDF file.
        """
        self._check_valid_281_10_configuration()
        employees_data = self._get_employee_281_10_values(basic_info)

        for employee in self:
            employee_data = employees_data[employee.id]
            attachments = []

            if 'xml' in file_types:
                employee_data.update({'F2019': employee._get_marital_status('xml')})
                attachments.append(employee._generate_281_10_form_xml(employee_data))

            if 'pdf' in file_types:
                employee_data.update({'F2019': employee._get_marital_status('pdf')})
                attachments.append(employee._generate_281_10_form_pdf(employee_data))

            employee.message_post(
                body=_("The 281.10 sheet has been generated"),
                attachments=attachments)

    def _check_valid_281_10_configuration(self):
        if not all(emp.company_id and emp.company_id.street and emp.company_id.zip and emp.company_id.city and emp.company_id.phone and emp.company_id.vat for emp in self):
            raise UserError(_("The company is not correctly configured on your employees. Please be sure that the following pieces of information are set: street, zip, city, phone and vat"))

        if not all(emp.address_home_id and emp.address_home_id.street and emp.address_home_id.zip and emp.address_home_id.city for emp in self):
            raise UserError(_('Some employee home address is missing or not completed!'))

        if not all(emp.contract_ids and emp.contract_id for emp in self):
            raise UserError(_('Some employee has no contract.'))

        if not all(emp.identification_id for emp in self):
            raise UserError(_('Some employee has no identification id.'))

        if not all(emp.language_code for emp in self):
            raise UserError(_('Some employee has no language.'))

    def _get_employee_281_10_values(self, basic_info):
        result = {}
        year = basic_info['year']
        for employee in self:
            data_dict = dict.fromkeys(CODES_281_10, 0.0)
            if employee.contract_id.date_end and employee.contract_id.date_end.year == datetime.datetime.now().year:
                F10_2056 = employee.contract_id.date_end.strftime('%d%m%Y')
            else:
                F10_2056 = '00000000'

            payslips = employee.env['hr.payslip'].search([
                ('date_to', '<=', datetime.date(int(year), 12, 31)),
                ('date_to', '>=', datetime.date(int(year), 1, 1)),
                ('state', 'in', ['done', 'paid']),
                ('employee_id', '=', employee.id),
                ('struct_id', 'not in', [employee.env.ref(xmlid).id for xmlid in STRUCT_BLACKLIST_281_10]),
            ])

            if employee.language_code == "dutch":
                language_code = '1'
            elif employee.language_code == "french":
                language_code = '2'
            else:
                language_code = '3'

            data_dict.update({
                'bce_number': employee.company_id.vat.replace('BE', ''),
                'company_name': employee.company_id.name,
                'company_address': employee.company_id.street + ' ' + (employee.company_id.street2 or ''),
                'company_zip': employee.company_id.zip,
                'company_city': employee.company_id.city,
                'company_phone': employee.company_id.phone,
                'contact_person_name': employee.env.user.name,
                'contact_person_mail': employee.env.user.email,
                'language_code': language_code,
                'A1020': 1,
                'F2008': '28110', # Sheet number
                'employee_name': employee.name,
                'employee_address': employee.address_home_id.street + ' ' + (employee.address_home_id.street2 or ''),
                'employee_zip': employee.address_home_id.zip,
                'employee_city': employee.address_home_id.city,
                'F2018': employee.nif_country_code,
                'F2020': employee._get_281_10_family_situation(),
                'F2021': employee.children + employee.disabled_children_number,
                'F2022': employee._get_dependent_people(),
                'F2023': employee._get_divers_status(),
                'F2024': 'H' if employee.disabled_spouse_bool else '',
                'F2026': 'H' if employee.disabled else '',
                'F2027': language_code,
                'F2112': employee.nif_country_code != '0' and employee.address_home_id.zip or '0',
                'F10_2037': 1,
                'F10_2055': employee.contract_id.date_start.strftime('%d%m%Y') if employee.contract_id.date_start.year == datetime.datetime.now().year else '00000000',
                'F10_2056': F10_2056,
                'F10_2058': employee.has_bicycle and employee.km_home_work or 0.0,
                'F10_2060': sum(payslip._get_salary_line_total('NET') for payslip in payslips),
                'F10_2063': employee._get_holiday_remuneration(year),
                'F10_2074': sum(payslip._get_salary_line_total('P.P') for payslip in payslips),
                'F10_2075': sum(abs(payslip._get_salary_line_total('M.ONSS')) for payslip in payslips),
                'F10_2076': payslips._get_atn_remuneration(),
                'F10_2078': sum(payslip._get_salary_line_total('REP.FEES') for payslip in payslips),
                'F10_2086': sum(payslip.contract_id.public_transport_reimbursed_amount for payslip in payslips if payslip.contract_id.transport_mode_public),
                'F10_2088': sum(payslip._get_salary_line_total('Tr.E') for payslip in payslips),
                'F10_2099': 9 if employee.contract_id.transport_mode_car else 7, # 9 = Vehicle // 7 = Computer,
                'F10_2100': '200-00', # Joint committee number,
                'F10_2109': str(employee.identification_id),
                'F10_2115': sum(payslip._get_salary_line_total('EmpBonus.1') for payslip in payslips),
            })

            data_dict.update({
                'F10_2099Bis': 'Voiture' if data_dict['F10_2099'] else 'Computer',
                'F10_2077': data_dict['F10_2086'] + data_dict['F10_2087'] + data_dict['F10_2088'] + data_dict['F10_2176'], # F10_2087 and F10_2176 not defined (= always 0)
                'F10_2062': data_dict['F10_2060'] + data_dict['F10_2069'] + data_dict['F10_2076'] + data_dict['F10_2082'] + data_dict['F10_2083'], # F10_2069, F10_2082 and F10_2083 not defined
                'F10_2133': data_dict.get('F10_2062', 0.0),
                'F10_2059': sum(float(data_dict.get('F10_%s' % n, 0.0)) for n in range(2060, 2090)),
            })

            result[employee.id] = {**basic_info, **data_dict}
        return result

    def _get_marital_status(self, file_type='pdf'):
        self.ensure_one()

        if file_type == 'pdf':
            marital = {
                'single': 'O',
                'married': 'G',
                'cohabitant': 'G',
                'widower': 'W',
                'divorced': 'E',
            }
            return marital.get(self.marital, 'O')
        marital = {
            'single': '1',
            'married': '2',
            'cohabitant': '2',
            'widower': '3',
            'divorced': '4',
        }
        return marital.get(self.marital, '0')

    def _get_281_10_family_situation(self):
        """
            This method returns a code that symbolizes the family situation.
        """
        if self.marital == 'married' or self.marital == 'cohabitant':
            if self.spouse_fiscal_status == 'with income':
                return '1'
            if self.spouse_fiscal_status == 'without income':
                if self.spouse_net_revenue == 0 and self.spouse_other_net_revenue <= 135.0:
                    return '2'
                if self.spouse_net_revenue <= 225.0 and self.spouse_other_net_revenue == 0:
                    return '3'
                if self.spouse_other_net_revenue <= 445.0 and self.spouse_net_revenue == 0:
                    return '3'
                raise UserError(_('The employee %s has a spouse without any revenue, but some revenues are declared for him.') % (self.name))
            raise UserError(_('The fiscal status for the spouse of the employee %s is not defined.') % (self.name))
        return '0'  # single, widow, ...

    def _get_dependent_people(self):
        if not self.other_dependent_people:
            return 0

        return self.other_senior_dependent + self.other_disabled_senior_dependent + self.other_juniors_dependent + self.other_disabled_juniors_dependent

    def _get_divers_status(self):
        if self.dependent_children and self._get_marital_status() in ['O', 'W']:
            return 'X'
        return ''

    def _get_holiday_remuneration(self, year):
        """
            This method returns the sum of the remuneration of the holiday pay.
            This holiday pay does not correspond to the 'Double Holiday Bonus'
            but to the number of leaves that the employee had before changing companies.
        """
        slip_ids = self.mapped('slip_ids').filtered(
            lambda slip: slip.struct_id == self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_departure_n_holidays') \
                    and slip.date_to.year == int(year))
        return sum(slip._get_salary_line_total('TAXABLE') for slip in slip_ids)

    def _generate_281_10_form_pdf(self, employee_data):
        self.ensure_one()
        file_name = '%s-%s-281_10' % (employee_data['year'], self.name)
        if employee_data.get('is_test', False):
            file_name += '-test'
        export_281_sheet_filename_pdf = file_name + '.pdf'

        export_281_sheet_pdf, _ = self.env.ref('l10n_be_hr_payroll.action_report_employee_281_10').render_qweb_pdf(self.id, employee_data)

        return export_281_sheet_filename_pdf, export_281_sheet_pdf

    def _generate_281_10_form_xml(self, employee_data):
        self.ensure_one()

        def add_elements(parent, children, data=employee_data):
            for name, key in children:
                element = etree.SubElement(parent, name)
                value = data.get(key, key)
                if isinstance(value, float):
                    value = float_round(value, 2)
                value = str(value)
                element.text = value

        file_name = employee_data['year'] + '-' + self.name + '-281_10'
        file_name += '-test' if employee_data['is_test'] else ''
        export_281_sheet_filename_xml = file_name + '.xml'

        Verzendingen = etree.Element('Verzendingen')
        Verzending = etree.SubElement(Verzendingen, 'Verzending')

        bestandtype = 'BELCOTST' if employee_data['is_test'] else 'BELCOTAX'

        elements = [('v0002_inkomstenjaar', 'year'), ('v0010_bestandtype', bestandtype),
                    ('v0011_aanmaakdatum', fields.Date.today().strftime('%d-%m-%Y')),
                    ('v0014_naam', 'company_name'), ('v0015_adres', 'company_address'),
                    ('v0016_postcode', 'company_zip'), ('v0017_gemeente', 'company_city'),
                    ('v0018_telefoonnummer', 'company_phone'), ('v0021_contactpersoon', 'contact_person_name'),
                    ('v0022_taalcode', 'language_code'), ('v0023_emailadres', 'contact_person_mail'),
                    ('v0024_nationaalnr', 'bce_number'), ('v0025_typeenvoi', 'type_sending')]

        add_elements(Verzending, elements)

        Aangiften = etree.SubElement(Verzending, 'Aangiften')
        Aangifte = etree.SubElement(Aangiften, 'Aangifte')

        elements = [('a1002_inkomstenjaar', 'year'), ('a1005_registratienummer', 'bce_number'),
                    ('a1011_naamnl1', 'company_name'), ('a1013_adresnl', 'company_address'),
                    ('a1015_gemeente', 'company_city'), ('a1020_taalcode', 'A1020')]

        add_elements(Aangifte, elements)

        Opgaven = etree.SubElement(Aangifte, 'Opgaven')
        Opgave32510 = etree.SubElement(Opgaven, 'Opgave32510')
        Opgave32510.append(self._get_fiche_281_10_xml(employee_data))  # Get the 281.10 sheet in xml.

        # "nombre total d'enregistrements dans le fichier "données" (premier et dernier enregistrement compris)" --> ici = 1
        elements = [('r8002_inkomstenjaar', 'year'), ('r8010_aantalrecords', 1), ('r8011_controletotaal', 'F2009'),
                    ('r8012_controletotaal', 'F10_2059')]

        add_elements(Aangifte, elements)

        # nombre de fichiers logiques constituant le fichier physique (fichier début et fichier fin compris) --> ici = 1
        # nombre d'enregistrements de l’envoi (fichier début et fichier fin compris)
        elements = [('r9002_inkomstenjaar', 'year'), ('r9010_aantallogbestanden', 1),
                    ('r9011_totaalaantalrecords', 1), ('r9012_controletotaal', 'F2009'),
                    ('r9013_controletotaal', 'F10_2059')]

        add_elements(Verzending, elements)

        export_281_sheet_xml = etree.tostring(Verzendingen, xml_declaration=True, encoding='utf-8')

        return export_281_sheet_filename_xml, export_281_sheet_xml

    def _get_fiche_281_10_xml(self, employee_data):
        def add_elements(parent, children, data=employee_data):
            for name, key in children:
                element = etree.SubElement(parent, name)
                value = data.get(key, key)
                if isinstance(value, float):
                    value = float_round(value, 2)
                value = str(value)
                element.text = value

        Fiche28110 = etree.Element('Fiche28110')

        elements = [('f2002_inkomstenjaar', 'year'), ('f2005_registratienummer', 'bce_number'),
                    ('f2008_typefiche', 'F2008'), ('f2009_volgnummer', 'F2009'), ('f2013_naam', 'employee_name'),
                    ('f2015_adres', 'employee_address'), ('f2016_postcodebelgisch', 'employee_zip'),
                    ('f2018_landwoonplaats', 'F2018'), ('f2019_burgerlijkstand', 'F2019'), ('f2020_echtgenote', 'F2020'),
                    ('f2021_aantalkinderen', 'F2021'), ('f2022_anderentlaste', 'F2022'), ('f2023_diverse', 'F2023'),
                    ('f2024_echtgehandicapt', 'F2024'), ('f2026_verkrghandicap', 'F2026'), ('f2027_taalcode', 'F2027'),
                    ('f2028_typetraitement', 'type_treatment'), ('f2029_enkelopgave325', 'F2029'),
                    ('f2112_buitenlandspostnummer', 'F2112'), ('f10_2031_vermelding', 'F10_2031'),
                    ('f10_2034_ex', 'F10_2034'), ('f10_2035_verantwoordingsstukken', 'F10_2035'),
                    ('f10_2036_inwonersdeenfr', 'F10_2036'), ('f10_2037_vergoedingkosten', 'F10_2037'),
                    ('f10_2039_optiebuitvennoots', 'F10_2039'), ('f10_2040_individualconvention', 'F10_2040'),
                    ('f10_2041_overheidspersoneel', 'F10_2041'), ('f10_2042_sailorcode', 'F10_2042'),
                    ('f10_2045_code', 'F10_2045'), ('f10_2055_datumvanindienstt', 'F10_2055'),
                    ('f10_2056_datumvanvertrek', 'F10_2056'), ('f10_2058_km', 'F10_2058'),
                    ('f10_2059_totaalcontrole', 'F10_2059'), ('f10_2060_gewonebezoldiginge', 'F10_2060'),
                    ('f10_2061_bedragoveruren300horeca', 'F10_2061'), ('f10_2062_totaal', 'F10_2062'),
                    ('f10_2063_vervroegdvakantieg', 'F10_2063'), ('f10_2064_afzbelachterstall', 'F10_2064'),
                    ('f10_2065_opzeggingsreclasseringsverg', 'F10_2065'), ('f10_2066_impulsfund', 'F10_2066'),
                    ('f10_2067_rechtvermindering66_81', 'F10_2067'), ('f10_2068_rechtvermindering57_75', 'F10_2068'),
		            ('f10_2069_fidelitystamps', 'F10_2069'), ('f10_2070_decemberremuneration', 'F10_2070'),
                    ('f10_2071_totalevergoeding', 'F10_2071'), ('f10_2072_pensioentoezetting', 'F10_2072'),
                    ('f10_2073_manageroutdatedvooropzeg', 'F10_2073'), ('f10_2074_bedrijfsvoorheffing', 'F10_2074'),
                    ('f10_2075_bijzonderbijdrage', 'F10_2075'), ('f10_2076_voordelenaardbedrag', 'F10_2076'),
                    ('f10_2077_totaal', 'F10_2077'), ('f10_2078_eigenkosten', 'F10_2078'),
                    ('f10_2079_tussenkomstintr', 'F10_2079'), ('f10_2080_detacheringsvergoed', 'F10_2080'),
                    ('f10_2081_gewonebijdragenenpremies', 'F10_2081'), ('f10_2082_bedrag', 'F10_2082'),
                    ('f10_2083_bedrag', 'F10_2083'), ('f10_2084_mobiliteitsvergoedi', 'F10_2084'),
                    ('f10_2085_forfbezoldiging', 'F10_2085'), ('f10_2086_openbaargemeenschap', 'F10_2086'),
                    ('f10_2087_bedrag', 'F10_2087'), ('f10_2088_andervervoermiddel', 'F10_2088'),
                    ('f10_2090_outborderdays', 'F10_2090'), ('f10_2093_datevooropzeg', 'F10_2093'),
                    ('f10_2095_aantaluren', 'F10_2095'), ('f10_2097_aantaluren', 'F10_2097'),
                    ('f10_2099_aard', 'F10_2099'), ('f10_2100_nrparitaircomite', 'F10_2100'),
                    ('f10_2101_percentages', 'F10_2101'), ('f10_2102_kasofvennootschap', 'F10_2102'),
                    ('f10_2109_fiscaalidentificat', 'F10_2109'), ('f10_2110_aantaloveruren360', 'F10_2110'),
                    ('f10_2111_achterstalloveruren300horeca', 'F10_2111'), ('f10_2113_forfaitrsz', 'F10_2113'),
                    ('f10_2115_bonus', 'F10_2115'), ('f10_2116_badweatherstamps', 'F10_2116'),
                    ('f10_2117_nonrecurrentadvantages', 'F10_2117'), ('f10_2118_aantaloveruren', 'F10_2118'),
                    ('f10_2119_sportremuneration', 'F10_2119'), ('f10_2120_sportvacancysavings', 'F10_2120'),
                    ('f10_2121_sportoutdated', 'F10_2121'), ('f10_2122_sportindemnificationofretraction', 'F10_2122'),
                    ('f10_2123_managerremuneration', 'F10_2123'), ('f10_2124_managervacancysavings', 'F10_2124'),
                    ('f10_2125_manageroutdated', 'F10_2125'), ('f10_2126_managerindemnificationofretraction', 'F10_2126'),
                    ('f10_2127_nonrecurrentadvantagesoutdated', 'F10_2127'),
                    ('f10_2128_opzeggingsreclasseringsvergvrijst', 'F10_2128'),
                    ('f10_2129_sportindemnificationofretractionvrijst', 'F10_2129'),
                    ('f10_2130_privatepc', 'F10_2130'), ('f10_2131_managerindemnificationofretractionvrijst', 'F10_2131'),
                    ('f10_2132_totaalgewone', 'F10_2132'), ('f10_2133_totaalvooropzeg', 'F10_2133'),
                    ('f10_2134_afzbelachterstallvooropzeg', 'F10_2134'),
                    ('f10_2135_decemberremunerationvoooropzeg', 'F10_2135'),
                    ('f10_2136_sportremunerationvooropzeg', 'F10_2136'), ('f10_2137_sportoutdatedvooropzeg', 'F10_2137'),
                    ('f10_2138_managerremunerationvooropzeg', 'F10_2138'),
                    ('f10_2141_occasionalworkhoreca', 'F10_2141'), ('f10_2142_aantaloveruren180', 'F10_2142'),
                    ('f10_2143_bedragoveruren360horeca', 'F10_2143'),
                    ('f10_2165_achterstalloveruren360horeca', 'F10_2165'), ('f10_2166_flexi_job', 'F10_2166'),
                    ('f10_2167_aantaloveruren300horeca', 'F10_2167'),
                    ('f10_2168_achterstallaantaloveruren300horeca', 'F10_2168'),
                    ('f10_2169_aantaloveruren360horeca', 'F10_2169'),
                    ('f10_2170_achterstallaantaloveruren360horeca', 'F10_2170'),
                    ('f10_2176_cashforcar', 'F10_2176'), ('f10_2177_winstpremies', 'F10_2177'),
                    ('f10_2178_cashforcartotaal', 'F10_2178'), ('f10_2179_startersjob', 'F10_2179')]

        add_elements(Fiche28110, elements)

        return Fiche28110
