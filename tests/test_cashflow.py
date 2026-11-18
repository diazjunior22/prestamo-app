from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.cashflow.models import CashAccount, CashMovement, CashReconciliation
from apps.cashflow.services.cashflow_service import CashflowService

User = get_user_model()

class CashflowTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser(
            email='admin_cash@test.local',
            username='admin_cash',
            password='Password123!',
            first_name='Admin',
            last_name='Cash'
        )
        self.client.login(email='admin_cash@test.local', password='Password123!')

        # Ensure default pockets exist
        CashAccount.ensure_default_accounts()
        self.acc_cash = CashAccount.objects.get(account_type=CashAccount.AccountType.CASH)
        self.acc_nequi = CashAccount.objects.get(account_type=CashAccount.AccountType.NEQUI)
        self.acc_nu = CashAccount.objects.get(account_type=CashAccount.AccountType.NU)

    def test_default_accounts_and_pocket_balances(self):
        """Default accounts are created and have individual balance tracking."""
        self.assertEqual(CashAccount.objects.count(), 4)
        self.assertIsNotNone(self.acc_nequi)
        self.assertIsNotNone(self.acc_nu)

        # Inject $1,000,000 into Nequi and $2,000,000 into Nu
        CashflowService.record_manual_movement(
            account=self.acc_nequi,
            movement_type=CashMovement.MovementType.CAPITAL_INJECTION,
            amount=Decimal('1000000.00'),
            description='Recarga Nequi inicial'
        )
        CashflowService.record_manual_movement(
            account=self.acc_nu,
            movement_type=CashMovement.MovementType.CAPITAL_INJECTION,
            amount=Decimal('2000000.00'),
            description='Aporte en Cajita Nu'
        )

        self.assertEqual(self.acc_nequi.get_current_balance(), Decimal('1000000.00'))
        self.assertEqual(self.acc_nu.get_current_balance(), Decimal('2000000.00'))
        self.assertEqual(self.acc_cash.get_current_balance(), Decimal('0.00'))
        self.assertEqual(CashMovement.get_current_balance(), Decimal('3000000.00'))

    def test_inter_account_transfer(self):
        """
        Transferring $400,000 from Nu to Nequi updates both pocket balances
        while keeping total consolidated liquidity constant.
        """
        # Fund Nu with $1,000,000
        CashflowService.record_manual_movement(
            account=self.acc_nu,
            movement_type=CashMovement.MovementType.CAPITAL_INJECTION,
            amount=Decimal('1000000.00')
        )

        # Transfer $400,000 from Nu to Nequi
        outflow, inflow = CashflowService.record_account_transfer(
            source_account=self.acc_nu,
            target_account=self.acc_nequi,
            amount=Decimal('400000.00'),
            notes='Paso de Nu a Nequi para prestar'
        )

        self.assertEqual(outflow.amount, Decimal('400000.00'))
        self.assertEqual(inflow.amount, Decimal('400000.00'))
        self.assertEqual(self.acc_nu.get_current_balance(), Decimal('600000.00'))
        self.assertEqual(self.acc_nequi.get_current_balance(), Decimal('400000.00'))
        self.assertEqual(CashMovement.get_current_balance(), Decimal('1000000.00'))

        # Transferring more than available balance fails
        with self.assertRaises(ValidationError):
            CashflowService.record_account_transfer(
                source_account=self.acc_nequi,
                target_account=self.acc_cash,
                amount=Decimal('900000.00')
            )

    def test_cash_reconciliation_arqueo(self):
        """Reconciliation compares physical or app balance with ledger balance."""
        CashflowService.record_manual_movement(
            account=self.acc_nequi,
            movement_type=CashMovement.MovementType.CAPITAL_INJECTION,
            amount=Decimal('500000.00')
        )

        # Counted in Nequi app is $495,000 (missing $5,000 due to fee or unaccounted withdrawal)
        rec = CashflowService.record_reconciliation(
            account=self.acc_nequi,
            physical_balance=Decimal('495000.00'),
            notes='Faltante por verificar'
        )

        self.assertEqual(rec.expected_balance, Decimal('500000.00'))
        self.assertEqual(rec.physical_balance, Decimal('495000.00'))
        self.assertEqual(rec.difference, Decimal('-5000.00'))

    def test_views_flow(self):
        """HTTP endpoints for cashflow view, movements, transfers and reconciliations."""
        # 1. Main cashflow ledger view
        response = self.client.get(reverse('cashflow:index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nequi')
        self.assertContains(response, 'Cuenta Nu')
        self.assertContains(response, 'Saldo Consolidado')

        # 2. Record manual movement POST
        post_data = {
            'account': self.acc_nu.id,
            'movement_type': 'CAPITAL_INJECTION',
            'amount': '800000.00',
            'movement_date': timezone.localdate().strftime('%Y-%m-%d'),
            'description': 'Inyección a Cajita Nu'
        }
        response = self.client.post(reverse('cashflow:movement_create'), data=post_data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.acc_nu.get_current_balance(), Decimal('800000.00'))

        # 3. Transfer POST
        transfer_data = {
            'source_account': self.acc_nu.id,
            'target_account': self.acc_cash.id,
            'amount': '300000.00',
            'transfer_date': timezone.localdate().strftime('%Y-%m-%d'),
            'notes': 'Retiro en cajero para caja'
        }
        response = self.client.post(reverse('cashflow:transfer'), data=transfer_data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.acc_nu.get_current_balance(), Decimal('500000.00'))
        self.assertEqual(self.acc_cash.get_current_balance(), Decimal('300000.00'))

        # 4. Arqueo POST
        rec_data = {
            'account': self.acc_cash.id,
            'physical_balance': '300000.00',
            'notes': 'Caja física contada en billetes'
        }
        response = self.client.post(reverse('cashflow:reconciliation'), data=rec_data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CashReconciliation.objects.count(), 1)

