from rest_framework import serializers
from .models import Customer, Loan, Payment
from decimal import Decimal

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = '__all__'

class LoanCreateSerializer(serializers.Serializer):
    customer_id = serializers.CharField(max_length=50)
    principal_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    loan_period_years = serializers.IntegerField()
    interest_rate = serializers.DecimalField(max_digits=5, decimal_places=2)

    def validate_customer_id(self, value):
        if not Customer.objects.filter(customer_id=value).exists():
            raise serializers.ValidationError("Customer does not exist.")
        return value


    class Meta:
        model = Loan
        fields = [
            'loan_id', 'customer_id', 'customer_name', 'principal_amount', 'loan_period_years',
            'interest_rate', 'total_interest', 'total_amount', 'monthly_emi', 'amount_paid',
            'remaining_balance', 'total_emis', 'emis_paid', 'emis_remaining', 'loan_status', 'created_at'
        ]

    def get_emis_remaining(self, obj):
        return obj.emis_remaining


class LoanResponseSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    emis_remaining = serializers.IntegerField(read_only=True)

    class Meta:
        model = Loan
        fields = [
            'loan_id', 'customer_name', 'principal_amount', 'loan_period_years',
            'interest_rate', 'total_interest', 'total_amount', 'monthly_emi',
            'amount_paid', 'remaining_balance', 'total_emis', 'emis_paid',
            'emis_remaining', 'loan_status', 'created_at'
        ]

class PaymentCreateSerializer(serializers.Serializer):
    loan_id = serializers.UUIDField()
    payment_type = serializers.ChoiceField(choices=['EMI', 'LUMP_SUM'])
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))

    def validate(self, data):
        """Cross-field validation"""
        try:
            loan = Loan.objects.get(loan_id=data['loan_id'])
            
            if loan.loan_status != 'ACTIVE':
                raise serializers.ValidationError("Cannot make payment on inactive loan")
            
            if loan.remaining_balance is None or loan.remaining_balance <= 0:
                raise serializers.ValidationError("Loan has no remaining balance")
                
            if data['amount'] > loan.remaining_balance:
                raise serializers.ValidationError(
                    f"Payment amount (₹{data['amount']}) exceeds remaining balance (₹{loan.remaining_balance})"
                )
            
            # Additional validation for EMI payments
            if data['payment_type'] == 'EMI':
                # Check if all EMIs are already paid
                if loan.emis_paid >= loan.total_emis:
                    raise serializers.ValidationError("All EMIs have already been paid")
                
        except Loan.DoesNotExist:
            raise serializers.ValidationError("Loan not found")
            
        return data

class PaymentSerializer(serializers.ModelSerializer):
    loan_id = serializers.UUIDField(source='loan.loan_id', read_only=True)
    emis_remaining = serializers.SerializerMethodField()
    emis_paid = serializers.SerializerMethodField()
    total_emis = serializers.SerializerMethodField()
    loan_status = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            'payment_id', 'loan_id', 'payment_type', 'amount', 'payment_date',
            'balance_after_payment', 'emis_remaining', 'emis_paid', 'total_emis', 'loan_status'
        ]

    def get_emis_remaining(self, obj):
        return obj.loan.emis_remaining

    def get_emis_paid(self, obj):
        return obj.loan.emis_paid

    def get_total_emis(self, obj):
        return obj.loan.total_emis

    def get_loan_status(self, obj):
        return obj.loan.loan_status