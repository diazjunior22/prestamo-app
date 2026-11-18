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

    def test_customer_creation_with_only_mandatory_fields(self):
        """Verify that only first_name, last_name, and phone are mandatory"""
        data = {
            'first_name': 'Julián',
            'last_name': 'Castro',
            'phone': '3009876543',
            'document_number': '',
            'status': 'ACTIVE',
        }
        response = self.client.post(reverse('customers:create'), data=data)
        self.assertEqual(response.status_code, 302)
        customer = Customer.objects.filter(first_name='Julián', last_name='Castro').first()
        self.assertIsNotNone(customer)
        self.assertIsNone(customer.document_number)
        self.assertEqual(customer.phone, '3009876543')

    def test_customer_mandatory_fields_validation(self):
        """Missing first_name, last_name, or phone must fail validation"""
        # Missing phone
        res_no_phone = self.client.post(reverse('customers:create'), data={'first_name': 'Ana', 'last_name': 'Soler', 'phone': ''})
        self.assertEqual(res_no_phone.status_code, 200)
        self.assertContains(res_no_phone, "El número de teléfono es obligatorio.")

        # Missing first_name
        res_no_name = self.client.post(reverse('customers:create'), data={'first_name': '', 'last_name': 'Soler', 'phone': '3110001122'})
        self.assertEqual(res_no_name.status_code, 200)
        self.assertContains(res_no_name, "El nombre del cliente es obligatorio.")

        # Missing last_name
        res_no_last = self.client.post(reverse('customers:create'), data={'first_name': 'Ana', 'last_name': '', 'phone': '3110001122'})
        self.assertEqual(res_no_last.status_code, 200)
        self.assertContains(res_no_last, "El apellido del cliente es obligatorio.")

    def test_customer_search_by_name(self):
        # Search by first name
        res_first = self.client.get(reverse('customers:list') + '?q=Andr')
        self.assertEqual(res_first.status_code, 200)
        self.assertContains(res_first, "Andrés Gómez")

        # Search by last name
        res_last = self.client.get(reverse('customers:list') + '?q=Gómez')
        self.assertEqual(res_last.status_code, 200)
        self.assertContains(res_last, "Andrés Gómez")

        # Search by full name combined
        res_full = self.client.get(reverse('customers:list') + '?q=Andrés Gómez')
        self.assertEqual(res_full.status_code, 200)
        self.assertContains(res_full, "Andrés Gómez")

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

    def test_customer_delete_view(self):
        customer = Customer.objects.create(
            first_name="Temporal",
            last_name="Eliminar",
            phone="3101112233",
            created_by=self.user
        )
        c_id = customer.pk

        # GET: renders confirmation
        res_get = self.client.get(reverse('customers:delete', kwargs={'pk': c_id}))
        self.assertEqual(res_get.status_code, 200)
        self.assertContains(res_get, "Temporal Eliminar")
        self.assertContains(res_get, "Confirmación de Eliminación")

        # POST: deletes customer
        res_post = self.client.post(reverse('customers:delete', kwargs={'pk': c_id}))
        self.assertEqual(res_post.status_code, 302)
        self.assertRedirects(res_post, reverse('customers:list'))
        self.assertFalse(Customer.objects.filter(pk=c_id).exists())


