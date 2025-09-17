from django.contrib import admin
from wefixhub.models import WfClient
# Register your models here.

class ClientAdmin(admin.ModelAdmin):
    list_display = ['client_id', 'client_code', 'client_name', 'client_cnpj', 'client_adress', 'client_city', 'client_state', 'client_state_subscription', 'client_date', 'is_active']
    search_fields =  ['client_id', 'client_code', 'client_name', 'client_cnpj', 'client_adress', 'client_city', 'client_state', 'client_state_subscription', 'client_date', 'is_active']

admin.site.register(WfClient, ClientAdmin)