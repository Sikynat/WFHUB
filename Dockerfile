# 1. PONTO DE PARTIDA
FROM python:3.11-slim

# 2. CONFIGURAÇÃO DO AMBIENTE
ENV LANG pt_BR.UTF-8
ENV LC_ALL pt_BR.UTF-8

# 3. INSTALAÇÃO DE PACOTES DO SISTEMA
RUN apt-get update && apt-get install -y locales \
  && sed -i -e 's/# pt_BR.UTF-8 UTF-8/pt_BR.UTF-8 UTF-8/' /etc/locale.gen \
  && dpkg-reconfigure --frontend=noninteractive locales \
  && rm -rf /var/lib/apt/lists/*

# 4. DEFINIÇÃO DO DIRETÓRIO DE TRABALHO
WORKDIR /app

# 5. CÓPIA E INSTALAÇÃO DE DEPENDÊNCIAS PYTHON
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. CÓPIA DO CÓDIGO DA APLICAÇÃO
COPY . .

# 7. BUILD DE ARQUIVOS ESTÁTICOS
# Define variáveis temporárias APENAS para o build do collectstatic
# Django vai tentar se conectar ao DB, então fornecemos valores falsos.
ENV SECRET_KEY="dummy"
ENV ALLOWED_HOSTS="dummy"
ENV CSRF_TRUSTED_ORIGINS="https://dummy.com"
ENV MYSQLDATABASE="dummy"
ENV MYSQLUSER="dummy"
ENV MYSQLPASSWORD="dummy"
ENV MYSQLHOST="localhost"
ENV MYSQLPORT="3306"
ENV DEBUG="False" # Adicionar DEBUG=False para simular o ambiente de produção

# Coleta todos os arquivos estáticos para o diretório STATIC_ROOT
RUN python manage.py collectstatic --noinput

# 8. COMANDO DE INICIALIZAÇÃO DA APLICAÇÃO
# Este é o comando que será executado quando o contêiner iniciar
CMD ["gunicorn", "app.wsgi:application", "--bind", "0.0.0.0:8000"]