# Generated by Django 5.1.3 on 2024-12-01 22:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chatbot', '0003_userprofile_personality_preference_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='personality_preference',
            field=models.CharField(choices=[('professional', 'Professional and Academic'), ('empathetic', 'Empathetic and Supportive'), ('encouraging', 'Encouraging and Motivational'), ('friendly', 'Friendly and Casual')], default='professional', help_text="Choose how you'd like the AI to interact with you", max_length=20),
        ),
    ]
