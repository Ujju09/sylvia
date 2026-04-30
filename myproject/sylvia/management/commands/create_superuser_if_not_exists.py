import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Create a superuser if one does not already exist (idempotent)'

    def handle(self, *args, **options):
        User = get_user_model()

        username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '')

        if not username or not password:
            self.stderr.write(
                self.style.ERROR(
                    'DJANGO_SUPERUSER_USERNAME and DJANGO_SUPERUSER_PASSWORD '
                    'environment variables must be set.'
                )
            )
            return

        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(
                    f'Superuser "{username}" already exists. Skipping creation.'
                )
            )
            return

        User.objects.create_superuser(username=username, password=password, email=email)
        self.stdout.write(
            self.style.SUCCESS(f'Superuser "{username}" created successfully.')
        )
