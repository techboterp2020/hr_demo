from odoo import models, fields


class SettlementType(models.Model):
    _name = "settlement.type"

    name = fields.Char("Name", required=True)
    final_settlement = fields.Selection([('resign', 'Resign'), ('termination', 'Termination')])
    remarks = fields.Text("Remarks")
    journal_id = fields.Many2one('account.journal', string="Journal")
    settlement_type_master_line = fields.One2many('settlement.type.line', 'settlement_type_master_line_id',
                                                  string="Settlement Line")


class SettlementTypeLine(models.Model):
    _name = "settlement.type.line"

    account_id = fields.Many2one('account.account', "Account")
    settlement_type_master_line_id = fields.Many2one('settlement.type')
