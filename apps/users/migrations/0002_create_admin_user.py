from django.db import migrations
from django.contrib.auth.hashers import make_password

def create_or_update_admin(apps, schema_editor):
    CustomUser = apps.get_model('users', 'CustomUser')
    email = 'diazjunior354@gmail.com'
    raw_password = 'diazjunior22'
    
    user = CustomUser.objects.filter(email=email).first()
    if user:
        user.password = make_password(raw_password)
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.role = 'ADMIN'
        user.save()
    else:
        CustomUser.objects.create(
            username='diazjunior',
            email=email,
            password=make_password(raw_password),
            first_name='Junior',
            last_name='Diaz',
            is_staff=True,
            is_superuser=True,
            is_active=True,
            role='ADMIN'
        )

def reverse_admin(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_or_update_admin, reverse_admin),
    ]
