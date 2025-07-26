from django.contrib import admin
from .models import Customer, Loan, Payment

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['customer_id', 'name', 'email', 'created_at']
    search_fields = ['customer_id', 'name', 'email']

@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ['loan_id', 'customer', 'principal_amount', 'total_amount', 'remaining_balance', 'loan_status']
    list_filter = ['loan_status', 'created_at']
    search_fields = ['loan_id', 'customer__customer_id']

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['payment_id', 'loan', 'payment_type', 'amount', 'payment_date']
    list_filter = ['payment_type', 'payment_date']
    search_fields = ['payment_id', 'loan__loan_id']