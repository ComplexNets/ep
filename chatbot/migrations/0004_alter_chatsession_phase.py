# Generated by Django 5.1.3 on 2024-12-09 02:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chatbot', '0003_chatsession_title_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='chatsession',
            name='phase',
            field=models.CharField(choices=[('facts', 'Factual Description'), ('feelings', 'Emotional Response'), ('associations', 'Behavioral Associations'), ('growth', 'Positive Reframing & Growth')], default='facts', max_length=20),
        ),
    ]
