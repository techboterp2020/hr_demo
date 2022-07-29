from odoo import models, fields, api
from datetime import datetime
from dateutil.relativedelta import relativedelta

class EmployeeSettlement(models.Model):
    _name  = "hr.settlement"
    _description = "Employee Settlement"

    @api.onchange('leave_type_id')
    def _onchange_leave_type(self):
        for l in self:
            hr_contract_id = self.env['hr.contract'].search(
                [('employee_id', '=', l.employee_id.id)],  limit=1)
            if l.leave_type_id:
                leave_id = self.env['hr.leave'].search(
                    [('employee_ids', 'in', l.employee_id.id), ('holiday_status_id', '=', l.leave_type_id.id),
                     ('state', '=', 'validate')])
                leave_days = 0
                for leave in leave_id:
                    leave_days += leave.number_of_days
                allocation_id = self.env['hr.leave.allocation'].search(
                    [('employee_id', '=', l.employee_id.id), ('holiday_status_id', '=', l.leave_type_id.id),
                     ('state', '=', 'validate')])
                allocated_leaves = 0
                for all in allocation_id:
                    allocated_leaves += all.number_of_days_display

                if leave_days:
                    remaining = allocated_leaves - leave_days
                else:
                    remaining = allocated_leaves
                l.write({'balance_leaves': remaining,
                         'eligible_leave_salary': (remaining) * (float(hr_contract_id.wage) / 30)
                         })

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        for i in self:
            leave_types = []
            hr_contract_id = self.env['hr.contract'].search(
                [('employee_id', '=', i.employee_id.id)], limit=1)
            i.write({
                'department_id': hr_contract_id.department_id.id,
                'job_id': hr_contract_id.job_id.id,
                'join_date': hr_contract_id.date_start,
                'last_date': hr_contract_id.date_end if hr_contract_id.date_end else fields.Date.today(),
                'contract_type': 'limited' if hr_contract_id.date_end else 'unlimited',
                'basic_salary': hr_contract_id.wage,
                'per_day_salary': float(hr_contract_id.wage) / 30,

            })
            employee = self.env['hr.leave.allocation'].search([('employee_id', '=', i.employee_id.id)])
            for emp in employee:
                if emp.holiday_status_id.id not in leave_types:
                    leave_types.append(emp.holiday_status_id.id)
            return {'domain': {'leave_type_id': [('id', 'in', leave_types)]}}

    name = fields.Char()
    employee_id = fields.Many2one('hr.employee', string='Employee',
                                  required=True, help="Employee")
    settlement_type_id = fields.Many2one('settlement.type', string="Settlement Type", required=True)
    join_date = fields.Date(string='Join Date')
    resign_date = fields.Date(string="Resign Date", default=fields.Date.context_today)
    last_date = fields.Date(string="Last Working Date")
    basic_salary = fields.Float(string="Basic Salary")
    reason = fields.Text()
    department_id = fields.Many2one('hr.department', string="Department", readonly=True)
    job_id = fields.Many2one('hr.job', string='Job', readonly=True)
    contract_type = fields.Selection([('limited', 'Limited'), ('unlimited', 'Unlimited')], string='Contract Type', required=True)
    gratuity_lines = fields.One2many('gratuity.lines', 'settlement_grat_id')
    gratuity_amount = fields.Float(compute='_get_gratuity_amount', store=True)

    balance_leaves = fields.Float(readonly="1")
    per_day_salary = fields.Float(string='Per Day Annual leave Salary', readonly="1")
    eligible_leave_salary = fields.Float(readonly="1")

    total_gratuity_amount = fields.Float(compute='_get_total_gratuity_amount', store=True)
    leave_type_id = fields.Many2one('hr.leave.type')
    state = fields.Selection([('draft', 'Draft'), ('generate', 'Generate'), ('gratuity_values', 'Calculated Gratuity Amount'),
                              ('validate', 'Validate'), ('paid', 'Paid')], default='draft')

    def action_paid(self):
        for i in self:
            i.state = 'paid'

    def action_create_journal_entry(self):
        for gratuity in self:
            date = fields.Date.context_today(self)
            move_dict = {
                'narration': '',
                # 'ref': fields.Date.context_today,   # strftime('%B %Y')
                'journal_id': gratuity.settlement_type_id.journal_id.id,
                'date': date,
            }
            line_ids = []
            debit_account_id = gratuity.settlement_type_id.account_debit.id
            credit_account_id = gratuity.settlement_type_id.account_credit.id

            amount = gratuity.total_gratuity_amount

            if debit_account_id:  # If the rule has a debit account.
                debit = amount if amount > 0.0 else 0.0
                credit = -amount if amount < 0.0 else 0.0

                # debit_line = self._get_existing_lines(
                #     line_ids, line, debit_account_id, debit, credit)

                # if not debit_line:
                debit_line = self._prepare_line_values(gratuity, debit_account_id, date, debit, credit)
                line_ids.append(debit_line)
            # else:
            #     debit_line['debit'] += debit
            #     debit_line['credit'] += credit

            if credit_account_id:  # If the rule has a credit account.
                debit = -amount if amount < 0.0 else 0.0
                credit = amount if amount > 0.0 else 0.0
                # credit_line = self._get_existing_lines(
                #     line_ids, line, credit_account_id, debit, credit)

                # if not credit_line:
                credit_line = self._prepare_line_values(gratuity, credit_account_id, date, debit, credit)
                line_ids.append(credit_line)
                # else:
                #     credit_line['debit'] += debit
                #     credit_line['credit'] += credit
            if line_ids:
                move_dict['line_ids'] = [(0, 0, line_vals) for line_vals in line_ids]
                move = self.env['account.move'].sudo().create(move_dict)
                gratuity.state = 'validate'
        return True

    def _prepare_line_values(self, line, account_id, date, debit, credit):
        return {
            'name': line.name,
            # 'partner_id': line.partner_id.id,
            'account_id': account_id,
            'journal_id': line.settlement_type_id.journal_id.id,
            'date': date,
            'debit': debit,
            'credit': credit,
            # 'analytic_account_id': line.salary_rule_id.analytic_account_id.id or line.slip_id.contract_id.analytic_account_id.id,
        }


    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('employee.settlement')
        return super(EmployeeSettlement, self).create(vals)

    @api.depends('eligible_leave_salary', 'gratuity_amount')
    def _get_total_gratuity_amount(self):
        total_amount = 0
        for i in self:
            gratuity_amount = i.gratuity_amount if i.gratuity_amount else 0.0
            eligible_leave_salary = i.eligible_leave_salary if i.eligible_leave_salary else 0.0
            total_amount += gratuity_amount + eligible_leave_salary
        self.total_gratuity_amount = total_amount


    @api.depends('gratuity_lines.resign_amount')
    def _get_gratuity_amount(self):
        total = 0
        for i in self.gratuity_lines:
            total += i.resign_amount
        self.gratuity_amount = total

    def generate_gratuity_amount(self):
        hr_contract_id = self.env['hr.contract'].search(
            [('employee_id', '=', self.employee_id.id)])
        one_day_wage = float(hr_contract_id.wage) / 30
        join_date = self.join_date
        last_date = self.last_date
        joining_date = datetime.strptime(str(join_date), "%Y-%m-%d").date()
        last_date = datetime.strptime(str(last_date), "%Y-%m-%d").date()
        experience = float((last_date - joining_date).days) / 365.00
        for lines in self.gratuity_lines:
            if self.contract_type == 'unlimited' and self.settlement_type_id.final_settlement == 'resign':
                if experience < 5:
                    lines.resign_amount = ((one_day_wage * lines.no_of_days) * lines.gratuity_fraction * lines.years_of_service)
                else:
                    lines.resign_amount = ((one_day_wage * lines.no_of_days) * lines.years_of_service)

            else:
                lines.resign_amount = ((one_day_wage * lines.no_of_days) * lines.years_of_service)
        self.state = 'gratuity_values'


    def generate(self):
        for obj in self:
            obj.gratuity_lines.unlink()
            data_lines = []
            final_settlement = obj.settlement_type_id.final_settlement
            join_date = obj.join_date
            last_date = obj.last_date
            joining_date = datetime.strptime(str(join_date), "%Y-%m-%d").date()
            last_date = datetime.strptime(str(last_date), "%Y-%m-%d").date()
            experience = float((last_date -  joining_date).days)/365.00
            experiance_days = float((last_date -  joining_date).days)
            working_days = ((last_date - joining_date).days + 1)

            l_date = obj.join_date + relativedelta(years=5)
            exp = float((l_date - joining_date).days) / 365.00
            extra_year = experience - exp
            extra_year_in_days = extra_year * 365

            if obj.contract_type == 'limited' and final_settlement == 'resign':
                if experience < 1:
                    vals1 = {
                        'slab': '0 to 1 Year',
                        'date_from': joining_date,
                        'date_to': last_date,
                        'no_of_days': 0,
                        'total_exp': experience,
                        'years_of_service': experience,
                        'termination_amount': 0.0,
                        'resign_amount': 0.0,
                    }
                    data_lines.append((0, 0, vals1), )
                elif experience >= 1 and experience < 5:
                    # gratuity = (((7 * one_day_wage)/365.0) * experiance_days)
                    vals2 = {
                              'slab':'1 to 5 Year',
                              'date_from':joining_date,
                              'date_to':last_date,
                              'no_of_days':0,
                              'total_exp': experience,
                              'years_of_service': experience,
                              'termination_amount':0,
                              'resign_amount':0,
                    }
                    data_lines.append((0,0,vals2),)
                elif experience >= 5:

                    # gratuity_amount = ((one_day_wage * 21) * experience)
                    vals2 = {
                        'slab': '1 to 5 Year',
                        'date_from': joining_date,
                        'date_to': l_date,
                        'no_of_days': 0,
                        'total_exp': experience,
                        'years_of_service': exp,
                        'termination_amount': 0,
                        'resign_amount': 0,
                    }
                    data_lines.append((0, 0, vals2), )

                    vals3 = {
                        'slab': 'Over 5 Years',
                        'date_from': l_date,
                        'date_to': last_date,
                        'no_of_days': 0,
                        'total_exp': experience,
                        'years_of_service': extra_year,
                        'termination_amount': 0,
                        'resign_amount': 0,
                    }
                    data_lines.append((0, 0, vals3), )

            if obj.contract_type == 'unlimited' and final_settlement == 'termination':
                if experience < 1:
                    vals1 = {
                        'slab': '0 to 1 Year',
                        'date_from': joining_date,
                        'date_to': last_date,
                        'no_of_days': 0,
                        'total_exp': experience,
                        'years_of_service': experience,
                        'termination_amount': 0.0,
                        'resign_amount': 0.0,
                    }
                    data_lines.append((0, 0, vals1), )
                elif experience >= 1 and experience < 5:
                    vals2 = {
                        'slab': '1 to 5 Year',
                        'date_from': joining_date,
                        'date_to': last_date,
                        'no_of_days': 0,
                        'total_exp': experience,
                        'years_of_service': experience,
                        'termination_amount': 0,
                        'resign_amount': 0,
                    }
                    data_lines.append((0, 0, vals2), )
                elif experience >= 5:
                    # gratuity_amount = ((one_day_wage * 21) * experience)
                    vals2 = {
                        'slab': '1 to 5 Year',
                        'date_from': joining_date,
                        'date_to': l_date,
                        'no_of_days': 0,
                        'total_exp': experience,
                        'years_of_service': exp,
                        'termination_amount': 0,
                        'resign_amount': 0,
                    }
                    data_lines.append((0, 0, vals2), )

                    vals3 = {
                        'slab': 'Over 5 Years',
                        'date_from': l_date,
                        'date_to': last_date,
                        'no_of_days': 0,
                        'total_exp': experience,
                        'years_of_service': extra_year,
                        'termination_amount': 0,
                        'resign_amount': 0,
                    }
                    data_lines.append((0, 0, vals3), )

            if obj.contract_type == 'unlimited' and final_settlement == 'resign':
                if experience < 1:
                    vals1 = {
                        'slab': '0 to 1 Year',
                        'date_from': joining_date,
                        'date_to': last_date,
                        'no_of_days': 0,
                        'total_exp': experience,
                        'years_of_service': experience,
                        'termination_amount': 0.0,
                        'resign_amount': 0.0,
                    }
                    data_lines.append((0, 0, vals1), )
                elif experience >= 1 and experience < 3:
                    vals2 = {
                        'slab': '1 to 3 Year',
                        'date_from': joining_date,
                        'date_to': last_date,
                        'no_of_days': 0,
                        'total_exp': experience,
                        'years_of_service': experience,
                        'gratuity_fraction': 0.0,
                        'termination_amount': 0.0,
                        'resign_amount': 0.0,
                    }
                    data_lines.append((0, 0, vals2), )
                elif experience >= 3 and experience < 5:
                    vals3 = {
                        'slab': '3 to 5 Year',
                        'date_from': joining_date,
                        'date_to': last_date,
                        'no_of_days': 0,
                        'total_exp': experience,
                        'years_of_service': experience,
                        'gratuity_fraction': 0.0,
                        'termination_amount': 0.0,
                        'resign_amount': 0.0,
                    }
                    data_lines.append((0, 0, vals3), )
                elif experience >= 5:

                    vals2 = {
                        'slab': '1 to 5 Year',
                        'date_from': joining_date,
                        'date_to': l_date,
                        'no_of_days': 0,
                        'total_exp': experience,
                        'years_of_service': exp,
                        'termination_amount': 0,
                        'resign_amount': 0,
                    }
                    data_lines.append((0, 0, vals2), )

                    vals3 = {
                        'slab': 'Over 5 Years',
                        'date_from': l_date,
                        'date_to': last_date,
                        'no_of_days': 0,
                        'total_exp': experience,
                        'years_of_service': extra_year,
                        'termination_amount': 0,
                        'resign_amount': 0,
                    }
                    data_lines.append((0, 0, vals3), )

            self.gratuity_lines = data_lines
            self.state = 'generate'


class GratuityLines(models.Model):
    _name = "gratuity.lines"
    _description = "Gratuity Lines"

    slab = fields.Char(string="Slab")
    date_from = fields.Date(string="Date From")
    date_to = fields.Date(string="Date To")
    no_of_days = fields.Float(string="Num of Days / Month")
    termination_amount = fields.Float(string="Termination")
    resign_amount = fields.Float(string="Resignation")
    settlement_grat_id = fields.Many2one('hr.settlement', string="Settlement")
    years_of_service = fields.Float(string='Years Of Service')
    total_exp = fields.Float(string='Experience')
    gratuity_fraction = fields.Float()


