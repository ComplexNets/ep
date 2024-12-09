# Generated by Django 5.0 on 2024-12-09 03:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chatbot', '0006_alter_chatsession_phase_alter_event_current_phase_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='chatsession',
            name='phase',
            field=models.CharField(choices=[('facts', 'Facts'), ('feelings', 'Feelings'), ('thoughts', 'Thoughts'), ('growth', 'Growth')], default='facts', max_length=20),
        ),
        migrations.AlterField(
            model_name='event',
            name='current_phase',
            field=models.CharField(choices=[('facts', 'Facts'), ('feelings', 'Feelings'), ('thoughts', 'Thoughts'), ('growth', 'Growth')], default='facts', max_length=20),
        ),
        migrations.AlterField(
            model_name='userthread',
            name='writing_phase',
            field=models.CharField(choices=[('facts', 'Facts'), ('feelings', 'Feelings'), ('thoughts', 'Thoughts'), ('growth', 'Growth')], default='facts', max_length=20),
        ),
    ]
