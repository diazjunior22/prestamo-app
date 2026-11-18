import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any
from apps.core.utils import quantize_currency

class LoanCalculator:
    """
    Deterministic financial engine for loan amortization.
    Strictly uses Decimal types and ROUND_HALF_UP.
    Guarantees that the sum of principal across all installments
    equals the initial principal exactly, absorbing rounding differences
    in the final installment.
    """

    @staticmethod
    def calculate_due_date(start_date: datetime.date, installment_idx: int, frequency: str) -> datetime.date:
        """
        Calculates the due date for installment_idx (1-based) starting from start_date.
        """
        offset = installment_idx - 1
        if offset == 0:
            return start_date

        if frequency == 'DAILY':
            return start_date + datetime.timedelta(days=offset)
        elif frequency == 'WEEKLY':
            return start_date + datetime.timedelta(weeks=offset)
        elif frequency == 'BIWEEKLY':
            return start_date + datetime.timedelta(days=offset * 14)
        elif frequency == 'MONTHLY':
            # Add months preserving day where possible
            year = start_date.year + (start_date.month + offset - 1) // 12
            month = (start_date.month + offset - 1) % 12 + 1
            day = start_date.day
            # Adjust for months with fewer days (e.g. Feb 30 -> Feb 28)
            while True:
                try:
                    return datetime.date(year, month, day)
                except ValueError:
                    day -= 1
        else:
            # Fallback monthly
            return start_date + datetime.timedelta(days=offset * 30)

    @classmethod
    def generate_schedule(
        cls,
        principal: Decimal,
        interest_rate: Decimal,
        interest_type: str,
        frequency: str,
        total_installments: int,
        first_payment_date: datetime.date
    ) -> Dict[str, Any]:
        """
        Generates full amortization schedule, total interest, and total payable amount.
        """
        principal = quantize_currency(principal)
        rate_decimal = Decimal(str(interest_rate)) / Decimal('100.0')
        n = total_installments

        if n <= 0:
            raise ValueError("El número de cuotas debe ser mayor a cero.")
        if principal <= Decimal('0.00'):
            raise ValueError("El capital debe ser mayor a cero.")

        installments_data: List[Dict[str, Any]] = []

        if interest_type == 'NO_INTEREST' or rate_decimal == Decimal('0.00'):
            # 0% Interest
            base_principal = quantize_currency(principal / Decimal(n))
            running_balance = principal

            for i in range(1, n + 1):
                due_date = cls.calculate_due_date(first_payment_date, i, frequency)
                p_amount = base_principal
                i_amount = Decimal('0.00')

                # On last installment, absorb remainder
                if i == n:
                    accumulated = sum(item['principal'] for item in installments_data)
                    p_amount = principal - accumulated

                running_balance -= p_amount
                installments_data.append({
                    'installment_number': i,
                    'due_date': due_date,
                    'principal': p_amount,
                    'interest': i_amount,
                    'total': p_amount + i_amount,
                    'balance_after': max(Decimal('0.00'), running_balance)
                })

            total_interest = Decimal('0.00')
            total_amount = principal

        elif interest_type == 'FLAT':
            # Flat Rate: Interest is calculated per period on original principal
            interest_per_installment = quantize_currency(principal * rate_decimal)
            base_principal = quantize_currency(principal / Decimal(n))
            total_interest = interest_per_installment * Decimal(n)
            total_amount = principal + total_interest
            running_balance = principal

            for i in range(1, n + 1):
                due_date = cls.calculate_due_date(first_payment_date, i, frequency)
                p_amount = base_principal
                i_amount = interest_per_installment

                if i == n:
                    # Final installment absorption
                    accumulated_p = sum(item['principal'] for item in installments_data)
                    p_amount = principal - accumulated_p

                running_balance -= p_amount
                installments_data.append({
                    'installment_number': i,
                    'due_date': due_date,
                    'principal': p_amount,
                    'interest': i_amount,
                    'total': p_amount + i_amount,
                    'balance_after': max(Decimal('0.00'), running_balance)
                })

        elif interest_type == 'AMORTIZED_REDUCING':
            # French Amortization (Cuota Fija sobre saldo decreciente)
            # PMT = P * [ r*(1+r)^n ] / [ (1+r)^n - 1 ]
            r = float(rate_decimal)
            p_float = float(principal)
            factor = (1.0 + r) ** n
            pmt_float = p_float * (r * factor) / (factor - 1.0)
            fixed_payment = quantize_currency(Decimal(str(pmt_float)))

            running_balance = principal
            accumulated_p = Decimal('0.00')
            accumulated_i = Decimal('0.00')

            for i in range(1, n + 1):
                due_date = cls.calculate_due_date(first_payment_date, i, frequency)
                i_amount = quantize_currency(running_balance * rate_decimal)
                p_amount = fixed_payment - i_amount

                if i == n:
                    # Last installment absorbs exact principal left
                    p_amount = principal - accumulated_p
                    total_cuota = p_amount + i_amount
                else:
                    total_cuota = fixed_payment

                accumulated_p += p_amount
                accumulated_i += i_amount
                running_balance -= p_amount

                installments_data.append({
                    'installment_number': i,
                    'due_date': due_date,
                    'principal': p_amount,
                    'interest': i_amount,
                    'total': total_cuota,
                    'balance_after': max(Decimal('0.00'), running_balance)
                })

            total_interest = sum(item['interest'] for item in installments_data)
            total_amount = principal + total_interest

        else:
            raise ValueError(f"Modalidad de interés '{interest_type}' no reconocida.")

        return {
            'principal': principal,
            'interest_rate': interest_rate,
            'interest_type': interest_type,
            'frequency': frequency,
            'total_installments': total_installments,
            'total_interest': quantize_currency(total_interest),
            'total_amount': quantize_currency(total_amount),
            'installments': installments_data,
        }

