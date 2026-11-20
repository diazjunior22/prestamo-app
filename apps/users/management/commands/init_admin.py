import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Creates or verifies the initial administrator superuser for LoanManager'

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, default=os.getenv('ADMIN_EMAIL', 'diazjunior354@gmail.com'))
        parser.add_argument('--username', type=str, default='diazjunior')
        parser.add_argument('--password', type=str, default=os.getenv('ADMIN_PASSWORD', 'diazjunior22'))
        parser.add_argument('--first-name', type=str, default='Junior')
        parser.add_argument('--last-name', type=str, default='Diaz')

    def handle(self, *args, **options):
        email = options['email']
        username = options['username']
        password = options['password']
        first_name = options['first_name']
        last_name = options['last_name']

        user = User.objects.filter(email=email).first()
        if user:
            user.set_password(password)
            user.role = User.Role.ADMIN
            user.is_superuser = True
            user.is_staff = True
            user.is_active = True
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Usuario '{email}' actualizado exitosamente con rol ADMIN."))
            return

        user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role=User.Role.ADMIN
        )
        self.stdout.write(self.style.SUCCESS(f"Superusuario '{email}' creado exitosamente."))

