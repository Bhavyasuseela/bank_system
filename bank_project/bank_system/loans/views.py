from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db import transaction
from .models import Customer, Loan, Payment
from .serializers import (
    CustomerSerializer, LoanCreateSerializer, LoanResponseSerializer,
    PaymentCreateSerializer, PaymentSerializer
)

@api_view(['POST'])
def create_customer(request):
    """Create a new customer"""
    serializer = CustomerSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response({
            'message': 'Customer created successfully',
            'customer': serializer.data
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@transaction.atomic
def lend_loan(request):
    """LEND: Create a new loan for a customer"""

    # Use the simpler serializer to validate request
    serializer = LoanCreateSerializer(data=request.data)

    if serializer.is_valid():
        customer_id = serializer.validated_data['customer_id']
        principal_amount = serializer.validated_data['principal_amount']
        loan_period_years = serializer.validated_data['loan_period_years']
        interest_rate = serializer.validated_data['interest_rate']

        try:
            # Get the customer object
            customer = Customer.objects.get(customer_id=customer_id)
            loan = Loan.objects.create(
                customer=customer,
                principal_amount=principal_amount,
                loan_period_years=loan_period_years,
                interest_rate=interest_rate
            )
            loan.refresh_from_db()

            response_serializer = LoanResponseSerializer(loan)
            response_data = response_serializer.data
            response_data['message'] = 'Loan created successfully'
            return Response(response_data, status=status.HTTP_201_CREATED)

        except Customer.DoesNotExist:
            return Response({'error': f'Customer {customer_id} not found.'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    return Response(serializer.errors, status=400)

@api_view(['POST'])
@transaction.atomic
def make_payment(request):
    """PAYMENT: Make a payment towards a loan"""

    serializer = PaymentCreateSerializer(data=request.data)

    if serializer.is_valid():
        loan_id = serializer.validated_data['loan_id']
        payment_type = serializer.validated_data['payment_type']
        amount = serializer.validated_data['amount']

        try:
            # Lock the loan record during payment processing
            loan = Loan.objects.select_for_update().get(loan_id=loan_id)

            # Create the payment
            payment = Payment.objects.create(
                loan=loan,
                payment_type=payment_type,
                amount=amount
            )

            # Refresh loan object to reflect new values
            loan.refresh_from_db()

            # Serialize the payment
            response_serializer = PaymentSerializer(payment)

            # Prepare response with additional fields
            return Response({
                **response_serializer.data,
                'loan_id': str(loan.loan_id),
                'payment_type': payment_type,
                'amount_paid': str(amount),
                'remaining_balance': str(loan.remaining_balance),
                'emis_remaining': loan.emis_remaining,
                'emis_paid': loan.emis_paid,
                'total_emis': loan.total_emis,
                'loan_status': loan.loan_status,
                'message': 'Payment processed successfully'
            }, status=status.HTTP_201_CREATED)

        except Loan.DoesNotExist:
            return Response({'error': 'Loan not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {'error': f'Failed to process payment: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def loan_ledger(request, loan_id):
    """LEDGER: Get all transactions for a loan"""
    try:
        loan = Loan.objects.get(loan_id=loan_id)
    except Loan.DoesNotExist:
        return Response({'error': 'Loan not found'}, status=status.HTTP_404_NOT_FOUND)
    
    payments = Payment.objects.filter(loan=loan).order_by('payment_date')
    payments_data = PaymentSerializer(payments, many=True).data
    
    response_data = {
        'loan_id': str(loan_id),
        'customer_id': loan.customer.customer_id,
        'customer_name': loan.customer.name,
        'principal_amount': str(loan.principal_amount),
        'total_amount': str(loan.total_amount),
        'monthly_emi': str(loan.monthly_emi),
        'remaining_balance': str(round(loan.remaining_balance, 2)),
        'emis_remaining': loan.emis_remaining,
        'emis_paid': loan.emis_paid,
        'total_emis': loan.total_emis,
        'amount_paid': str(round(loan.amount_paid, 2)),
        'loan_status': loan.loan_status,
        'total_transactions': payments.count(),
        'transactions': payments_data
    }
    
    return Response(response_data, status=status.HTTP_200_OK)

@api_view(['GET'])
def account_overview(request, customer_id):
    """ACCOUNT OVERVIEW: Get all loans for a customer"""

    try:
        customer = Customer.objects.get(customer_id=customer_id)
    except Customer.DoesNotExist:
        return Response({'error': 'Customer not found'}, status=status.HTTP_404_NOT_FOUND)

    loans = Loan.objects.filter(customer=customer).order_by('-created_at')
    loans_data = LoanResponseSerializer(loans, many=True).data

    # Calculate summary
    total_principal = sum(loan.principal_amount for loan in loans)
    total_amount_all_loans = sum(loan.total_amount for loan in loans)
    total_remaining = sum(loan.remaining_balance for loan in loans)
    total_paid = sum(loan.amount_paid for loan in loans)
    active_loans = loans.filter(loan_status='ACTIVE').count()
    completed_loans = loans.filter(loan_status='COMPLETED').count()

    response_data = {
        'customer_id': customer.customer_id,
        'customer_name': customer.name,
        'customer_email': customer.email,
        'total_loans': loans.count(),
        'active_loans': active_loans,
        'completed_loans': completed_loans,
        'total_principal_amount': str(total_principal),
        'total_amount_all_loans': str(total_amount_all_loans),
        'total_amount_paid': str(total_paid),
        'total_remaining_balance': str(total_remaining),
        'loans': loans_data
    }

    return Response(response_data, status=status.HTTP_200_OK)
