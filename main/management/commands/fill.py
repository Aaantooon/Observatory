from django.core.management import BaseCommand

from main.models import Student


class Command(BaseCommand):

    def handle(self, *args, **options):
        students_list = [
            {'last_name': 'Ivanov', 'first_name': 'Alexei'},
            {'last_name': 'Petrova', 'first_name': 'Maria'},
            {'last_name': 'Sokolov', 'first_name': 'Dmitry'},
            {'last_name': 'Volkova', 'first_name': 'Elena'},
            {'last_name': 'Morozov', 'first_name': 'Kirill'},
            {'last_name': 'Novikova', 'first_name': 'Anastasia'},
            {'last_name': 'Pavlov', 'first_name': 'Igor'},
            {'last_name': 'Lebedeva', 'first_name': 'Olga'},
            {'last_name': 'Vasiliev', 'first_name': 'Andrey'},
            {'last_name': 'Smirnova', 'first_name': 'Tatiana'},
        ]

        # for student_item in students_list:
        #     Student.objects.create(**student_item) //Для для маленьких баз данных

        students_for_create = []
        for student_item in students_list:
            students_for_create.append(
                Student(**student_item)

            )
        Student.objects.bulk_create(students_for_create)