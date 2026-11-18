from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.customers.models import Customer

User = get_user_model()

class CustomerModuleTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.password = "AdminPass2026!"
        self.user = User.objects.create_user(
            username="admin_test",
            email="admin@test.local",
            password=self.password,
            first_name="Carlos",
            last_name="Admin",
            role=User.Role.ADMIN
        )
        self.client.login(username="admin@test.local", password=self.password)

        self.customer1 = Customer.objects.create(
            first_name="Andrés",
            last_name="Gómez",
            document_type=Customer.DocumentType.CC,
            document_number="1020304050",
            phone="3101234567",
            whatsapp="3101234567",
            city="Bogotá",
            status=Customer.Status.ACTIVE,
            created_by=self.user
        )

    def test_customer_creation_valid(self):
        data = {
            'first_name': 'Mariana',
            'last_name': 'Ramírez',
            'document_type': 'CC',
            'document_number': '987654321',
            'phone': '3129876543',
            'whatsapp': '3129876543',
            'email': 'mariana@correo.com',
            'address': 'Carrera 7 # 72-10',
            'city': 'Medellín',
            'status': 'ACTIVE',
            'reference_name': 'Pedro Ramírez',
            'reference_relationship': 'Padre',
            'reference_phone': '3151112233',
            'notes': 'Cliente referida con excelente historial',
        }
        response = self.client.post(reverse('customers:create'), data=data)
        self.assertEqual(response.status_code, 302)
        new_customer = Customer.objects.filter(document_number='987654321').first()
        self.assertIsNotNone(new_customer)
        self.assertEqual(new_customer.full_name, "Mariana Ramírez")
        self.assertEqual(new_customer.city, "Medellín")
        self.assertEqual(new_customer.created_by, self.user)

    def test_customer_duplicate_document_rejected(self):
        # Attempt to create customer with same document number (even with formatting)
        data = {
            'first_name': 'Otro',
            'last_name': 'Gómez',
            'document_type': 'CC',
            'document_number': '1.020.304.050',  # Same as customer1 with dots
            'phone': '3200000000',
            'city': 'Bogotá',
            'status': 'ACTIVE',
        }
        response = self.client.post(reverse('customers:create'), data=data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ya existe un cliente registrado con el documento")
        self.assertEqual(Customer.objects.filter(first_name='Otro').count(), 0)

    def test_customer_search_by_name_and_document(self):
        # Search by name
        res_name = self.client.get(reverse('customers:list') + '?q=Andr')
        self.assertEqual(res_name.status_code, 200)
        self.assertContains(res_name, "Andrés Gómez")

        # Search by document
        res_doc = self.client.get(reverse('customers:list') + '?q=1020304050')
        self.assertEqual(res_doc.status_code, 200)
        self.assertContains(res_doc, "1020304050")

        # Search nonexistent
        res_none = self.client.get(reverse('customers:list') + '?q=InexistenteXYZ')
        self.assertEqual(res_none.status_code, 200)
        self.assertContains(res_none, "No se encontraron clientes")

    def test_customer_htmx_search_returns_partial(self):
        response = self.client.get(reverse('customers:list') + '?q=Andrés', HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 200)
        # Should contain table partial, not full html layout
        self.assertContains(response, "<table")
        self.assertNotContains(response, "<!DOCTYPE html>")

    def test_customer_detail_view(self):
        response = self.client.get(reverse('customers:detail', kwargs={'pk': self.customer1.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Andrés Gómez")
        self.assertContains(response, "1020304050")
        self.assertContains(response, "Histórico Prestado")
        self.assertContains(response, "Saldo Pendiente")

    def test_customer_update(self):
        data = {
            'first_name': 'Andrés Felipe',
            'last_name': 'Gómez',
            'document_type': 'CC',
            'document_number': '1020304050',
            'phone': '3109998877',
            'city': 'Cali',
            'status': 'ACTIVE',
        }
        response = self.client.post(reverse('customers:update', kwargs={'pk': self.customer1.pk}), data=data)
        self.assertEqual(response.status_code, 302)
        self.customer1.refresh_from_db()
        self.assertEqual(self.customer1.first_name, "Andrés Felipe")
        self.assertEqual(self.customer1.city, "Cali")
        self.assertEqual(self.customer1.phone, "3109998877")

    def test_customer_toggle_status(self):
        response = self.client.post(reverse('customers:toggle_status', kwargs={'pk': self.customer1.pk}))
        self.assertEqual(response.status_code, 302)
        self.customer1.refresh_from_db()
        self.assertEqual(self.customer1.status, Customer.Status.INACTIVE)

        # Toggle back to ACTIVE
        self.client.post(reverse('customers:toggle_status', kwargs={'pk': self.customer1.pk}))
        self.customer1.refresh_from_db()
        self.assertEqual(self.customer1.status, Customer.Status.ACTIVE)

