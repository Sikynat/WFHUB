from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from wefixhub.models import WfClient

class Command(BaseCommand):
    help = 'Cria usuários para clientes existentes e os vincula.'

    def handle(self, *args, **options):
        self.stdout.write("Iniciando o processo de vinculação de clientes...")

        for client in WfClient.objects.all():
            username = str(client.client_code)
            password = "senha_temporaria_123"

            try:
                user, created = User.objects.get_or_create(username=username)
                
                if created:
                    user.set_password(password)
                    user.save()
                    self.stdout.write(self.style.SUCCESS(f"Usuário '{username}' criado com sucesso."))

                if not hasattr(client, 'user') or not client.user:
                    client.user = user
                    client.save()
                    self.stdout.write(self.style.SUCCESS(f"Cliente '{client.client_name}' vinculado ao usuário '{username}'."))
                else:
                    self.stdout.write(self.style.WARNING(f"Cliente '{client.client_name}' já está vinculado. Pulando..."))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Erro ao vincular o cliente {client.client_name}: {e}"))

        self.stdout.write(self.style.SUCCESS("Processo de vinculação concluído!"))