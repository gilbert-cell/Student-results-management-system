import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Create the initial Render Super Admin when bootstrap credentials are configured.'

    def handle(self, *args, **options):
        username = os.environ.get('SRMS_BOOTSTRAP_ADMIN_USERNAME', '').strip()
        password = os.environ.get('SRMS_BOOTSTRAP_ADMIN_PASSWORD', '')
        email = os.environ.get('SRMS_BOOTSTRAP_ADMIN_EMAIL', '').strip()

        if not username or not password:
            self.stdout.write('No bootstrap admin credentials configured; skipping.')
            return

        User = get_user_model()
        existing = User.objects.filter(username=username).first()
        if existing:
            if not existing.is_superuser:
                raise CommandError(
                    f'Bootstrap username {username!r} already belongs to a non-superuser account.'
                )
            self.stdout.write(f'Super Admin {username!r} already exists; skipping.')
            return

        try:
            validate_password(password)
        except ValidationError as error:
            raise CommandError('; '.join(error.messages)) from error

        User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
        )
        self.stdout.write(self.style.SUCCESS(f'Created initial Super Admin {username!r}.'))
