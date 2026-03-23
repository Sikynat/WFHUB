from django import forms
from django.contrib.auth.models import User
from .models import Endereco, WfClient, wefixhub_uf, Pedido, Empresa

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

class CadastroEmpresaForm(forms.Form):
    # Dados da empresa
    nome = forms.CharField(max_length=128, label='Nome da Empresa')
    slug = forms.SlugField(max_length=64, label='Identificador único (ex: wefix-sp)', help_text='Só letras minúsculas, números e hífens. Sem espaços.')
    plano = forms.ChoiceField(choices=Empresa.PLANO_CHOICES, label='Plano')
    email_contato = forms.EmailField(label='E-mail de contato', required=False)
    telefone = forms.CharField(max_length=20, label='Telefone', required=False)

    # Dados do usuário administrador
    username = forms.CharField(max_length=150, label='Usuário (login)')
    email_usuario = forms.EmailField(label='E-mail do administrador')
    senha = forms.CharField(widget=forms.PasswordInput, label='Senha')
    confirmar_senha = forms.CharField(widget=forms.PasswordInput, label='Confirmar senha')

    def clean_slug(self):
        slug = self.cleaned_data['slug']
        if Empresa.objects.filter(slug=slug).exists():
            raise forms.ValidationError('Este identificador já está em uso.')
        return slug

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Este nome de usuário já existe.')
        return username

    def clean(self):
        cleaned_data = super().clean()
        senha = cleaned_data.get('senha')
        confirmar = cleaned_data.get('confirmar_senha')
        if senha and confirmar and senha != confirmar:
            self.add_error('confirmar_senha', 'As senhas não coincidem.')
        return cleaned_data


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