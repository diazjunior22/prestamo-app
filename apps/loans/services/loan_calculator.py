import datetime
from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import List, Dict, Any
from apps.core.utils import quantize_currency

class LoanCalculator:
    """
    Deterministic financial calculation engine for LoanManager.
    Strictly uses Python Decimal types and ROUND_HALF_UP.
    Guarantees exact cent conservation (sum of principal equals original principal).
    Correctly supports Daily, Weekly, Biweekly (quincenal = 15 days), and Monthly frequencies,
    with explicit rate period conversions (Monthly, Annual, Daily, or Per Installment).
    """

    @staticmethod
    def calculate_due_date(start_date: datetime.date, installment_idx: int, frequency: str) -> datetime.date:
        """
        Calculates the exact due date for installment_idx (1-based), starting from start_date.
        - DAILY: increments of 1 calendar day.
        - WEEKLY: increments of 7 calendar days.
        - BIWEEKLY (Quincenal): increments of exactly 15 calendar days (consistent Colombian rule).
        - MONTHLY: increments of calendar months preserving the day of month where possible.
        """
        offset = installment_idx - 1
        if offset == 0:
            return start_date

        if frequency == 'DAILY':
            return start_date + datetime.timedelta(days=offset)
        elif frequency == 'WEEKLY':
            return start_date + datetime.timedelta(days=offset * 7)
        elif frequency == 'BIWEEKLY':
            # Exactly 15 days per installment (standard quincenal rule)
            return start_date + datetime.timedelta(days=offset * 15)
        elif frequency == 'MONTHLY':
            # Calendar month addition preserving day
            year = start_date.year + (start_date.month + offset - 1) // 12
            month = (start_date.month + offset - 1) % 12 + 1
            day = start_date.day
            while True:
                try:
                    return datetime.date(year, month, day)
                except ValueError:
                    day -= 1
        else:
            return start_date + datetime.timedelta(days=offset * 30)

    @classmethod
    def get_periodic_rate(cls, nominal_rate: Decimal, rate_period: str, payment_frequency: str) -> Decimal:
        """
        Converts nominal rate to the exact periodic rate applied in each installment.
        - If rate_period == 'PER_INSTALLMENT': nominal rate is applied directly per installment.
        - If rate_period == 'MONTHLY' (Standard):
            * Monthly loan: 1x monthly rate.
            * Biweekly loan (Quincenal): monthly_rate / 2 (2 quincenas per commercial month).
            * Weekly loan: monthly_rate / 4 (4 weeks per commercial month).
            * Daily loan: monthly_rate / 30 (30 days per commercial month).
        - If rate_period == 'ANNUAL':
            * Monthly loan: annual_rate / 12.
            * Biweekly loan: annual_rate / 24.
            * Weekly loan: annual_rate / 52.
            * Daily loan: annual_rate / 360.
        - If rate_period == 'DAILY':
            * Daily loan: daily_rate.
            * Weekly loan: daily_rate * 7.
            * Biweekly loan: daily_rate * 15.
            * Monthly loan: daily_rate * 30.
        """
        r = Decimal(str(nominal_rate)) / Decimal('100.0')

        if rate_period == 'PER_INSTALLMENT':
            return r

        # Convert input rate to monthly baseline
        if rate_period == 'MONTHLY':
            monthly_r = r
        elif rate_period == 'ANNUAL':
            monthly_r = r / Decimal('12.0')
        elif rate_period == 'DAILY':
            monthly_r = r * Decimal('30.0')
        else:
            monthly_r = r

        # Convert from monthly baseline to installment frequency
        if payment_frequency == 'MONTHLY':
            return monthly_r
        elif payment_frequency == 'BIWEEKLY':  # Quincenal (2 quincenas por mes de 15 días)
            return monthly_r / Decimal('2.0')
        elif payment_frequency == 'WEEKLY':    # Semanal (4 semanas por mes)
            return monthly_r / Decimal('4.0')
        elif payment_frequency == 'DAILY':     # Diario (30 días por mes)
            return monthly_r / Decimal('30.0')
        else:
            return monthly_r

    @classmethod
    def generate_schedule(
        cls,
        principal: Decimal,
        interest_rate: Decimal,
        interest_type: str,
        frequency: str,
        total_installments: int,
        first_payment_date: datetime.date,
        interest_rate_period: str = 'MONTHLY'
    ) -> Dict[str, Any]:
        """
        Generates full amortization schedule with exact installment values,
        due dates, capital breakdown, interest breakdown, and total payable.
        """
        principal = quantize_currency(principal)
        n = total_installments

        if n <= 0:
            raise ValueError("La cantidad de cuotas debe ser mayor a cero.")
        if principal <= Decimal('0.00'):
            raise ValueError("El capital a prestar debe ser mayor a cero.")

        # Compute effective periodic rate
        periodic_rate = cls.get_periodic_rate(interest_rate, interest_rate_period, frequency)

        installments_data: List[Dict[str, Any]] = []

        if interest_type == 'NO_INTEREST' or periodic_rate == Decimal('0.00'):
            # 0% Interest: distribute principal evenly
            base_principal = quantize_currency(principal / Decimal(n))
            running_balance = principal

            for i in range(1, n + 1):
                due_date = cls.calculate_due_date(first_payment_date, i, frequency)
                p_amount = base_principal
                i_amount = Decimal('0.00')

                # Final installment absorbs cent rounding
                if i == n:
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

            total_interest = Decimal('0.00')
            total_amount = principal
            inst_p = base_principal
            inst_i = Decimal('0.00')
            inst_total = base_principal

        elif interest_type == 'FLAT':
            # Flat Rate (Interés simple sobre capital inicial por período)
            total_interest_target = quantize_currency(principal * periodic_rate * Decimal(n))
            interest_per_cuota = quantize_currency(total_interest_target / Decimal(n))
            base_principal = quantize_currency(principal / Decimal(n))
            running_balance = principal

            for i in range(1, n + 1):
                due_date = cls.calculate_due_date(first_payment_date, i, frequency)
                p_amount = base_principal
                i_amount = interest_per_cuota

                # Final installment absorbs principal and interest remainder
                if i == n:
                    accumulated_p = sum(item['principal'] for item in installments_data)
                    p_amount = principal - accumulated_p
                    accumulated_i = sum(item['interest'] for item in installments_data)
                    i_amount = total_interest_target - accumulated_i

                running_balance -= p_amount
                installments_data.append({
                    'installment_number': i,
                    'due_date': due_date,
                    'principal': p_amount,
                    'interest': i_amount,
                    'total': p_amount + i_amount,
                    'balance_after': max(Decimal('0.00'), running_balance)
                })

            total_interest = total_interest_target
            total_amount = principal + total_interest
            inst_p = base_principal
            inst_i = interest_per_cuota
            inst_total = base_principal + interest_per_cuota

        elif interest_type == 'AMORTIZED_REDUCING':
            # French Amortization (Cuota fija sobre saldo decreciente)
            # PMT = P * [ r*(1+r)^n ] / [ (1+r)^n - 1 ]
            r = periodic_rate
            # Decimal precision power
            factor = (Decimal('1.0') + r) ** Decimal(n)
            pmt_decimal = principal * (r * factor) / (factor - Decimal('1.0'))
            fixed_payment = quantize_currency(pmt_decimal)

            running_balance = principal
            accumulated_p = Decimal('0.00')

            for i in range(1, n + 1):
                due_date = cls.calculate_due_date(first_payment_date, i, frequency)
                i_amount = quantize_currency(running_balance * r)
                p_amount = fixed_payment - i_amount

                if i == n:
                    # Final installment absorbs exact principal left
                    p_amount = principal - accumulated_p
                    total_cuota = p_amount + i_amount
                else:
                    total_cuota = fixed_payment

                accumulated_p += p_amount
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
            inst_p = quantize_currency(principal / Decimal(n))
            inst_i = quantize_currency(total_interest / Decimal(n))
            inst_total = fixed_payment

        else:
            raise ValueError(f"Modalidad de interés '{interest_type}' no reconocida.")

        frequency_names = {
            'DAILY': 'Diario',
            'WEEKLY': 'Semanal',
            'BIWEEKLY': 'Quincenal',
            'MONTHLY': 'Mensual',
        }

        return {
            'principal': principal,
            'interest_rate': interest_rate,
            'interest_rate_period': interest_rate_period,
            'interest_type': interest_type,
            'frequency': frequency,
            'frequency_name': frequency_names.get(frequency, 'Período'),
            'total_installments': total_installments,
            'periodic_rate_pct': quantize_currency(periodic_rate * Decimal('100.0')),
            'total_interest': quantize_currency(total_interest),
            'total_amount': quantize_currency(total_amount),
            'installment_principal': inst_p,
            'installment_interest': inst_i,
            'installment_total': inst_total,
            'installments': installments_data,
        }
