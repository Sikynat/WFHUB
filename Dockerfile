# 1. PONTO DE PARTIDA
# "Comece com um sistema operacional Linux mínimo que já tenha o Python 3.11 instalado."
FROM python:3.11-slim

# 2. CONFIGURAÇÃO DO AMBIENTE
# "Defina estas variáveis de ambiente para que o sistema use português por padrão."
ENV LANG pt_BR.UTF-8
ENV LC_ALL pt_BR.UTF-8

# 3. EXECUÇÃO DE COMANDOS
# "Execute estes comandos no terminal do sistema para instalar o pacote de idiomas."
# Isso acontece DURANTE A CONSTRUÇÃO da imagem.
RUN apt-get update && apt-get install -y locales \
  && sed -i -e 's/# pt_BR.UTF-8 UTF-8/pt_BR.UTF-8 UTF-8/' /etc/locale.gen \
  && dpkg-reconfigure --frontend=noninteractive locales

# 4. DEFINIÇÃO DO DIRETÓRIO DE TRABALHO
# "Crie uma pasta chamada /app e entre nela. Todos os próximos comandos serão a partir daqui."
WORKDIR /app

# 5. CÓPIA DE ARQUIVOS
# "Copie o arquivo requirements.txt do meu computador para dentro da imagem, na pasta /app."
COPY requirements.txt .

# 6. INSTALAÇÃO DE DEPENDÊNCIAS
# "Agora, execute o pip para instalar as bibliotecas Python listadas no requirements.txt."
RUN pip install -r requirements.txt

# 7. CÓPIA DO RESTANTE DO CÓDIGO
# "Finalmente, copie todo o resto do meu projeto para dentro da imagem."
COPY . .

# 8. COMANDO DE INICIALIZAÇÃO
# "Quando alguém iniciar um contêiner a partir desta imagem, execute este comando para ligar o servidor web."
# Isso acontece QUANDO O CONTÊINER RODA, não durante a construção.
CMD ["gunicorn", "app.wsgi:application", "--bind", "0.0.0.0:8000"]