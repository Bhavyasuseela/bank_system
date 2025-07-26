from django.urls import path
from . import views

urlpatterns = [
    path('customer/create/', views.create_customer, name='create_customer'),
    path('lend/', views.lend_loan, name='lend_loan'),  # Changed to match /api/lend/
    path('payment/', views.make_payment, name='make_payment'),
    path('ledger/<uuid:loan_id>/', views.loan_ledger, name='loan_ledger'),
    path('overview/<str:customer_id>/', views.account_overview, name='account_overview'),
]