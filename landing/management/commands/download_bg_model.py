from django.core.management.base import BaseCommand
from landing.bg_remover import download_model


class Command(BaseCommand):
    help = 'Baixa o modelo u2netp.onnx para remoção de fundo'

    def handle(self, *args, **options):
        download_model()
        self.stdout.write(self.style.SUCCESS('Modelo pronto.'))
