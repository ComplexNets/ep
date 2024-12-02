# Generated by Django 5.1.3 on 2024-11-30 23:44

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chatbot', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='userthread',
            name='writing_phase',
            field=models.CharField(choices=[('facts', 'Factual Description'), ('feelings', 'Emotional Response'), ('associations', 'Behavioral Associations')], default='facts', max_length=20),
        ),
        migrations.CreateModel(
            name='Event',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('date_occurred', models.DateField(help_text='When did this event occur?')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('current_phase', models.CharField(choices=[('facts', 'Factual Description'), ('feelings', 'Emotional Response'), ('associations', 'Behavioral Associations')], default='facts', max_length=20)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-date_occurred'],
            },
        ),
        migrations.AddField(
            model_name='userthread',
            name='event',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='chatbot.event'),
        ),
        migrations.AddIndex(
            model_name='userthread',
            index=models.Index(fields=['event', 'writing_phase'], name='chatbot_use_event_i_ca2687_idx'),
        ),
    ]
