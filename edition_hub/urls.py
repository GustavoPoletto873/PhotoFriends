from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include

from landing.views import CustomPasswordResetConfirmView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('landing.urls')),

    # Redefinição de senha — Django built-in com templates customizados
    path('accounts/password_reset/', auth_views.PasswordResetView.as_view(
        template_name='registration/password_reset_form.html',
        email_template_name='registration/password_reset_email.html',
        subject_template_name='registration/password_reset_subject.txt',
    ), name='password_reset'),

    path('accounts/password_reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html',
    ), name='password_reset_done'),

    path('accounts/reset/<uidb64>/<token>/', CustomPasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html',
    ), name='password_reset_confirm'),

    path('accounts/reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html',
    ), name='password_reset_complete'),
]
