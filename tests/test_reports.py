import json
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.customers.models import Customer
from apps.reports.services.backup_service import BackupService

User = get_user_model()

class BackupAndReportsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser(
            email='admin@test.local',
            username='admintest',
            password='Password123!',
            first_name='Admin',
            last_name='Test',
            role=User.Role.ADMIN
        )
        self.client.login(email='admin@test.local', password='Password123!')

        self.customer = Customer.objects.create(
            first_name='Mariana',
            last_name='Gomez',
            document_type=Customer.DocumentType.CC,
            document_number='987654321',
            phone='3109876543',
            city='Medellín'
        )

    def test_report_list_view(self):
        response = self.client.get(reverse('reports:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Mariana Gomez' if 'Mariana Gomez' in response.content.decode() else 'Reportes y Respaldo')
        self.assertContains(response, 'Descargar Backup')

    def test_backup_service_export_and_restore(self):
        # 1. Export JSON backup
        json_str = BackupService.generate_full_backup_json()
        data = json.loads(json_str)
        self.assertTrue(len(data) > 0)

        # Verify our customer is in the exported data
        customer_found = any(item.get('model') == 'customers.customer' and item['fields']['document_number'] == '987654321' for item in data)
        self.assertTrue(customer_found)

        # 2. Delete customer and verify restore
        Customer.objects.filter(document_number='987654321').delete()
        self.assertFalse(Customer.objects.filter(document_number='987654321').exists())

        # 3. Restore from backup
        restored_count = BackupService.restore_backup_json(json_str)
        self.assertTrue(restored_count > 0)
        self.assertTrue(Customer.objects.filter(document_number='987654321').exists())

    def test_backup_views_download_and_upload(self):
        # 1. Download backup view
        res_export = self.client.get(reverse('reports:backup_export'))
        self.assertEqual(res_export.status_code, 200)
        self.assertEqual(res_export['Content-Type'], 'application/json')
        self.assertIn('attachment; filename="backup_prestamos_', res_export['Content-Disposition'])

        backup_content = res_export.content

        # 2. Upload backup view
        backup_file = SimpleUploadedFile('backup_test.json', backup_content, content_type='application/json')
        res_restore = self.client.post(reverse('reports:backup_restore'), {'backup_file': backup_file})
        self.assertEqual(res_restore.status_code, 302)
        self.assertRedirects(res_restore, reverse('reports:list'))
