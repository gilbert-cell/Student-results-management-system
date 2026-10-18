from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [('core', '0010_user_must_change_password')]

    operations = [
        migrations.AddField(
            model_name='schoolclass',
            name='max_optional_subjects',
            field=models.PositiveSmallIntegerField(default=2),
        ),
        migrations.AddField(
            model_name='subject',
            name='is_optional',
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name='StudentSubjectRegistration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('academic_year', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='subject_registrations', to='core.academicyear')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='subject_registrations', to='core.student')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='student_registrations', to='core.subject')),
                ('term', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='subject_registrations', to='core.term')),
            ],
        ),
        migrations.AddConstraint(
            model_name='studentsubjectregistration',
            constraint=models.UniqueConstraint(fields=('student', 'subject', 'academic_year', 'term'), name='unique_student_subject_registration'),
        ),
    ]
