import io
import json
from collections import defaultdict
from datetime import timedelta

import cloudinary.uploader
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.views import PasswordResetConfirmView
from django.core.mail import EmailMultiAlternatives
from django.urls import reverse_lazy
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import LoginForm, RegisterForm
from .models import Album, AlbumMember, Community, CommunityMember, Media, UserProfile


# ── LANDING ─────────────────────────────────────────────────────────────────

def index(request):
    return render(request, 'landing/index.html')


# ── AUTH ─────────────────────────────────────────────────────────────────────

def register_view(request):
    if request.user.is_authenticated:
        return redirect('albums_list')

    error = None
    form = RegisterForm(request.POST or None, request.FILES or None)

    if request.method == 'POST':
        if form.is_valid():
            d = form.cleaned_data
            user = User.objects.create_user(
                username=d['username'],
                email=d['email'],
                password=d['password'],
                first_name=d['first_name'],
                last_name=d['last_name'],
            )
            profile = UserProfile.objects.create(user=user)

            # Avatar upload to Cloudinary
            avatar_file = d.get('avatar')
            if avatar_file:
                try:
                    result = cloudinary.uploader.upload(
                        avatar_file,
                        folder='photo-friends/avatars',
                        transformation=[{'width': 400, 'height': 400, 'crop': 'fill'}],
                    )
                    profile.avatar_url = result['secure_url']
                    profile.avatar_id = result['public_id']
                except Exception:
                    pass

            # Email verification
            code = profile.generate_code('verification')
            profile.verification_sent_at = timezone.now()
            profile.save()

            _send_verification_email(user, code)

            request.session['verify_user_id'] = user.id
            return redirect('verify_email')
        else:
            error = next(iter(form.errors.values()))[0]

    return render(request, 'landing/auth/register.html', {'form': form, 'error': error})


def verify_email_view(request):
    user_id = request.session.get('verify_user_id')
    if not user_id:
        return redirect('login')

    user = get_object_or_404(User, id=user_id)
    profile = user.profile
    error = None

    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        if not profile.verification_sent_at:
            error = 'Código inválido.'
        elif timezone.now() > profile.verification_sent_at + timedelta(minutes=15):
            error = 'Código expirado. Reenvie o e-mail.'
        elif code != profile.verification_code:
            error = 'Código incorreto.'
        else:
            profile.email_verified = True
            profile.verification_code = ''
            profile.save()
            login(request, user)
            del request.session['verify_user_id']
            return redirect('albums_list')

    return render(request, 'landing/auth/verify_email.html', {'user': user, 'error': error})


def resend_verification_view(request):
    user_id = request.session.get('verify_user_id')
    if not user_id:
        return redirect('login')
    user = get_object_or_404(User, id=user_id)
    profile = user.profile
    code = profile.generate_code('verification')
    profile.verification_sent_at = timezone.now()
    profile.save()
    _send_verification_email(user, code)
    return redirect('verify_email')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('albums_list')

    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user:
            if not hasattr(user, 'profile') or not user.profile.email_verified:
                try:
                    profile = user.profile
                except UserProfile.DoesNotExist:
                    profile = UserProfile.objects.create(user=user)
                code = profile.generate_code('verification')
                profile.verification_sent_at = timezone.now()
                profile.save()
                _send_verification_email(user, code)
                request.session['verify_user_id'] = user.id
                return redirect('verify_email')
            login(request, user)
            return redirect('albums_list')
        else:
            error = 'Usuário ou senha incorretos.'

    return render(request, 'landing/auth/login.html', {'error': error})


def logout_view(request):
    logout(request)
    return redirect('index')


def forgot_password_view(request):
    error = None
    sent = False

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        try:
            user = User.objects.get(email=email)
            try:
                profile = user.profile
            except UserProfile.DoesNotExist:
                profile = UserProfile.objects.create(user=user)
            code = profile.generate_code('reset')
            profile.reset_code_sent_at = timezone.now()
            profile.save()
            _send_reset_email(user, code)
            request.session['reset_user_id'] = user.id
            return redirect('reset_password')
        except User.DoesNotExist:
            error = 'Nenhuma conta encontrada com esse e-mail.'

    return render(request, 'landing/auth/forgot_password.html', {'error': error})


def reset_password_view(request):
    user_id = request.session.get('reset_user_id')
    if not user_id:
        return redirect('forgot_password')

    user = get_object_or_404(User, id=user_id)
    profile = user.profile
    error = None

    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        password = request.POST.get('password', '')
        confirm = request.POST.get('password_confirm', '')

        if not profile.reset_code_sent_at or timezone.now() > profile.reset_code_sent_at + timedelta(minutes=15):
            error = 'Código expirado. Solicite um novo.'
        elif code != profile.reset_code:
            error = 'Código incorreto.'
        elif len(password) < 6:
            error = 'Senha deve ter ao menos 6 caracteres.'
        elif password != confirm:
            error = 'As senhas não conferem.'
        else:
            user.set_password(password)
            user.save()
            profile.reset_code = ''
            profile.save()
            del request.session['reset_user_id']
            return redirect('login')

    return render(request, 'landing/auth/reset_password.html', {'error': error})


# ── ALBUMS ───────────────────────────────────────────────────────────────────

@login_required
def albums_list_view(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        if name:
            album = Album.objects.create(
                name=name, description=description, created_by=request.user
            )
            AlbumMember.objects.get_or_create(album=album, user=request.user)
            return redirect('album_detail', album_id=album.id)

    albums = Album.objects.filter(
        Q(community__isnull=True) &
        (Q(created_by=request.user) | Q(members=request.user))
    ).distinct().prefetch_related('media')

    return render(request, 'landing/albums/list.html', {'albums': albums})


@login_required
def album_detail_view(request, album_id):
    album = get_object_or_404(Album, id=album_id)

    if album.community:
        membership = CommunityMember.objects.filter(community=album.community, user=request.user).first()
        if not membership:
            return redirect('communities_list')
        is_admin = membership.role == CommunityMember.ADMIN
        is_owner = album.created_by == request.user or is_admin
        members = album.community.members.select_related('profile')
    else:
        has_access = (
            album.created_by == request.user
            or AlbumMember.objects.filter(album=album, user=request.user).exists()
        )
        if not has_access:
            return redirect('albums_list')
        is_owner = album.created_by == request.user
        members = album.members.select_related('profile')

    media_qs = (
        album.media
        .select_related('uploaded_by')
        .annotate(sort_date=Coalesce('taken_at', 'uploaded_at'))
        .order_by('-sort_date')
    )

    grouped = defaultdict(list)
    for m in media_qs:
        dt = m.display_date
        if dt:
            local_dt = timezone.localtime(dt) if timezone.is_aware(dt) else dt
            key = local_dt.date()
        else:
            key = None
        grouped[key].append(m)

    media_by_date = sorted(
        [(k, v) for k, v in grouped.items() if k is not None],
        reverse=True,
    )

    return render(request, 'landing/albums/detail.html', {
        'album': album,
        'media_by_date': media_by_date,
        'members': members,
        'is_owner': is_owner,
        'total_media': media_qs.count(),
        'community': album.community,
    })


@login_required
@require_POST
def upload_media_view(request, album_id):
    album = get_object_or_404(Album, id=album_id)
    if album.community:
        has_access = CommunityMember.objects.filter(community=album.community, user=request.user).exists()
    else:
        has_access = (
            album.created_by == request.user
            or AlbumMember.objects.filter(album=album, user=request.user).exists()
        )
    if not has_access:
        return JsonResponse({'error': 'Sem acesso'}, status=403)

    files = request.FILES.getlist('files')
    if not files:
        return JsonResponse({'error': 'Nenhum arquivo enviado'}, status=400)

    uploaded = []
    for f in files:
        is_video = f.content_type.startswith('video/')
        resource_type = 'video' if is_video else 'image'
        taken_at = None if is_video else _extract_exif_date(f)
        try:
            result = cloudinary.uploader.upload(
                f, folder='photo-friends', resource_type=resource_type,
            )
            media = Media.objects.create(
                album=album,
                uploaded_by=request.user,
                cloudinary_url=result['secure_url'],
                cloudinary_id=result['public_id'],
                media_type='video' if is_video else 'photo',
                filename=f.name,
                taken_at=taken_at,
            )
            if not album.cover_url and not is_video:
                album.cover_url = result['secure_url']
                album.save(update_fields=['cover_url'])
            uploaded.append({'id': media.id, 'url': result['secure_url']})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'uploaded': uploaded})


@login_required
@require_POST
def invite_member_view(request, album_id):
    album = get_object_or_404(Album, id=album_id, created_by=request.user)
    username = request.POST.get('username', '').strip()
    try:
        user = User.objects.get(username=username)
        if user == request.user:
            return JsonResponse({'error': 'Você já é membro'}, status=400)
        AlbumMember.objects.get_or_create(album=album, user=user)
        name = user.get_full_name() or user.username
        return JsonResponse({'ok': True, 'name': name})
    except User.DoesNotExist:
        return JsonResponse({'error': 'Usuário não encontrado'}, status=404)


@login_required
@require_POST
def delete_album_view(request, album_id):
    album = get_object_or_404(Album, id=album_id, created_by=request.user)
    for m in album.media.all():
        try:
            cloudinary.uploader.destroy(
                m.cloudinary_id,
                resource_type='video' if m.media_type == 'video' else 'image',
            )
        except Exception:
            pass
    album.delete()
    return redirect('albums_list')


@login_required
@require_POST
def delete_media_view(request, media_id):
    media = get_object_or_404(Media, id=media_id, uploaded_by=request.user)
    try:
        cloudinary.uploader.destroy(
            media.cloudinary_id,
            resource_type='video' if media.media_type == 'video' else 'image',
        )
    except Exception:
        pass
    media.delete()
    return JsonResponse({'ok': True})


# ── HELPERS ──────────────────────────────────────────────────────────────────

def _send_verification_email(user, code):
    first_name = user.first_name or user.username
    subject = 'Photo Friends — Verifique seu e-mail'
    text = (
        f'Olá {first_name}!\n\n'
        f'Seu código de verificação é: {code}\n\n'
        f'Expira em 15 minutos.\n\n— Photo Friends'
    )
    html = render_to_string('landing/email/verify.html', {
        'first_name': first_name,
        'code': code,
    })
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    msg.attach_alternative(html, 'text/html')
    msg.send(fail_silently=True)


def _send_reset_email(user, code):
    first_name = user.first_name or user.username
    subject = 'Photo Friends — Redefinição de senha'
    text = (
        f'Olá {first_name}!\n\n'
        f'Seu código para redefinir a senha é: {code}\n\n'
        f'Expira em 15 minutos.\n\nSe não foi você, ignore este e-mail.'
    )
    html = render_to_string('landing/email/reset.html', {
        'first_name': first_name,
        'code': code,
    })
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    msg.attach_alternative(html, 'text/html')
    msg.send(fail_silently=True)


@login_required
def my_uploads_view(request):
    media_qs = (
        Media.objects.filter(uploaded_by=request.user)
        .select_related('album', 'uploaded_by')
        .annotate(sort_date=Coalesce('taken_at', 'uploaded_at'))
        .order_by('-sort_date')
    )

    albums_dict = {}
    albums_order = []
    for m in media_qs:
        aid = m.album_id
        if aid not in albums_dict:
            albums_dict[aid] = {'album': m.album, 'items': []}
            albums_order.append(aid)
        albums_dict[aid]['items'].append(m)

    return render(request, 'landing/uploads.html', {
        'albums_with_media': [albums_dict[aid] for aid in albums_order],
        'total': media_qs.count(),
        'total_photos': media_qs.filter(media_type='photo').count(),
        'total_videos': media_qs.filter(media_type='video').count(),
    })


# ── COMMUNITIES ──────────────────────────────────────────────────────────────

@login_required
def communities_list_view(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        if name:
            community = Community.objects.create(
                name=name, description=description, created_by=request.user
            )
            CommunityMember.objects.create(
                community=community, user=request.user, role=CommunityMember.ADMIN
            )
            return redirect('community_detail', community_id=community.id)

    communities = Community.objects.filter(members=request.user).distinct()
    return render(request, 'landing/communities/list.html', {'communities': communities})


@login_required
def community_detail_view(request, community_id):
    community = get_object_or_404(Community, id=community_id)
    membership = CommunityMember.objects.filter(community=community, user=request.user).first()
    if not membership:
        return redirect('communities_list')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        if name:
            album = Album.objects.create(
                name=name, description=description,
                created_by=request.user, community=community,
            )
            return redirect('album_detail', album_id=album.id)

    albums = community.albums.prefetch_related('media').order_by('-created_at')
    memberships = community.memberships.select_related('user', 'user__profile').order_by('joined_at')
    is_admin = membership.role == CommunityMember.ADMIN

    return render(request, 'landing/communities/detail.html', {
        'community': community,
        'albums': albums,
        'memberships': memberships,
        'is_admin': is_admin,
        'member_count': community.memberships.count(),
    })


@login_required
@require_POST
def invite_to_community_view(request, community_id):
    community = get_object_or_404(Community, id=community_id)
    if not CommunityMember.objects.filter(
        community=community, user=request.user, role=CommunityMember.ADMIN
    ).exists():
        return JsonResponse({'error': 'Apenas admins podem convidar'}, status=403)

    username = request.POST.get('username', '').strip()
    try:
        user = User.objects.get(username=username)
        if user == request.user:
            return JsonResponse({'error': 'Você já é membro'}, status=400)
        _, created = CommunityMember.objects.get_or_create(
            community=community, user=user,
            defaults={'role': CommunityMember.MEMBER},
        )
        name = user.get_full_name() or user.username
        msg = f'{name} adicionado!' if created else f'{name} já é membro'
        return JsonResponse({'ok': True, 'name': name, 'message': msg})
    except User.DoesNotExist:
        return JsonResponse({'error': 'Usuário não encontrado'}, status=404)


@login_required
@require_POST
def leave_community_view(request, community_id):
    community = get_object_or_404(Community, id=community_id)
    if community.created_by == request.user:
        return JsonResponse({'error': 'O fundador não pode sair. Delete a comunidade.'}, status=400)
    CommunityMember.objects.filter(community=community, user=request.user).delete()
    return redirect('communities_list')


@login_required
@require_POST
def delete_community_view(request, community_id):
    community = get_object_or_404(Community, id=community_id, created_by=request.user)
    for album in community.albums.all():
        for m in album.media.all():
            try:
                cloudinary.uploader.destroy(
                    m.cloudinary_id,
                    resource_type='video' if m.media_type == 'video' else 'image',
                )
            except Exception:
                pass
    community.delete()
    return redirect('communities_list')


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    success_url = reverse_lazy('login')

    def form_valid(self, form):
        messages.success(
            self.request,
            'Senha redefinida com sucesso! Faça login para continuar.',
        )
        return super().form_valid(form)


def _extract_exif_date(image_file):
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS
        from datetime import datetime

        image_file.seek(0)
        img = Image.open(io.BytesIO(image_file.read()))
        image_file.seek(0)

        exif_data = img._getexif()
        if not exif_data:
            return None

        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag in ('DateTimeOriginal', 'DateTimeDigitized', 'DateTime'):
                return datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
    except Exception:
        pass
    return None
