from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class RegisterForm(forms.Form):
    first_name = forms.CharField(max_length=100, label='Nome')
    last_name = forms.CharField(max_length=100, label='Sobrenome')
    username = forms.CharField(max_length=150, label='Usuário')
    password = forms.CharField(widget=forms.PasswordInput, label='Senha', min_length=6)
    password_confirm = forms.CharField(widget=forms.PasswordInput, label='Confirmar senha')
    avatar = forms.ImageField(required=False, label='Foto de perfil')

    def clean_username(self):
        u = self.cleaned_data['username']
        if User.objects.filter(username=u).exists():
            raise ValidationError('Username já em uso.')
        return u

    def clean(self):
        c = super().clean()
        if c.get('password') and c.get('password_confirm') and c['password'] != c['password_confirm']:
            self.add_error('password_confirm', 'As senhas não conferem.')
        return c


class LoginForm(forms.Form):
    username = forms.CharField(label='Usuário')
    password = forms.CharField(widget=forms.PasswordInput, label='Senha')
