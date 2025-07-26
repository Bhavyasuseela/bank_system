from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from decimal import Decimal, ROUND_HALF_UP
import uuid

class Customer(models.Model):
    customer_id = models.CharField(max_length=50, unique=True, primary_key=True)
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=15, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.customer_id} - {self.name}"

class Loan(models.Model):
    loan_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='loans')
    principal_amount = models.DecimalField(max_digits=12, decimal_places=2) # P
    loan_period_years = models.IntegerField() # N
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2) # R
    total_interest = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True) # I
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True) # A
    monthly_emi = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    remaining_balance = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    total_emis = models.IntegerField(null=True, blank=True)
    emis_paid = models.IntegerField(default=0)
    loan_status = models.CharField(max_length=20, choices=[
        ('ACTIVE', 'Active'),
        ('COMPLETED', 'Completed'),
        ('DEFAULTED', 'Defaulted')
    ], default='ACTIVE')
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        """Validate loan data"""
        if self.principal_amount and self.principal_amount <= 0:
            raise ValidationError("Principal amount must be positive")
        if self.loan_period_years and self.loan_period_years <= 0:
            raise ValidationError("Loan period must be positive")
        if self.interest_rate is not None and self.interest_rate < 0:
            raise ValidationError("Interest rate cannot be negative")

    def save(self, *args, **kwargs):
        # Calculate loan values if not already calculated
        if self.total_amount is None or self.total_interest is None:
            principal = Decimal(str(self.principal_amount))
            period = Decimal(str(self.loan_period_years))
            rate = Decimal(str(self.interest_rate))
            self.total_interest = (principal * period * rate / Decimal('100')).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            self.total_amount = (principal + self.total_interest).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            self.total_emis = int(self.loan_period_years * 12)
            if self.total_emis > 0:
                self.monthly_emi = (self.total_amount / Decimal(str(self.total_emis))).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP
                )
            else:
                self.monthly_emi = self.total_amount
            if self.remaining_balance is None:
                self.remaining_balance = self.total_amount

        # Always save updated values, but only skip validation if _skip_validation is set
        if hasattr(self, '_skip_validation'):
            super().save(*args, **kwargs)
            # Remove the flag after save to avoid issues in future saves
            if hasattr(self, '_skip_validation'):
                delattr(self, '_skip_validation')
        else:
            self.full_clean()
            super().save(*args, **kwargs)

    @property
    def emis_remaining(self):
        return max(0, self.total_emis - self.emis_paid)

    def __str__(self):
        return f"Loan {self.loan_id} - {self.customer.customer_id}"

class Payment(models.Model):
    PAYMENT_TYPES = [
        ('EMI', 'EMI Payment'),
        ('LUMP_SUM', 'Lump Sum Payment')
    ]
    
    payment_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='payments')
    payment_type = models.CharField(max_length=10, choices=PAYMENT_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateTimeField(auto_now_add=True)
    balance_after_payment = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    def clean(self):
        """Validate payment data"""
        if self.amount and self.amount <= 0:
            raise ValidationError("Payment amount must be positive")
        if self.loan:
            if self.loan.loan_status != 'ACTIVE':
                raise ValidationError("Cannot make payment on inactive loan")
            if self.amount and self.amount > self.loan.remaining_balance:
                raise ValidationError("Payment amount cannot exceed remaining balance")

    def save(self, *args, **kwargs):
        if not self.pk:  # New payment
            # Get the loan object
            loan = self.loan
            payment_amount = Decimal(str(self.amount))
            print(f"[DEBUG] Payment.save() called: payment_type={self.payment_type}, payment_amount={payment_amount}, loan_id={loan.loan_id}")
            print(f"[DEBUG] Before payment: amount_paid={loan.amount_paid}, remaining_balance={loan.remaining_balance}, emis_paid={loan.emis_paid}")

            # Validate payment
            if loan.loan_status != 'ACTIVE':
                print("[DEBUG] Loan not active!")
                raise ValidationError("Cannot make payment on inactive loan")
            if payment_amount > loan.remaining_balance:
                print("[DEBUG] Payment exceeds remaining balance!")
                raise ValidationError(f"Payment amount (₹{payment_amount}) exceeds remaining balance (₹{loan.remaining_balance})")

            # Update loan amounts
            loan.amount_paid = (Decimal(str(loan.amount_paid)) + payment_amount).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            loan.remaining_balance = (Decimal(str(loan.remaining_balance)) - payment_amount).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )

            # Ensure remaining balance doesn't go negative
            if loan.remaining_balance < Decimal('0.00'):
                loan.remaining_balance = Decimal('0.00')

            # Handle EMI vs Lump Sum logic - STRICT LOGIC
            if self.payment_type == 'EMI':
                # Only allow EMI payment if amount is exactly equal to monthly EMI
                if payment_amount != loan.monthly_emi:
                    print(f"[DEBUG] EMI payment not equal to monthly EMI! payment_amount={payment_amount}, monthly_emi={loan.monthly_emi}")
                    raise ValidationError(f"EMI payment must be exactly the monthly EMI amount (₹{loan.monthly_emi})")
                loan.emis_paid = min(loan.emis_paid + 1, loan.total_emis)
                print(f"[DEBUG] EMI payment processed. emis_paid now {loan.emis_paid}")
            else:  # LUMP_SUM
                # For lump sum, calculate how many EMIs this amount would cover
                if loan.monthly_emi > 0:
                    emis_covered = int(payment_amount // Decimal(str(loan.monthly_emi)))
                    loan.emis_paid = min(loan.emis_paid + emis_covered, loan.total_emis)
                    print(f"[DEBUG] Lump sum payment processed. emis_covered={emis_covered}, emis_paid now {loan.emis_paid}")

            # Check if loan is completed
            if loan.remaining_balance <= Decimal('0.01'):  # Using small threshold for floating point precision
                loan.loan_status = 'COMPLETED'
                loan.remaining_balance = Decimal('0.00')
                loan.emis_paid = loan.total_emis  # Mark all EMIs as paid when loan is completed
                print(f"[DEBUG] Loan completed!")

            # Set balance after payment
            self.balance_after_payment = loan.remaining_balance

            # Mark loan to skip validation during save to avoid conflicts
            loan._skip_validation = True

            # Save the loan
            loan.save()
            print(f"[DEBUG] After payment: amount_paid={loan.amount_paid}, remaining_balance={loan.remaining_balance}, emis_paid={loan.emis_paid}")

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Payment {self.payment_id} - ₹{self.amount}"