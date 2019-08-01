# -*- coding: utf-8 -*-
import datetime

from datetime import date, timedelta
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
    
    type = fields.Selection(
        [('contact', 'Contact'),
         ('invoice', 'Invoice address'),
         ('delivery', 'Shipping address'),
         ('other', 'Other address'),
         ("private", "Sub Account"),
        ], string='Address Type',
        default='contact',
        help="Used by Sales and Purchase Apps to select the relevant address depending on the context.")
    
    tax_compliance = fields.Selection([('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5')], string='Tax compliance', required=False)
    due_diligence_form = fields.Selection([('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5')], string='Due Diligence Form', required=False)
    cac = fields.Selection([('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5')], string='CAC', required=False)
    delivery_speed = fields.Selection([('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5')], string='Delivery Speed')
    
    overall_vendor_rating = fields.Selection([('0', '0'),('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5')], string='Overall Vendor Rating', required=False)
    
    parent_account_number = fields.Char(string='Parent Account Number', required=False, index=True, copy=False, store=True)
    
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
    
class PurchaseOrder(models.Model):
    _name = "purchase.order"
    _inherit = ['purchase.order']
    
    #@api.onchange('project_id')
    #def _onchange_partner_id(self):
    #    self.partner_id = self.project_id.partner_id
    #    return {}
    
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
    
    need_override = fields.Boolean ('Need Budget Override', compute= "_check_override", track_visibility="onchange")
    employee_id = fields.Many2one('hr.employee', 'Employee',
        states={'done': [('readonly', True)], 'cancel': [('readonly', True)]}, default=_default_employee)
    approval_date = fields.Date(string='Manager Approval Date', readonly=True, track_visibility='onchange')
    manager_approval = fields.Many2one('res.users','Manager Approval Name', readonly=True, track_visibility='onchange')
    client_id = fields.Many2one('res.partner','Client', track_visibility='onchange')
    
    project_id = fields.Many2one(comodel_name='project.project', string='Project')
    
    state = fields.Selection([
        ('draft', 'RFQ'),
        ('sent', 'RFQ Sent'),
        ('to approve', 'To Approve'),
        ('submit', 'Manager Approval'),
        ('purchase', 'Purchase Order'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled')
        ], string='Status', readonly=True, index=True, copy=False, default='draft', track_visibility='onchange')
    
    department_name = fields.Char(string="Department", related="employee_id.department_id.name", readonly=True)    
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
        return {}

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
            group_id = self.env['ir.model.data'].xmlid_to_object('netcom.group_sale_account_budget')
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
            if self._check_budget() == False and self.need_override:
                return {}
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
    need_override = fields.Boolean ('Need Budget Override', track_visibility="onchange")
    override_budget = fields.Boolean ('Override Budget', track_visibility="onchange")
    
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

class SaleOrderLine(models.Model):
    _name = 'sale.order.line'
    _description = 'Sales Order Line'
    _inherit = ['sale.order.line']
    
    type = fields.Selection([('sale', 'Sale'), ('lease', 'Lease')], string='Type', required=True, default='sale')
    
class Project(models.Model):
    _name = "project.project"
    _inherit = "project.project"
    _description = "Project"
    
    def _default_analytic(self):
        return self.env['account.analytic.account'].search([('name','=','Sunray')])
    
    #def _default_account(self):
    #    return self.product_id.property_account_expense_id
    
    checklist_count = fields.Integer(compute="_checklist_count",string="Checklist", store=False)
    
    crm_lead_id = fields.Many2one(comodel_name='crm.lead', string='Lead')
    
    parent_project_id = fields.Many2one(comodel_name='project.project', string='Parent Project')
    
    account_analytic_id = fields.Many2one('account.analytic.account', string='Analytic Account', required=False, default=_default_analytic, track_visibility="always")
    account_id = fields.Many2one('account.account', string='Account',  domain = [('user_type_id', 'in', [5,8,17,16])])
    
    monthly_maintenance_schedule = fields.Date(string="Monthly Maintenance Schedule", track_visibility="onchange")
    client_site_visit = fields.Date(string="Client Site Visit", track_visibility="onchange")
    internal_external_monthly = fields.Date(string="Internal External Monthly", track_visibility="onchange")
    
    lead_technician_id = fields.Many2one(comodel_name='res.users', string='Lead Tecnician')
    quality_assurance_id = fields.Many2one(comodel_name='res.users', string='Quality Assurance Engineer')
    
    project_engineers_id = fields.Many2many(comodel_name='res.users', string='Project Engineers', help="list of engineeers for this project")
    
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
    def open_project_checklist(self):
        self.ensure_one()
        action = self.env.ref('sunray.sunray_project_checklist_action').read()[0]
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
        
    
    account_id = fields.Many2one('account.account', string='Account', index=True, ondelete='cascade')
    
    price_cost = fields.Float(string="Cost", default=_default_cost)
    price_subtotal = fields.Float(string="Price Subtotal", compute="_compute_subtotal", readonly=True)
    
    
    
    
    
    
    
    