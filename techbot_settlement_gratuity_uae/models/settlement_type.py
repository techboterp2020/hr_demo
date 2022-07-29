from odoo import models, fields


class SettlementType(models.Model):
    _name = "settlement.type"
    _description = "Settlement Type"

    name = fields.Char("Name", required=True)
    final_settlement = fields.Selection([('resign', 'Resign'), ('termination', 'Termination')])
    remarks = fields.Text("Remarks")
    journal_id = fields.Many2one('account.journal', string="Journal")
    settlement_type_master_line = fields.One2many('settlement.type.line', 'settlement_type_id',
                                                  string="Settlement Line")
    account_debit = fields.Many2one('account.account')
    account_credit = fields.Many2one('account.account')


class SettlementTypeLine(models.Model):
    _name = "settlement.type.line"
    _description = "Settlement Type Line"

    account_id = fields.Many2one('account.account', "Account")
    settlement_type_id = fields.Many2one('settlement.type')
