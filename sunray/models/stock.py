# -*- coding: utf-8 -*-
import datetime

from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from odoo.tools import email_split, float_is_zero
from ast import literal_eval
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _

class ResCompany(models.Model):
    _inherit = "res.company"
    
    company_lead_approval = fields.Boolean(string='Lead Approval', company_dependent=True)
    
class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    lead_approval = fields.Boolean(string='Lead Approval', company_dependent=False, readonly=False, related='company_id.company_lead_approval')
    
class Partner(models.Model):
    _name = 'res.partner'
    _inherit = 'res.partner'
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submit', 'Submitted'),
        ('validate', 'Second Approval'),
        ('approve', 'Approved'),
        ('reject', 'Rejected'),
        ], string='Status', readonly=True, index=True, copy=False, default='draft', track_visibility='onchange')
    
    type = fields.Selection(
        [('contact', 'Contact'),
         ('invoice', 'Invoice address'),
         ('delivery', 'Shipping address'),
         ('other', 'Sub Account'),
         ("private", "Private Address"),
        ], string='Address Type',
        default='contact',
        help="Used by Sales and Purchase Apps to select the relevant address depending on the context.")
    
    tax_compliance = fields.Selection([('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5')], string='Tax compliance', required=False)
    due_diligence_form = fields.Selection([('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5')], string='Due Diligence Form', required=False)
    cac = fields.Selection([('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5')], string='CAC', required=False)
    delivery_speed = fields.Selection([('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5')], string='Delivery Speed')
    
    overall_vendor_rating = fields.Selection([('0', '0'),('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5')], string='Overall Vendor Rating', required=False)
    
    parent_account_number = fields.Char(string='Parent Account Number', required=False, index=True, copy=False, store=True)
    
    vendor_registration = fields.Boolean ('Vendor fully Registered', track_visibility="onchange", readonly=True)
    
    @api.model
    def create(self, vals):
        if 'customer' in vals and vals['customer'] == True:
            vals['parent_account_number'] = self.env['ir.sequence'].next_by_code('res.partner') or '/'
        return super(Partner, self).create(vals)
    
    @api.multi
    def name_get(self):
        res = []
 
        for partner in self:
            result = partner.name
            if partner.parent_account_number:
                result = str(partner.name) + " " + str(partner.parent_account_number)
            res.append((partner.id, result))
        return res
    
    @api.multi
    def button_reset(self):
        self.write({'state': 'draft'})
        return {}
    
    @api.multi
    def button_submit(self):
        self.write({'state': 'submit'})
        group_id = self.env['ir.model.data'].xmlid_to_object('sunray.group_one_vendor_approval')
        user_ids = []
        partner_ids = []
        for user in group_id.users:
            user_ids.append(user.id)
            partner_ids.append(user.partner_id.id)
        self.message_subscribe(partner_ids=partner_ids)
        subject = "This Vendor {} needs first approval".format(self.name)
        self.message_post(subject=subject,body=subject,partner_ids=partner_ids)
        return {}
    
    @api.multi
    def button_validate(self):
        self._check_line_manager()
        self.write({'state': 'validate'})
        group_id = self.env['ir.model.data'].xmlid_to_object('sunray.group_two_vendor_approval')
        user_ids = []
        partner_ids = []
        for user in group_id.users:
            user_ids.append(user.id)
            partner_ids.append(user.partner_id.id)
        self.message_subscribe(partner_ids=partner_ids)
        subject = "This Vendor {} needs second approval".format(self.name)
        self.message_post(subject=subject,body=subject,partner_ids=partner_ids)
        return {}
    
    @api.multi
    def button_approve(self):
        self.write({'state': 'approve'})
        self.vendor_registration = True
        return {}
    
    @api.multi
    def button_reject(self):
        self.write({'state': 'reject'})
        return {}
    
class HrExpenseSheet(models.Model):
    _name = "hr.expense.sheet"
    _inherit = 'hr.expense.sheet'
    
    state = fields.Selection([('submit', 'Submitted'),
                              ('approve', 'Line Manager Approved'),
                              ('confirmed', 'MD Approved'),
                              ('post', 'Posted'),
                              ('open', 'Open'),
                              ('done', 'Paid'),
                              ('cancel', 'Refused')
                              ], string='Status', index=True, readonly=True, track_visibility='onchange', copy=False, default='submit', required=True,
    help='Expense Report State')
    
    @api.multi
    def button_md_approval(self):
        self.write({'state': 'confirmed'})
        return {}
    
    @api.multi
    def action_sheet_move_create(self):
        if any(sheet.state != 'confirmed' for sheet in self):
            raise UserError(_("You can only generate accounting entry for approved expense(s)."))

        if any(not sheet.journal_id for sheet in self):
            raise UserError(_("Expenses must have an expense journal specified to generate accounting entries."))

        expense_line_ids = self.mapped('expense_line_ids')\
            .filtered(lambda r: not float_is_zero(r.total_amount, precision_rounding=(r.currency_id or self.env.user.company_id.currency_id).rounding))
        res = expense_line_ids.action_move_create()

        if not self.accounting_date:
            self.accounting_date = self.account_move_id.date

        if self.payment_mode == 'own_account' and expense_line_ids:
            self.write({'state': 'post'})
        else:
            self.write({'state': 'done'})
        self.activity_update()
        return res

class BudgetDept(models.Model):
    _name = 'account.budget.post'
    _inherit = 'account.budget.post'
    
    department_id = fields.Many2one(
        comodel_name="hr.department",
        string='Department')

class CrossoveredBudgetLines(models.Model):
    _name = "crossovered.budget.lines"
    _inherit = ['crossovered.budget.lines']
    _order = "general_budget_id"
    
    allowed_amount = fields.Float(compute='_compute_allowed_amount', string='Allowed Amount', digits=0, store=False)
    commitments = fields.Float(compute='_compute_commitments', string='Commitments', digits=0, store=False)
    dept_id = fields.Many2one('hr.department', 'Department',related='general_budget_id.department_id', store=True, readonly=False, copy=False)
    
    practical_amount = fields.Float(compute='_compute_practical_amount', string='Practical Amount', digits=0, store=False)
    theoritical_amount = fields.Float(compute='_compute_theoritical_amount', string='Theoretical Amount', digits=0, store=False)
    percentage = fields.Float(compute='_compute_percentage', string='Achievement', store=False)
    '''
    dept_id = fields.Many2one(
        comodel_name='account.budget.post')
    department = fields.Many2one(
        comodel_name='hr.department',
        related = 'dept_id.department_id',
        string='Department')
    '''
    @api.multi
    def _compute_theoritical_amount(self):
        today = fields.Datetime.now()
        for line in self:
            # Used for the report

            if self.env.context.get('wizard_date_from') and self.env.context.get('wizard_date_to'):
                date_from = fields.Datetime.from_string(self.env.context.get('wizard_date_from'))
                date_to = fields.Datetime.from_string(self.env.context.get('wizard_date_to'))
                if date_from < fields.Datetime.from_string(line.date_from):
                    date_from = fields.Datetime.from_string(line.date_from)
                elif date_from > fields.Datetime.from_string(line.date_to):
                    date_from = False

                if date_to > fields.Datetime.from_string(line.date_to):
                    date_to = fields.Datetime.from_string(line.date_to)
                elif date_to < fields.Datetime.from_string(line.date_from):
                    date_to = False

                theo_amt = 0.00
                if date_from and date_to:
                    line_timedelta = fields.Datetime.from_string(line.date_to) - fields.Datetime.from_string(line.date_from)
                    elapsed_timedelta = date_to - date_from
                    if elapsed_timedelta.days > 0:
                        theo_amt = (elapsed_timedelta.total_seconds() / line_timedelta.total_seconds()) * line.planned_amount
            else:
                if line.paid_date:
                    if fields.Datetime.from_string(line.date_to) <= fields.Datetime.from_string(line.paid_date):
                        theo_amt = 0.00
                    else:
                        theo_amt = line.planned_amount
                else:
                    line_timedelta = fields.Datetime.from_string(line.date_to) - fields.Datetime.from_string(line.date_from)
                    elapsed_timedelta = fields.Datetime.from_string(today) - (fields.Datetime.from_string(line.date_from))

                    if elapsed_timedelta.days < 0:
                        # If the budget line has not started yet, theoretical amount should be zero
                        theo_amt = 0.00
                    
                    elif line_timedelta.days > 0 and fields.Datetime.from_string(today) < fields.Datetime.from_string(line.date_to):
                        month_dif =int(str(fields.Datetime.from_string(today))[5:7]) - int(str(line.date_from)[5:7]) + 1
#                         interval = int(str(line.date_to)[5:7]) - int(str(line.date_from)[5:7]) + 1
                        interval = 12
                        theo_amt =  (line.planned_amount/interval) * month_dif
                    else:
                        theo_amt = line.planned_amount

            line.theoritical_amount = theo_amt
    
    @api.multi
    def _compute_allowed_amount(self):
        for line in self:
            line.allowed_amount = line.theoritical_amount + float((line.practical_amount or 0.0)) + float((line.commitments or 0.0))
    
    
    @api.multi
    def _compute_commitments(self):
        for line in self:
            result = 0.0
            acc_ids = line.general_budget_id.account_ids.ids
            date_to = self.env.context.get('wizard_date_to') or line.date_to
            date_from = self.env.context.get('wizard_date_from') or line.date_from
            if line.analytic_account_id.id:
                self.env.cr.execute("""
                    SELECT sum(price_total) 
                    from purchase_order_line 
                    WHERE account_analytic_id=%s
                    AND account_id=ANY(%s)
                    AND order_id in (SELECT id FROM purchase_order WHERE state in ('done','purchase') 
                    and invoice_status != 'invoiced'
                    and date_order between to_date(%s,'yyyy-mm-dd') AND to_date(%s,'yyyy-mm-dd'))""",
                        (line.analytic_account_id.id, acc_ids, date_from, date_to,))
                result = self.env.cr.fetchone()[0] or 0.0
                
                self.env.cr.execute("""
                    SELECT sum(total_amount) 
                    from hr_expense 
                    WHERE analytic_account_id=%s
                    AND account_id=ANY(%s)
                    AND sheet_id in (SELECT id FROM hr_expense_sheet WHERE state = 'approve') 
                    and date between to_date(%s,'yyyy-mm-dd') AND to_date(%s,'yyyy-mm-dd')""",
                        (line.analytic_account_id.id, acc_ids, date_from, date_to,))
                result2 = self.env.cr.fetchone()[0] or 0.0
                
            line.commitments = -(result+result2)


class PurchaseOrder(models.Model):
    _name = "purchase.order"
    _inherit = ['purchase.order']
    
    #@api.onchange('project_id')
    #def _onchange_partner_id(self):
    #    self.partner_id = self.project_id.partner_id
    #    return {}
    
    @api.multi
    def _check_line_manager(self):
        current_employee = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        if current_employee == self.employee_id:
            raise UserError(_('You are not allowed to approve your own request.'))
        
    @api.multi
    def _check_vendor_registration(self):
        if self.partner_id.vendor_registration == False:
            raise UserError(_('Cant Confirm purchase order for an Unknown Vendor -- Request Vendor Registration.'))
    
    def _default_employee(self):
        self.env['hr.employee'].search([('user_id','=',self.env.uid)])
        return self.env['hr.employee'].search([('user_id','=',self.env.uid)])
    
    @api.multi
    def _check_override(self):
        for self in self:
            for line in self.order_line:
                if line.need_override and line.override_budget == False:
                    self.need_override = True
                else:
                    self.need_override = False
    
    need_override = fields.Boolean ('Need Budget Override', compute= "_check_override", track_visibility="onchange", copy=False)
    
    employee_id = fields.Many2one('hr.employee', 'Employee',
        states={'done': [('readonly', True)], 'cancel': [('readonly', True)]}, default=_default_employee)
    request_date = fields.Date(string='Request Date', readonly=True, track_visibility='onchange')
    department_name = fields.Char(string="Employee Department", related="employee_id.department_id.name", readonly=True)    
    
    approval_date = fields.Date(string='Manager Approval Date', readonly=True, track_visibility='onchange')
    manager_approval = fields.Many2one('res.users','Manager Approval Name', readonly=True, track_visibility='onchange')
    manager_position = fields.Char('Manager Position', readonly=True, track_visibility='onchange')
    
    po_approval_date = fields.Date(string='Confirmation Date', readonly=True, track_visibility='onchange')
    po_manager_approval = fields.Many2one('res.users','Manager Confirmation Name', readonly=True, track_visibility='onchange')
    po_manager_position = fields.Char('Manager Confirmation Position', readonly=True, track_visibility='onchange')
    
    client_id = fields.Many2one('res.partner','Client', track_visibility='onchange')
    
    project_id = fields.Many2one(comodel_name='project.project', string='Project')
    
    state = fields.Selection([
        ('draft', 'RFQ'),
        ('sent', 'RFQ Sent'),
        ('to approve', 'To Approve'),
        ('submit', 'Manager Approval'),
        ('legal', 'Awaiting Legal Review'),
        ('legal_reviewed', 'Reviewed'),
        ('purchase', 'Purchase Order'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled')
        ], string='Status', readonly=True, index=True, copy=False, default='draft', track_visibility='onchange')
    
    stock_source = fields.Char(string='Source document')
    store_request_id = fields.Many2one('stock.picking','Store Request', readonly=True, track_visibility='onchange')
    
    @api.model
    def create(self, vals):
        result = super(PurchaseOrder, self).create(vals)
        result.send_store_request_mail()
        return result
    
    @api.multi
    def send_store_request_mail(self):
        if self.store_request_id:
            config = self.env['mail.template'].sudo().search([('name','=','P.O Store Request')], limit=1)
            mail_obj = self.env['mail.mail']
            if config:
                values = config.generate_email(self.id)
                mail = mail_obj.create(values)
                if mail:
                    mail.send()
    
    @api.multi
    def button_submit(self):
        self.write({'state': 'submit'})
        self.request_date = date.today()
        return {}
    
    @api.multi
    def button_submit_legal(self):
        self.write({'state': 'legal'})
        group_id = self.env['ir.model.data'].xmlid_to_object('sunray.group_legal_team')
        user_ids = []
        partner_ids = []
        for user in group_id.users:
            user_ids.append(user.id)
            partner_ids.append(user.partner_id.id)
        self.message_subscribe_users(user_ids=user_ids)
        subject = "Purchase Order {} needs a review from legal team".format(self.name)
        self.message_post(subject=subject,body=subject,partner_ids=partner_ids)
        return False
    
    @api.multi
    def button_legal_reviewd(self):
        self.write({'state': 'legal_reviewed'})
        subject = "Legal team review has been Done, Purchase Order {} can be approved now".format(self.name)
        partner_ids = []
        for partner in self.message_partner_ids:
            partner_ids.append(partner.id)
        self.message_post(subject=subject,body=subject,partner_ids=partner_ids)
    
    @api.multi
    def _check_budget(self):
        override = False
        for line in self.order_line:
            self.env.cr.execute("""
                    SELECT * FROM crossovered_budget_lines WHERE
                    general_budget_id in (SELECT budget_id FROM account_budget_rel WHERE account_id=%s) AND
                    analytic_account_id = %s AND 
                    to_date(%s,'yyyy-mm-dd') between date_from and date_to""",
                    (line.account_id.id,line.account_analytic_id.id, line.order_id.date_order))
            result = self.env.cr.fetchone()
            if result:
                result = self.env['crossovered.budget.lines'].browse(result[0])  
                if line.price_total > result.allowed_amount and line.override_budget == False:
                    override = True
                    line.write({'need_override': True})
            else:
                if line.override_budget == False:
                    override = True
                    line.write({'need_override': True})
        if override:
            group_id = self.env['ir.model.data'].xmlid_to_object('sunray.group_hr_line_manager')
            user_ids = []
            partner_ids = []
            for user in group_id.users:
                user_ids.append(user.id)
                partner_ids.append(user.partner_id.id)
            self.message_subscribe_users(user_ids=user_ids)
            subject = "Purchase Order {} needs a budget override".format(self.name)
            self.message_post(subject=subject,body=subject,partner_ids=partner_ids)
            return False
        return True

    @api.multi
    def button_confirm(self):
        for order in self:
            if order.state not in ['draft','submit', 'sent']:
                continue
            self._check_line_manager()
            self._check_line_manager()
            #if self._check_budget() == False and self.need_override:
             #   return {}
            self.approval_date = date.today()
            self.manager_approval = self._uid
            order._add_supplier_to_product()
            # Deal with double validation process
            if order.company_id.po_double_validation == 'one_step'\
                    or (order.company_id.po_double_validation == 'two_step'\
                        and order.amount_total < self.env.user.company_id.currency_id.compute(order.company_id.po_double_validation_amount, order.currency_id))\
                    or order.user_has_groups('purchase.group_purchase_manager'):
                order.button_approve()
            else:
                order.write({'state': 'to approve'})
        return True
    
    @api.multi
    def button_approve(self):
        res = super(PurchaseOrder, self).button_approve()
        self._check_vendor_registration()
        self.button_submit_legal()
        return res
    
    #NOT TO BE USED YET AND DO NOT DELETE THIS 
    """@api.multi
    def button_approve(self):
        super(PurchaseOrder, self).button_approve()
        for order in self:
            for order_line in order.order_line:
                order_line.product_id.standard_price = order_line.price_unit
    """

    
    @api.multi
    def button_reset(self):
        self.mapped('order_line')
        self.write({'state': 'draft'})
        return {}
    
    '''
    @api.multi
    def copy(self, default=None):
        new_po = super(PurchaseOrder, self).copy(default=default)
        for line in new_po.order_line:
            seller = line.product_id._select_seller(
                partner_id=line.partner_id, quantity=line.product_qty,
                date=line.order_id.date_order and line.order_id.date_order[:10], uom_id=line.product_uom)
            line.date_planned = line._get_date_planned(seller)
            line.write({'need_override': False})
            line.write({'override_budget': False})
        return new_po
    '''
    
class PurchaseOrderLine(models.Model):
    _name = "purchase.order.line"
    _inherit = ['purchase.order.line']
    
    def _default_analytic(self):
        return self.env['account.analytic.account'].search([('name','=','sunray')])
    
    def _default_account(self):
        return self.product_id.property_account_expense_id
#     
#     @api.multi
#     @api.onchange('type')
#     def type_change(self):
#         self.product_id = False
    
    account_analytic_id = fields.Many2one('account.analytic.account', string='Analytic Account', required=False, default=_default_analytic, track_visibility="always")
    account_id = fields.Many2one('account.account', string='Account',  domain = [('user_type_id', 'in', [5,8,17,16])])
    need_override = fields.Boolean ('Need Budget Override', track_visibility="onchange", copy=False)
    override_budget = fields.Boolean ('Override Budget', track_visibility="onchange", copy=False)
    
    @api.multi
    def action_override_budget(self):
        self.write({'override_budget': True})
        if self.order_id.need_override == False:
            subject = "Budget Override Done, Purchase Order {} can be approved now".format(self.name)
            partner_ids = []
            for partner in self.order_id.message_partner_ids:
                partner_ids.append(partner.id)
            self.order_id.message_post(subject=subject,body=subject,partner_ids=partner_ids)

class PurchaseRequisition(models.Model):
    _name = "purchase.requisition"
    _inherit = ['purchase.requisition']
    
    #stock_source = fields.Char(string='Source document')
    store_request_id = fields.Many2one('stock.picking','Store Request', readonly=True, track_visibility='onchange')
    
class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    product_expiration_date = fields.Date(string='Product Expiration Date', track_visibility='onchange')
    
    @api.multi
    def send_expired_product_mail(self):
        test = False
        product = self.env['product.template'].search([])
        
        for self in product:
            if self.product_expiration_date:
                test = datetime.datetime.strptime(self.product_expiration_date, "%Y-%m-%d")
                
                birthday_day = test.day
                birthday_month = test.month
                
                today = datetime.datetime.now().strftime("%Y-%m-%d")
                
                test_today = datetime.datetime.today().strptime(today, "%Y-%m-%d")
                birthday_day_today = test_today.day
                birthday_month_today = test_today.month
                
                if birthday_month == birthday_month_today:
                    if birthday_day == birthday_day_today:
                        config = self.env['mail.template'].sudo().search([('name','=','Birthday Reminder')], limit=1)
                        mail_obj = self.env['mail.mail']
                        if config:
                            values = config.generate_email(self.id)
                            mail = mail_obj.create(values)
                            if mail:
                                mail.send()
                            return True
        return
    
    @api.multi
    def send_product_expiration_mail(self):

        product = self.env['product.template'].search([])
        
        current_dates = False
        
        for self in product:
            if self.product_expiration_date:
                
                current_dates = datetime.datetime.strptime(self.product_expiration_date, "%Y-%m-%d")
                current_datesz = current_dates - relativedelta(days=7)
                
                date_start_day = current_datesz.day
                date_start_month = current_datesz.month
                date_start_year = current_datesz.year
                
                today = datetime.datetime.now().strftime("%Y-%m-%d")
                
                test_today = datetime.datetime.today().strptime(today, "%Y-%m-%d")
                date_start_day_today = test_today.day
                date_start_month_today = test_today.month
                date_start_year_today = test_today.year
                
                
                if date_start_month == date_start_month_today:
                    if date_start_day == date_start_day_today:
                        if date_start_year == date_start_year_today:
                            config = self.env['mail.template'].sudo().search([('name','=','Confirmation')], limit=1)
                            mail_obj = self.env['mail.mail']
                            if config:
                                values = config.generate_email(self.id)
                                mail = mail_obj.create(values)
                                if mail:
                                    mail.send()
                                return True
        return

class SaleOrder(models.Model):
    _inherit = "sale.order"
    
    state = fields.Selection([
        ('draft', 'Quotation'),
        ('manager_approval', 'Management Approval'),
        ('sent', 'Quotation Sent'),
        ('sale', 'Sales Order'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled'),
        ], string='Status', readonly=True, copy=False, index=True, track_visibility='onchange', track_sequence=3, default='draft')
    
    need_management_approval = fields.Boolean('Needs Management Approval', track_visibility="onchange", copy=False, default=False)
    
    @api.multi
    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        self._check_approval()
        return res
    
    @api.depends('amount_total')
    def _check_approval(self):
        if self.amount_total > 180:
            self.need_management_approval = True
            group_id = self.env['ir.model.data'].xmlid_to_object('sunray.group_sale_account_budget')
            user_ids = []
            partner_ids = []
            for user in group_id.users:
                user_ids.append(user.id)
                partner_ids.append(user.partner_id.id)
            self.message_subscribe(partner_ids=partner_ids)
            subject = "Sales Order {} needs management approval".format(self.name)
            self.message_post(subject=subject,body=subject,partner_ids=partner_ids)
            return False
            raise ValidationError(_('Only your line manager can approve your leave request.'))
        else:
            self.need_approval = False
            
            
class SaleOrderLine(models.Model):
    _name = 'sale.order.line'
    _description = 'Sales Order Line'
    _inherit = ['sale.order.line']
    
    type = fields.Selection([('sale', 'Sale'), ('lease', 'Lease')], string='Type', required=True, default='sale')
    
class Project(models.Model):
    _name = "project.project"
    _inherit = ['project.project', 'mail.activity.mixin', 'rating.mixin']
    _description = "Project"
    
    def _default_analytic(self):
        return self.env['account.analytic.account'].search([('name','=','Sunray')])
    
    #def _default_account(self):
    #    return self.product_id.property_account_expense_id
    
    state = fields.Selection([
        ('kick_off', 'Kick off'),
        ('project_plan', 'Project plan'),
        ('supply_chain_project_execution', 'Supply Chain Project Execution'),
        ('qc_sign_off', 'Qc sign off'),
        ('customer_sign_off', 'Customer Sign off'),
        ('close_out', ' Close out'),
        ], string='Stage', readonly=False, index=True, copy=False, default='kick_off', track_visibility='onchange')
    
    checklist_count = fields.Integer(compute="_checklist_count",string="Checklist", store=False)
    
    action_count = fields.Integer(compute="_action_count",string="Action", store=False)
    
    issues_count = fields.Integer(compute="_issues_count",string="Issues", store=False)
    
    risk_count = fields.Integer(compute="_risk_count",string="Risks", store=False)

    ehs_count = fields.Integer(compute="_ehs_count",string="EHS", store=False)

    change_request_count = fields.Integer(compute="_change_request_count",string="Change Request", store=False)

    decision_count = fields.Integer(compute="_decision_count",string="Decision", store=False)
    
    mo_count = fields.Integer(compute="_mo_count",string="Manufacturing Orders", store=False)
    
    crm_lead_id = fields.Many2one(comodel_name='crm.lead', string='Lead')
    
    parent_project_id = fields.Many2one(comodel_name='project.project', string='Parent Project')
    
    account_analytic_id = fields.Many2one('account.analytic.account', string='Analytic Acount', required=False, default=_default_analytic, track_visibility="always")
    account_id = fields.Many2one('account.account', string='Account',  domain = [('user_type_id', 'in', [5,8,17,16])])
    
    monthly_maintenance_schedule = fields.Datetime(string="Monthly Maintenance Schedule", track_visibility="onchange")
    client_site_visit = fields.Datetime(string="Client Site Visit", track_visibility="onchange")
    internal_external_monthly = fields.Datetime(string="Internal External Monthly", track_visibility="onchange")
    
    lead_technician_id = fields.Many2one(comodel_name='res.users', string='Lead Technician')
    quality_assurance_id = fields.Many2one(comodel_name='res.users', string='Quality Assurance Engineer')
    
    project_engineers_id = fields.Many2many(comodel_name='res.users', string='Project Engineers', help="list of engineeers for this project")
    
    project_plan_file = fields.Binary(string='Project Plan', track_visibility="onchange", store=True)
    project_budget = fields.Float(string='Project Budget', track_visibility="onchange", store=True, related='crm_lead_id.budget')
    
    project_code_id = fields.Many2one(comodel_name='res.partner', string='Project Code', help="Client sub account code")
    
    
    @api.model
    def create(self, vals):
        result = super(Project, self).create(vals)
        result.send_project_commencement_mail()
        return result
    
    @api.multi
    def send_project_commencement_mail(self):
        config = self.env['mail.template'].sudo().search([('name','=','Project Commencement Email')], limit=1)
        mail_obj = self.env['mail.mail']
        if config:
            values = config.generate_email(self.id)
            mail = mail_obj.create(values)
            if mail:
                mail.send()
    
    @api.multi
    def _checklist_count(self):
        oe_checklist = self.env['project.checklist']
        for pa in self:
            domain = [('project_id', '=', pa.id)]
            pres_ids = oe_checklist.search(domain)
            pres = oe_checklist.browse(pres_ids)
            checklist_count = 0
            for pr in pres:
                checklist_count+=1
            pa.checklist_count = checklist_count
        return True
    
    @api.multi
    def _action_count(self):
        oe_checklist = self.env['project.action']
        for pa in self:
            domain = [('project_id', '=', pa.id)]
            pres_ids = oe_checklist.search(domain)
            pres = oe_checklist.browse(pres_ids)
            action_count = 0
            for pr in pres:
                action_count+=1
            pa.action_count = action_count
        return True
    
    @api.multi
    def _mo_count(self):
        oe_checklist = self.env['mrp.production']
        for pa in self:
            domain = [('project_id', '=', pa.id)]
            pres_ids = oe_checklist.search(domain)
            pres = oe_checklist.browse(pres_ids)
            action_count = 0
            for pr in pres:
                action_count+=1
            pa.action_count = action_count
        return True
    
    @api.multi
    def _issues_count(self):
        oe_checklist = self.env['project.issues']
        for pa in self:
            domain = [('project_id', '=', pa.id)]
            pres_ids = oe_checklist.search(domain)
            pres = oe_checklist.browse(pres_ids)
            issues_count = 0
            for pr in pres:
                issues_count+=1
            pa.issues_count = issues_count
        return True
    
    @api.multi
    def _risk_count(self):
        oe_checklist = self.env['project.risk']
        for pa in self:
                domain = [('project_id', '=', pa.id)]
                pres_ids = oe_checklist.search(domain)
                pres = oe_checklist.browse(pres_ids)
                risk_count = 0
                for pr in pres:
                    risk_count+=1
                pa.risk_count = risk_count
        return True



    @api.multi
    def _change_request_count(self):
        oe_checklist = self.env['project.change_request']
        for pa in self:
                domain = [('project_id', '=', pa.id)]
                pres_ids = oe_checklist.search(domain)
                pres = oe_checklist.browse(pres_ids)
                change_request_count = 0
                for pr in pres:
                    change_request_count+=1
                pa.change_request_count = change_request_count
        return True

    @api.multi
    def _ehs_count(self):
        oe_checklist = self.env['project.ehs']
        for pa in self:
                domain = [('project_id', '=', pa.id)]
                pres_ids = oe_checklist.search(domain)
                pres = oe_checklist.browse(pres_ids)
                ehs_count = 0
                for pr in pres:
                    ehs_count+=1
                pa.ehs_count = ehs_count
        return True

    @api.multi
    def _decision_count(self):
        oe_checklist = self.env['project.decision']
        for pa in self:
                domain = [('project_id', '=', pa.id)]
                pres_ids = oe_checklist.search(domain)
                pres = oe_checklist.browse(pres_ids)
                decision_count = 0
                for pr in pres:
                    decision_count+=1
                pa.decision_count = decision_count
        return True
    
    @api.multi
    def open_project_checklist(self):
        self.ensure_one()
        action = self.env.ref('sunray.sunray_project_checklist_action').read()[0]
        action['domain'] = literal_eval(action['domain'])
        action['domain'].append(('partner_id', 'child_of', self.partner_id.id))
        return action
    
    @api.multi
    def open_project_action(self):
        self.ensure_one()
        action = self.env.ref('sunray.sunray_project_actionform_action').read()[0]
        action['domain'] = literal_eval(action['domain'])
        action['domain'].append(('partner_id', 'child_of', self.partner_id.id))
        return action
    
    @api.multi
    def open_project_issues(self):
        self.ensure_one()
        action = self.env.ref('sunray.sunray_project_issuesform_action').read()[0]
        action['domain'] = literal_eval(action['domain'])
        action['domain'].append(('partner_id', 'child_of', self.partner_id.id))
        return action
    
    @api.multi
    def open_manfacturing_order(self):
        self.ensure_one()
        action = self.env.ref('sunray.sunray_mrp_production_action').read()[0]
        action['domain'] = literal_eval(action['domain'])
        action['domain'].append(('partner_id', 'child_of', self.partner_id.id))
        return action
    
    @api.multi
    def open_project_change_request(self):
        self.ensure_one()
        action = self.env.ref('sunray.sunray_project_change_request_form_action').read()[0]
        action['domain'] = literal_eval(action['domain'])
        action['domain'].append(('partner_id', 'child_of', self.partner_id.id))
        return action
    
    @api.multi
    def open_project_risk(self):
        self.ensure_one()
        action = self.env.ref('sunray.sunray_project_riskform_action').read()[0]
        action['domain'] = literal_eval(action['domain'])
        action['domain'].append(('partner_id', 'child_of', self.partner_id.id))
        return action

    @api.multi
    def open_project_decision(self):
        self.ensure_one()
        action = self.env.ref('sunray.sunray_project_decisionform_action').read()[0]
        action['domain'] = literal_eval(action['domain'])
        action['domain'].append(('partner_id', 'child_of', self.partner_id.id))
        return action    

    @api.multi
    def open_project_ehs(self):
        self.ensure_one()
        action = self.env.ref('sunray.sunray_project_ehsform_action').read()[0]
        action['domain'] = literal_eval(action['domain'])
        action['domain'].append(('partner_id', 'child_of', self.partner_id.id))
        return action
    
    @api.multi
    def send_monthly_maintenance_schedule_mail(self):
        employees = self.env['project.project'].search([])
        current_dates = False
        for self in employees:
            if self.monthly_maintenance_schedule:
                
                current_dates = datetime.datetime.strptime(self.monthly_maintenance_schedule, "%Y-%m-%d")
                current_datesz = current_dates - relativedelta(days=5)
                
                date_start_day = current_datesz.day
                date_start_month = current_datesz.month
                date_start_year = current_datesz.year
                
                today = datetime.datetime.now().strftime("%Y-%m-%d")
                
                test_today = datetime.datetime.today().strptime(today, "%Y-%m-%d")
                date_start_day_today = test_today.day
                date_start_month_today = test_today.month
                date_start_year_today = test_today.year
                
                if date_start_month == date_start_month_today:
                    if date_start_day == date_start_day_today:
                        if date_start_year == date_start_year_today:
                            config = self.env['mail.template'].sudo().search([('name','=','Monthly Maintenance Schedule')], limit=1)
                            mail_obj = self.env['mail.mail']
                            if config:
                                values = config.generate_email(self.id)
                                mail = mail_obj.create(values)
                                if mail:
                                    mail.send()
    
    @api.multi
    def send_client_site_visit_mail(self):
        employees = self.env['project.project'].search([])
        current_dates = False
        for self in employees:
            if self.client_site_visit:
                
                current_dates = datetime.datetime.strptime(self.client_site_visit, "%Y-%m-%d")
                current_datesz = current_dates - relativedelta(days=5)
                
                date_start_day = current_datesz.day
                date_start_month = current_datesz.month
                date_start_year = current_datesz.year
                
                today = datetime.datetime.now().strftime("%Y-%m-%d")
                
                test_today = datetime.datetime.today().strptime(today, "%Y-%m-%d")
                date_start_day_today = test_today.day
                date_start_month_today = test_today.month
                date_start_year_today = test_today.year
                
                if date_start_month == date_start_month_today:
                    if date_start_day == date_start_day_today:
                        if date_start_year == date_start_year_today:
                            config = self.env['mail.template'].sudo().search([('name','=','Client Site Visit')], limit=1)
                            mail_obj = self.env['mail.mail']
                            if config:
                                values = config.generate_email(self.id)
                                mail = mail_obj.create(values)
                                if mail:
                                    mail.send()
                                    
    @api.multi
    def send_client_site_visit_customer_mail(self):
        employees = self.env['project.project'].search([])
        current_dates = False
        for self in employees:
            if self.client_site_visit:
                
                current_dates = datetime.datetime.strptime(self.client_site_visit, "%Y-%m-%d")
                current_datesz = current_dates - relativedelta(days=5)
                
                date_start_day = current_datesz.day
                date_start_month = current_datesz.month
                date_start_year = current_datesz.year
                
                today = datetime.datetime.now().strftime("%Y-%m-%d")
                
                test_today = datetime.datetime.today().strptime(today, "%Y-%m-%d")
                date_start_day_today = test_today.day
                date_start_month_today = test_today.month
                date_start_year_today = test_today.year
                
                if date_start_month == date_start_month_today:
                    if date_start_day == date_start_day_today:
                        if date_start_year == date_start_year_today:
                            config = self.env['mail.template'].sudo().search([('name','=','Client Site Visit customer')], limit=1)
                            mail_obj = self.env['mail.mail']
                            if config:
                                values = config.generate_email(self.id)
                                mail = mail_obj.create(values)
                                if mail:
                                    mail.send()
                    
    @api.multi
    def send_internal_external_monthly_mail(self):
        employees = self.env['project.project'].search([])
        current_dates = False
        for self in employees:
            if self.internal_external_monthly:
                
                current_dates = datetime.datetime.strptime(self.internal_external_monthly, "%Y-%m-%d")
                current_datesz = current_dates - relativedelta(days=5)
                
                date_start_day = current_datesz.day
                date_start_month = current_datesz.month
                date_start_year = current_datesz.year
                
                today = datetime.datetime.now().strftime("%Y-%m-%d")
                
                test_today = datetime.datetime.today().strptime(today, "%Y-%m-%d")
                date_start_day_today = test_today.day
                date_start_month_today = test_today.month
                date_start_year_today = test_today.year
                
                if date_start_month == date_start_month_today:
                    if date_start_day == date_start_day_today:
                        if date_start_year == date_start_year_today:
                            config = self.env['mail.template'].sudo().search([('name','=','Internal External Monthly')], limit=1)
                            mail_obj = self.env['mail.mail']
                            if config:
                                values = config.generate_email(self.id)
                                mail = mail_obj.create(values)
                                if mail:
                                    mail.send()
    
    @api.multi
    def create_purchase_agreement(self):
        """
        Method to open create purchase agreement form
        """

        partner_id = self.partner_id
        #client_id = self.client_id
        #store_request_id = self.id
        #sub_account_id = self.sub_account_id
        #product_id = self.move_lines.product_id
             
        view_ref = self.env['ir.model.data'].get_object_reference('purchase_requisition', 'view_purchase_requisition_form')
        view_id = view_ref[1] if view_ref else False
        
        #purchase_line_obj = self.env['purchase.order.line']
        '''for subscription in self:
            order_lines = []
            for line in subscription.move_lines:
                order_lines.append((0, 0, {
                    'product_uom_id': line.product_id.uom_id.id,
                    'product_id': line.product_id.id,
                    'account_analytic_id': 1,
                    'product_qty': line.product_uom_qty,
                    'schedule_date': date.today(),
                    'price_unit': line.product_id.standard_price,
                }))
        ''' 
        res = {
            'type': 'ir.actions.act_window',
            'name': ('Purchase Agreement'),
            'res_model': 'purchase.requisition',
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': view_id,
            'target': 'current',
            'context': {'default_type_id': 2, 'default_origin': self.name}
        }
        
        return res
    
    @api.multi
    def create_manufacturing_order(self):
        """
        Method to open create purchase agreement form
        """

        partner_id = self.partner_id
        #client_id = self.client_id
        #store_request_id = self.id
        #sub_account_id = self.sub_account_id
        #product_id = self.move_lines.product_id
             
        view_ref = self.env['ir.model.data'].get_object_reference('mrp', 'mrp_production_form_view')
        view_id = view_ref[1] if view_ref else False
        
        #purchase_line_obj = self.env['purchase.order.line']
        '''for subscription in self:
            order_lines = []
            for line in subscription.move_lines:
                order_lines.append((0, 0, {
                    'product_uom_id': line.product_id.uom_id.id,
                    'product_id': line.product_id.id,
                    'account_analytic_id': 1,
                    'product_qty': line.product_uom_qty,
                    'schedule_date': date.today(),
                    'price_unit': line.product_id.standard_price,
                }))
        ''' 
        res = {
            'type': 'ir.actions.act_window',
            'name': ('Manufacturing Order'),
            'res_model': 'mrp.production',
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': view_id,
            'target': 'current',
            'context': {'default_origin': self.name}
        }
        
        return res
    
    
    @api.multi
    def create_store_request(self):
        """
        Method to open create purchase order form
        """

        #partner_id = self.request_client_id
        client_id = self.partner_id
        #sub_account_id = self.sub_account_id
        #product_id = self.move_lines.product_id
             
        view_ref = self.env['ir.model.data'].get_object_reference('sunray', 'sunray_stock_form_view')
        view_id = view_ref[1] if view_ref else False
        
        #purchase_line_obj = self.env['purchase.order.line']
        #for subscription in self:
        #    order_lines = []
        #    for line in subscription.move_raw_ids:
        #        order_lines.append((0, 0, {
        #            'name': line.product_id.name,
        #            'product_uom': line.product_id.uom_id.id,
        #            'product_id': line.product_id.id,
        #            'reserved_availability': line.reserved_availability,
        #            'product_uom_qty': line.product_uom_qty,
        #            'additional': True,
        #            'date_expected': date.today(),
        #            'price_cost': line.product_id.standard_price,
        #       }))
         
        res = {
            'type': 'ir.actions.act_window',
            'name': ('Store Request'),
            'res_model': 'stock.picking',
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': view_id,
            'target': 'current',
            'context': {'default_origin': self.name, 'default_client_id': client_id.id, "default_is_locked":False, "default_picking_type_id":self.env.ref("sunray.stock_picking_type_emp").id, 'default_partner_id': self.partner_id.id, 'default_project_id': self.id}
        }
        
        return res
    
class ProjectChecklist(models.Model):
    _name = "project.checklist"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    
    '''
    @api.multi
    def name_get(self):
        result = []
        for ticket in self:
            result.append((ticket.id, "%s (#%d)" % (ticket.ticket_id.name, ticket.id)))
        return result
    '''
    
    @api.model
    def _get_default_project(self):
        ctx = self._context
        if ctx.get('active_model') == 'project.project':
            return self.env['project.project'].browse(ctx.get('active_ids')[0]).id
  
    partner_id = fields.Many2one(comodel_name='res.partner', related='project_id.partner_id', string='Customer', readonly=True)
    
    project_id = fields.Many2one(comodel_name='project.project', string='Project', readonly=True, default=_get_default_project)
    
    detailed_site_review=fields.Boolean(
        string='Detailed site review'
    )
    detailed_system_design=fields.Boolean(
        string ='Detailed System design'
    )
    two_d_diagram=fields.Boolean(
        string="2D Diagram"
    )
    cable_schedule=fields.Boolean(
         string="Cable Schedule"
    )
    panel_layout=fields.Boolean(
        string="Panel Layout"
    )
    ancillary_equipment_breakdown=fields.Boolean(
        string="Ancillary Equipment breakdown"
    )
    
    project_schedule=fields.Boolean(
        string="Project Schedule"
    )
    purchase_stock_request_ancillaries_equipment=fields.Boolean(
         string="Purchase or stock request for ancillaries’ equipment"
    )
    
    project_planning_form = fields.Boolean(
        string='Project planning Form', 
    )
    
    communication_with_clients = fields.Boolean(
        string='Communication with clients', 
    )
    
    technician_assignment = fields.Boolean(
        string='Technician assignment', 
    )
    
    execution = fields.Boolean(
        string='Execution', 
    )
    
    quality_assurance = fields.Boolean(
        string='Quality Assurance', 
    )
    
    commissioning_test = fields.Boolean(
        string='Commissioning test', 
    )
    
    job_completion_certificate = fields.Boolean(
        string='Job Completion Certificate', 
    )
    
    training = fields.Boolean(
        string='Training', 
    )
    
    @api.multi
    def button_select_all(self):
        self.write({'detailed_site_review': True})
        self.write({'detailed_system_design': True})
        self.write({'two_d_diagram': True})
        self.write({'cable_schedule': True})
        self.write({'panel_layout': True})
        self.write({'ancillary_equipment_breakdown': True})
        self.write({'project_schedule': True})
        self.write({'purchase_stock_request_ancillaries_equipment': True})
        self.write({'project_planning_form': True})
        self.write({'communication_with_clients': True})
        self.write({'technician_assignment': True})
        self.write({'execution': True})
        self.write({'quality_assurance': True})
        self.write({'commissioning_test': True})
        self.write({'job_completion_certificate': True})
        self.write({'training': True})
        return {}
    
class Picking(models.Model):
    _name = "stock.picking"
    _inherit = 'stock.picking'
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submit', 'Submitted'),
        ('waiting', 'Waiting Another Operation'),
        ('confirmed', 'Waiting'),
        ('assigned', 'Ready'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', compute='_compute_state',
        copy=False, index=True, readonly=True, store=True, track_visibility='onchange',
        help=" * Draft: not confirmed yet and will not be scheduled until confirmed.\n"
             " * Waiting Another Operation: waiting for another move to proceed before it becomes automatically available (e.g. in Make-To-Order flows).\n"
             " * Waiting: if it is not ready to be sent because the required products could not be reserved.\n"
             " * Ready: products are reserved and ready to be sent. If the shipping policy is 'As soon as possible' this happens as soon as anything is reserved.\n"
             " * Done: has been processed, can't be modified or cancelled anymore.\n"
             " * Cancelled: has been cancelled, can't be confirmed anymore.")
    
    @api.multi
    def button_submit(self):
        self.write({'state': 'submit'})
        group_id = self.env['ir.model.data'].xmlid_to_object('sunray.group_hr_line_manager')
        user_ids = []
        partner_ids = []
        for user in group_id.users:
            user_ids.append(user.id)
            partner_ids.append(user.partner_id.id)
        self.message_subscribe(partner_ids=partner_ids)
        subject = "Store request {} needs approval".format(self.name)
        self.message_post(subject=subject,body=subject,partner_ids=partner_ids)
        return False
        return {}
    
    @api.multi
    def action_confirm(self):
        res = super(Picking, self).action_confirm()
        self.manager_confirm()
        group_id = self.env['ir.model.data'].xmlid_to_object('stock.group_stock_manager')
        user_ids = []
        partner_ids = []
        for user in group_id.users:
            user_ids.append(user.id)
            partner_ids.append(user.partner_id.id)
        self.message_subscribe(partner_ids=partner_ids)
        subject = "Store request {} has been approved by line manager".format(self.name)
        self.message_post(subject=subject,body=subject,partner_ids=partner_ids)
        return False
        return res
    
    @api.multi
    def manager_confirm(self):
        for order in self:
            order.write({'man_confirm': True})
        return True
    
    def _default_owner(self):
        return self.env.context.get('default_employee_id') or self.env['res.users'].browse(self.env.uid).partner_id
    
    def _default_employee(self):
        self.env['hr.employee'].search([('user_id','=',self.env.uid)])
        return self.env['hr.employee'].search([('user_id','=',self.env.uid)])
    
    owner_id = fields.Many2one('res.partner', 'Owner',
        states={'done': [('readonly', True)], 'cancel': [('readonly', True)]}, default=_default_owner,
        help="Default Owner")
    
    employee_id = fields.Many2one('hr.employee', 'Employee',
        states={'done': [('readonly', True)], 'cancel': [('readonly', True)]}, default=_default_employee,
        help="Default Owner")
    
    man_confirm = fields.Boolean('Manager Confirmation', track_visibility='onchange')
    #net_lot_id = fields.Many2one(string="Serial Number", related="move_line_ids.lot_id", readonly=True)
    internal_transfer = fields.Boolean('Internal Transfer?', track_visibility='onchange')
    client_id = fields.Many2one('res.partner', string='Client', index=True, ondelete='cascade', required=False)
    need_approval = fields.Boolean ('Need Approval', compute= "check_approval", track_visibility="onchange")
    #rejection_reason = fields.Many2one('stock.rejection.reason', string='Rejection Reason', index=True, track_visibility='onchange')
    
    project_id = fields.Many2one('project.project', string='Project', index=True, ondelete='cascade', required=False)
    
    total_price = fields.Float(string='Total', compute='_total_price', readonly=True, store=True)
    
    @api.depends('total_price')
    def check_approval(self):
        if self.total_price > 1800000:
            self.need_approval = True
            group_id = self.env['ir.model.data'].xmlid_to_object('stock.group_stock_manager')
            user_ids = []
            partner_ids = []
            for user in group_id.users:
                user_ids.append(user.id)
                partner_ids.append(user.partner_id.id)
            self.message_subscribe(partner_ids=partner_ids)
            subject = "Store request {} needs approval".format(self.name)
            self.message_post(subject=subject,body=subject,partner_ids=partner_ids)
            return False
        else:
            self.need_approval = False
    
    @api.multi
    def button_approve_srt(self):
        self.need_approval = False
        return {}
    
    @api.multi
    def button_reset(self):
        self.mapped('move_lines')._action_cancel()
        self.write({'state': 'draft'})
        return {}
    
    @api.model
    def create(self, vals):
        a = super(Picking, self).create(vals)
        a.send_store_request_mail()
        return a
        return super(Picking, self).create(vals)
    
    @api.multi
    def send_store_request_mail(self):
        if self.picking_type_id.name == "Staff Store Requests" and self.state in ['draft','waiting','confirmed']:
            group_id = self.env['ir.model.data'].xmlid_to_object('stock.group_stock_manager')
            user_ids = []
            partner_ids = []
            for user in group_id.users:
                user_ids.append(user.id)
                partner_ids.append(user.partner_id.id)
            self.message_subscribe(partner_ids=partner_ids)
            subject = "A new store request {} has been made".format(self.name)
            self.message_post(subject=subject,body=subject,partner_ids=partner_ids)
            return False
        return True
    
    @api.multi
    def send_store_request_done_mail(self):
        if self.state in ['done']:
            subject = "Store request {} has been approved and validated".format(self.name)
            partner_ids = []
            for partner in self.sheet_id.message_partner_ids:
                partner_ids.append(partner.id)
            self.sheet_id.message_post(subject=subject,body=subject,partner_ids=partner_ids)
    
    
    @api.multi
    def send_receipt_mail(self):
        if self.picking_type_id.name == "Receipts":
            config = self.env['mail.template'].sudo().search([('name','=','recieved')], limit=1)
            mail_obj = self.env['mail.mail']
            if config:
                values = config.generate_email(self.id)
                mail = mail_obj.create(values)
                if mail:
                    mail.send()
    
    @api.multi
    def create_purchase_order(self):
        """
        Method to open create purchase order form
        """

        partner_id = self.client_id
        client_id = self.client_id
        #store_request_id = self.id
        #sub_account_id = self.sub_account_id
        #product_id = self.move_lines.product_id
             
        view_ref = self.env['ir.model.data'].get_object_reference('purchase', 'purchase_order_form')
        view_id = view_ref[1] if view_ref else False
        
        #purchase_line_obj = self.env['purchase.order.line']
        for subscription in self:
            order_lines = []
            for line in subscription.move_lines:
                order_lines.append((0, 0, {
                    'name': line.product_id.name,
                    'product_uom': line.product_id.uom_id.id,
                    'product_id': line.product_id.id,
                    'account_id': line.account_id.id,
                    'product_qty': line.product_uom_qty,
                    'date_planned': date.today(),
                    'price_unit': line.product_id.standard_price,
                }))
         
        res = {
            'type': 'ir.actions.act_window',
            'name': ('Purchase Order'),
            'res_model': 'purchase.order',
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': view_id,
            'target': 'current',
            'context': {'default_client_id': client_id.id, 'default_stock_source': self.name, 'default_store_request_id': self.id, 'default_order_line': order_lines}
        }
        
        return res
    
    
    @api.multi
    def create_purchase_agreement(self):
        """
        Method to open create purchase agreement form
        """

        partner_id = self.client_id
        client_id = self.client_id
        #store_request_id = self.id
        #sub_account_id = self.sub_account_id
        #product_id = self.move_lines.product_id
             
        view_ref = self.env['ir.model.data'].get_object_reference('purchase_requisition', 'view_purchase_requisition_form')
        view_id = view_ref[1] if view_ref else False
        
        #purchase_line_obj = self.env['purchase.order.line']
        for subscription in self:
            order_lines = []
            for line in subscription.move_lines:
                order_lines.append((0, 0, {
                    'product_uom_id': line.product_id.uom_id.id,
                    'product_id': line.product_id.id,
                    'account_analytic_id': 1,
                    'product_qty': line.product_uom_qty,
                    'schedule_date': date.today(),
                    'price_unit': line.product_id.standard_price,
                }))
         
        res = {
            'type': 'ir.actions.act_window',
            'name': ('Purchase Agreement'),
            'res_model': 'purchase.requisition',
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': view_id,
            'target': 'current',
            'context': {'default_type_id': 2, 'default_origin': self.name, 'default_store_request_id': self.id, 'default_line_ids': order_lines}
        }
        
        return res
    
    @api.one
    @api.depends('move_lines.price_unit')
    def _total_price(self):
        total_unit = 0.0
        for line in self.move_lines:
            self.total_price += line.price_subtotal
    
class StockMove(models.Model):
    _inherit = "stock.move"
    
    @api.one
    @api.depends('product_uom_qty', 'price_cost')
    def _compute_subtotal(self):
        for line in self:
            self.price_subtotal = self.product_uom_qty * line.price_cost
    
    def _default_cost(self):
        return self.product_id.standard_price
    
    def _default_analytic(self):
        return self.env['account.analytic.account'].search([('name','=','Sunray')])
    
    @api.multi
    @api.onchange('product_id')
    def product_change(self):
        accounts_data = self.product_id.product_tmpl_id.get_product_accounts()
        if self.location_dest_id.valuation_in_account_id:
            acc_dest = self.location_dest_id.valuation_in_account_id.id
        else:
            acc_dest = accounts_data['stock_output'].id
        self.account_id = acc_dest
        
    @api.multi
    def _get_accounting_data_for_valuation(self):
        """ Return the accounts and journal to use to post Journal Entries for
        the real-time valuation of the quant. """
        self.ensure_one()
        accounts_data = self.product_id.product_tmpl_id.get_product_accounts()

        if self.location_id.valuation_out_account_id:
            acc_src = self.location_id.valuation_out_account_id.id
        else:
            acc_src = accounts_data['stock_input'].id

        if self.account_id:
            acc_dest = self.account_id.id
        elif self.location_dest_id.valuation_in_account_id:
            acc_dest = self.location_dest_id.valuation_in_account_id.id
        else:
            acc_dest = accounts_data['stock_output'].id

        acc_valuation = accounts_data.get('stock_valuation', False)
        if acc_valuation:
            acc_valuation = acc_valuation.id
        if not accounts_data.get('stock_journal', False):
            raise UserError(_('You don\'t have any stock journal defined on your product category, check if you have installed a chart of accounts'))
        if not acc_src:
            raise UserError(_('Cannot find a stock input account for the product %s. You must define one on the product category, or on the location, before processing this operation.') % (self.product_id.name))
        if not acc_dest:
            raise UserError(_('Cannot find a stock output account for the product %s. You must define one on the product category, or on the location, before processing this operation.') % (self.product_id.name))
        if not acc_valuation:
            raise UserError(_('You don\'t have any stock valuation account defined on your product category. You must define one before processing this operation.'))
        journal_id = accounts_data['stock_journal'].id
        return journal_id, acc_src, acc_dest, acc_valuation
    
#     @api.model
#     def _get_account_id(self):
#         accounts_data = self.product_id.product_tmpl_id.get_product_accounts()
#         print(accounts_data) 
#         if self.location_dest_id.valuation_in_account_id:
#             acc_dest = self.location_dest_id.valuation_in_account_id.id
#         else:
#             acc_dest = accounts_data['stock_output'].id
#         return acc_dest
        
    
    account_analytic_id = fields.Many2one('account.analytic.account', string='Analytic Acount', required=False, default=_default_analytic, track_visibility="always")
    account_id = fields.Many2one('account.account', string='Account', index=True, ondelete='cascade')
    
    price_cost = fields.Float(string="Cost", default=lambda self: self.product_id.standard_price)
    price_subtotal = fields.Float(string="Price Subtotal", compute="_compute_subtotal", readonly=True)
    
    
class MrpProduction(models.Model):
    _inherit = "mrp.production"    
    
    state = fields.Selection([
        ('unconfirmed', 'Unconfirmed'),
        ('confirmed', 'Confirmed'),
        ('planned', 'Planned'),
        ('progress', 'In Progress'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')], string='State',
        copy=False, default='unconfirmed', track_visibility='onchange')
    
    def _default_partner(self):
        return self.project_id.partner_id.id
    
    project_id = fields.Many2one(comodel_name='project.project', string='Projects')
    
    partner_id = fields.Many2one(comodel_name='res.partner', string='Customer', readonly=False, default=_default_partner)
    
    total_cost = fields.Float(string='Total Cost', compute='_total_cost', track_visibility='onchange', readonly=True)
    
    project_budget = fields.Float(string='Project Budget', related='project_id.project_budget', track_visibility='onchange', readonly=True)
    
    @api.model
    def create(self, vals):
        result = super(MrpProduction, self).create(vals)
        result.mrp_created()
        return result
    
    @api.multi
    def mrp_created(self):
        group_id = self.env['ir.model.data'].xmlid_to_object('sunray.group_head_projects','project.group_project_manager')
        user_ids = []
        partner_ids = []
        for user in group_id.users:
            user_ids.append(user.id)
            partner_ids.append(user.partner_id.id)
        self.message_subscribe(partner_ids=partner_ids)
        subject = "Manufacturing Order {} has been created and needs approval".format(self.name)
        self.message_post(subject=subject,body=subject,partner_ids=partner_ids)
        return {}
    
    @api.multi
    def button_mrp_approved(self):
        self.write({'state': 'confirmed'})
        subject = "Manufacturing Order {} has been approved".format(self.name)
        partner_ids = []
        for partner in self.message_partner_ids:
            partner_ids.append(partner.id)
        self.message_post(subject=subject,body=subject,partner_ids=partner_ids)
    
    @api.multi
    @api.depends('move_raw_ids.product_uom_qty')
    def _total_cost(self):
        for a in self:
            for line in a.move_raw_ids:
                a.total_cost += line.price_cost * line.product_uom_qty
                
    
    @api.multi
    def create_store_request(self):
        """
        Method to open create purchase order form
        """

        #partner_id = self.request_client_id
        #client_id = self.request_client_id
        #sub_account_id = self.sub_account_id
        #product_id = self.move_lines.product_id
             
        view_ref = self.env['ir.model.data'].get_object_reference('sunray', 'sunray_stock_form_view')
        view_id = view_ref[1] if view_ref else False
        
        #purchase_line_obj = self.env['purchase.order.line']
        for subscription in self:
            order_lines = []
            for line in subscription.move_raw_ids:
                order_lines.append((0, 0, {
                    'name': line.product_id.name,
                    'product_uom': line.product_id.uom_id.id,
                    'product_id': line.product_id.id,
                    'reserved_availability': line.reserved_availability,
                    'product_uom_qty': line.product_uom_qty,
                    'additional': True,
                    'date_expected': date.today(),
                    'price_cost': line.product_id.standard_price,
                }))
         
        res = {
            'type': 'ir.actions.act_window',
            'name': ('Store Request'),
            'res_model': 'stock.picking',
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': view_id,
            'target': 'current',
            'context': {'default_origin': self.name, "default_is_locked":False, "default_picking_type_id":self.env.ref("sunray.stock_picking_type_emp").id, 'default_move_lines': order_lines}
        }
        
        return res
    
    
    
             
    