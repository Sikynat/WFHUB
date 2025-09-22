# wefixhub/forms.py

from django import forms
from .models import WfClient, Endereco, wefixhub_uf

class WfClientForm(forms.ModelForm):
    class Meta:
        model = WfClient
        fields = ['client_name', 'client_cnpj', 'client_city', 'client_state_subscription', 'client_code']

class EnderecoForm(forms.ModelForm):
    class Meta:
        model = Endereco
        fields = ['logradouro', 'numero', 'bairro', 'cidade', 'estado', 'cep', 'is_default']
        widgets = {
            'is_default': forms.RadioSelect(choices=[(True, 'Endereço Padrão'), (False, 'Endereço Secundário')]),
        }

    def __init__(self, *args, **kwargs):
        super(EnderecoForm, self).__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs['class'] = 'form-control'