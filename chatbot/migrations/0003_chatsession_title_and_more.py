# Generated by Django 5.1.3 on 2024-12-09 02:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chatbot', '0002_chatsession'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatsession',
            name='title',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddIndex(
            model_name='chatsession',
            index=models.Index(fields=['event', 'phase', 'timestamp'], name='chat_session_lookup_idx'),
        ),
    ]