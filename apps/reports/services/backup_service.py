import io
import json
from django.core import serializers
from django.db import transaction
from django.utils import timezone
from apps.users.models import CustomUser
from apps.customers.models import Customer
from apps.loans.models import Loan, Installment
from apps.payments.models import Payment, PaymentAllocation
from apps.cashflow.models import CashAccount, CashMovement

class BackupService:
    @staticmethod
    def generate_full_backup_json():
        """
        Serializes all system entities into formatted JSON string.
        Preserves complete relational integrity.
        """
        objects = []
        for model in [CustomUser, Customer, Loan, Installment, Payment, PaymentAllocation, CashAccount, CashMovement]:
            objects.extend(model.objects.all().order_by('pk'))
        
        return serializers.serialize('json', objects, indent=2, use_natural_foreign_keys=True)

    @staticmethod
    def restore_backup_json(json_content):
        """
        Restores database state from a validated JSON string inside an atomic transaction.
        """
        if isinstance(json_content, bytes):
            json_content = json_content.decode('utf-8')

        with transaction.atomic():
            count = 0
            for deserialized_obj in serializers.deserialize('json', json_content):
                deserialized_obj.save()
                count += 1
            return count
