from django.contrib import admin
from wefixhub.models import WfClient
# Register your models here.

class ClientAdmin(admin.ModelAdmin):
    list_display = ['client_is_active', 'client_id', 'client_code', 'client_name', 'client_cnpj', 'client_adress', 'client_city', 'client_state', 'client_state_subscription', 'client_date' ]
    search_fields =  ['client_is_active','client_id', 'client_code', 'client_name', 'client_cnpj', 'client_adress', 'client_city', 'client_state__uf_name', 'client_state_subscription', 'client_date',]

admin.site.register(WfClient, ClientAdmin)