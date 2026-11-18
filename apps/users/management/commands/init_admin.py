import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Creates or verifies the initial administrator superuser for LoanManager'

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, default=os.getenv('ADMIN_EMAIL', 'admin@loanmanager.local'))
        parser.add_argument('--username', type=str, default='admin')
        parser.add_argument('--password', type=str, default='AdminLoan2026!')
        parser.add_argument('--first-name', type=str, default='Administrador')
        parser.add_argument('--last-name', type=str, default='Principal')

    def handle(self, *args, **options):
        email = options['email']
        username = options['username']
        password = options['password']
        first_name = options['first_name']
        last_name = options['last_name']

        if User.objects.filter(email=email).exists():
            self.stdout.write(self.style.WARNING(f"El usuario con email '{email}' ya existe."))
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

