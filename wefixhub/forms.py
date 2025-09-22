# wefixhub/forms.py
from django import forms
from .models import WfClient

class WfClientForm(forms.ModelForm):
    class Meta:
        model = WfClient
        fields = ['client_name', 'client_cnpj', 'client_adress', 'client_city', 'client_state_subscription']

    def __init__(self, *args, **kwargs):
        super(WfClientForm, self).__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs['class'] = 'form-control'