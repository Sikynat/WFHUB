from django import forms
from .models import Endereco, WfClient, wefixhub_uf, Pedido

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

class GerarPedidoForm(forms.Form):
    cliente = forms.ModelChoiceField(
        queryset=WfClient.objects.all().order_by('client_name'),
        label='Selecione o Cliente',
        empty_label='---',
        required=False

    )

class SelectClientForm(forms.Form):
    cliente = forms.ModelChoiceField(
        queryset=WfClient.objects.all(),
        label="Selecione o Cliente",
        empty_label="---",
        widget=forms.Select(attrs={'class': 'form-select form-control'})
    )

class UploadPedidoForm(forms.Form):
    data_expedicao = forms.DateField(
        label="Data de Expedição",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        required=True
    )
    endereco_selecionado = forms.ModelChoiceField(
        queryset=Endereco.objects.none(),
        label="Endereço de Entrega",
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    frete_option = forms.ChoiceField(
        choices=Pedido.FRETE_CHOICES,
        label="Opção de Frete",
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    nota_fiscal = forms.ChoiceField(
        choices=Pedido.NOTA_FISCAL_CHOICES,
        label="Nota Fiscal",
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    planilha_pedido = forms.FileField(
        label="Fazer Upload da Planilha de Pedido",
        help_text="Arquivo .xlsx ou .csv com duas colunas: 'codigo' e 'quantidade'.",
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )

 # ✅ Alterado o nome do campo para 'observacao_preferencia'
    observacao_preferencia = forms.CharField(
        label="Observação (opcional)",
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )