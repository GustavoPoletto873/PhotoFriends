import io
import json
import logging
from collections import defaultdict
from datetime import timedelta

logger = logging.getLogger(__name__)

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
from .models import Album, AlbumMember, Comment, Community, CommunityMember, Favorite, FriendRequest, Media, UserProfile


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

            profile.email_verified = True
            profile.save()

            login(request, user)
            return redirect('albums_list')
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
    # Fallback: always log the code so it's visible in Render logs if email fails
    logger.info('VERIFY CODE for %s: %s', user.email, code)

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
    try:
        msg.send(fail_silently=False)
        logger.info('SMTP verification email sent OK to %s', user.email)
    except Exception as e:
        logger.error('SMTP verification email failed for %s: %s', user.email, e)


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
    try:
        msg.send(fail_silently=False)
    except Exception as e:
        logger.error('SMTP reset email failed for %s: %s', user.email, e)


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
        'is_member': True,
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


# ── PROFILE ──────────────────────────────────────────────────────────────────

@login_required
def edit_profile_view(request):
    profile = request.user.profile
    error = None
    success = None

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        new_username = request.POST.get('username', '').strip()
        bio = request.POST.get('bio', '').strip()
        avatar_file = request.FILES.get('avatar')

        if not first_name or not new_username:
            error = 'Nome e usuário são obrigatórios.'
        elif new_username != request.user.username and User.objects.filter(username=new_username).exists():
            error = 'Esse usuário já está em uso.'
        else:
            request.user.first_name = first_name
            request.user.last_name = last_name
            request.user.username = new_username
            request.user.save()
            profile.bio = bio

            if avatar_file:
                content_type = avatar_file.content_type or ''
                is_video = content_type.startswith('video/')
                is_gif = 'gif' in content_type
                resource_type = 'video' if is_video else 'image'
                try:
                    if profile.avatar_id:
                        try:
                            cloudinary.uploader.destroy(profile.avatar_id,
                                resource_type='video' if profile.avatar_type == 'video' else 'image')
                        except Exception:
                            pass
                    result = cloudinary.uploader.upload(
                        avatar_file,
                        folder='photo-friends/avatars',
                        resource_type=resource_type,
                        transformation=[] if is_video else [{'width': 400, 'height': 400, 'crop': 'fill'}],
                    )
                    profile.avatar_url = result['secure_url']
                    profile.avatar_id = result['public_id']
                    profile.avatar_type = 'video' if is_video else ('gif' if is_gif else 'photo')
                except Exception as e:
                    error = f'Erro ao enviar avatar: {e}'

            if not error:
                profile.save()
                success = 'Perfil atualizado!'

    pending_requests = FriendRequest.objects.filter(to_user=request.user, status=FriendRequest.PENDING)
    friends_qs = User.objects.filter(
        Q(sent_friend_requests__to_user=request.user, sent_friend_requests__status=FriendRequest.ACCEPTED) |
        Q(received_friend_requests__from_user=request.user, received_friend_requests__status=FriendRequest.ACCEPTED)
    ).distinct().select_related('profile')
    friends = []
    for f in friends_qs:
        f.friend_count = FriendRequest.objects.filter(
            Q(from_user=f, status=FriendRequest.ACCEPTED) |
            Q(to_user=f, status=FriendRequest.ACCEPTED)
        ).count()
        friends.append(f)
    user_albums = Album.objects.filter(created_by=request.user, community__isnull=True)
    user_communities = Community.objects.filter(members=request.user).distinct()
    from itertools import groupby
    from django.utils.timezone import localtime
    favs_qs = list(Favorite.objects.filter(user=request.user).select_related('media', 'media__album').order_by('-media__uploaded_at'))
    favorites_by_date = []
    for date_key, items in groupby(favs_qs, key=lambda f: localtime(f.media.display_date).date()):
        favorites_by_date.append((date_key, list(items)))
    favorites_by_date.reverse()

    return render(request, 'landing/profile/edit.html', {
        'profile': profile,
        'error': error,
        'success': success,
        'pending_requests': pending_requests,
        'friends': friends,
        'friends_count': len(friends),
        'user_albums': user_albums,
        'user_communities': user_communities,
        'user_favorites': favs_qs,
        'favorites_by_date': favorites_by_date,
    })


def profile_view(request, username):
    target_user = get_object_or_404(User, username=username)
    profile = target_user.profile

    friendship_status = None
    if request.user.is_authenticated and request.user != target_user:
        req = FriendRequest.objects.filter(
            Q(from_user=request.user, to_user=target_user) |
            Q(from_user=target_user, to_user=request.user)
        ).first()
        if req:
            friendship_status = req.status if req.from_user == request.user else f'received_{req.status}'
        else:
            friendship_status = 'none'

    public_albums = Album.objects.filter(created_by=target_user, community__isnull=True)
    return render(request, 'landing/profile/view.html', {
        'target_user': target_user,
        'profile': profile,
        'friendship_status': friendship_status,
        'public_albums': public_albums,
    })


# ── FAVORITES ────────────────────────────────────────────────────────────────

@login_required
def favorites_view(request):
    favs = Favorite.objects.filter(user=request.user).select_related('media', 'media__album', 'media__uploaded_by')
    return render(request, 'landing/favorites.html', {'favorites': favs})


@login_required
@require_POST
def toggle_favorite_view(request, media_id):
    media = get_object_or_404(Media, id=media_id)
    fav, created = Favorite.objects.get_or_create(user=request.user, media=media)
    if not created:
        fav.delete()
        return JsonResponse({'favorited': False})
    return JsonResponse({'favorited': True})


# ── PHOTO EDITOR ─────────────────────────────────────────────────────────────

@login_required
@require_POST
def edit_media_view(request, media_id):
    import io, requests as req_lib
    from PIL import Image, ImageEnhance, ImageFilter

    media = get_object_or_404(Media, id=media_id, uploaded_by=request.user)

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Dados inválidos'}, status=400)

    brightness  = max(0.1, min(3.0, float(data.get('brightness',  1.0))))
    contrast    = max(0.1, min(3.0, float(data.get('contrast',    1.0))))
    saturation  = max(0.0, min(4.0, float(data.get('saturation',  1.0))))
    sharpness   = max(0.0, min(4.0, float(data.get('sharpness',   1.0))))
    blur_radius = max(0.0, min(20.0, float(data.get('blur',       0.0))))
    rotation    = int(data.get('rotation', 0)) % 360
    flip_h      = bool(data.get('flip_h', False))
    flip_v      = bool(data.get('flip_v', False))
    grayscale   = bool(data.get('grayscale', False))

    # Download original from Cloudinary
    resp = req_lib.get(media.cloudinary_url, timeout=30)
    resp.raise_for_status()
    img = Image.open(io.BytesIO(resp.content)).convert('RGBA')

    # Geometric transforms
    if rotation:
        img = img.rotate(-rotation, expand=True, resample=Image.BICUBIC)
    if flip_h:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    if flip_v:
        img = img.transpose(Image.FLIP_TOP_BOTTOM)

    # Colour / tone adjustments (operate on RGB copy, preserve alpha)
    rgb = img.convert('RGB')
    if grayscale:
        rgb = rgb.convert('L').convert('RGB')
    if brightness != 1.0:
        rgb = ImageEnhance.Brightness(rgb).enhance(brightness)
    if contrast != 1.0:
        rgb = ImageEnhance.Contrast(rgb).enhance(contrast)
    if saturation != 1.0:
        rgb = ImageEnhance.Color(rgb).enhance(saturation)
    if sharpness != 1.0:
        rgb = ImageEnhance.Sharpness(rgb).enhance(sharpness)
    if blur_radius > 0:
        rgb = rgb.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    # Merge back with original alpha channel
    r, g, b = rgb.split()
    a = img.split()[3]
    img = Image.merge('RGBA', (r, g, b, a))

    # Upload back (overwrite + CDN invalidate)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)

    result = cloudinary.uploader.upload(
        buf,
        public_id=media.cloudinary_id,
        overwrite=True,
        invalidate=True,
        resource_type='image',
        format='png',
    )
    media.cloudinary_url = result['secure_url']
    media.save()
    return JsonResponse({'url': media.cloudinary_url})


@login_required
@require_POST
def remove_bg_view(request, media_id):
    import io, requests as req_lib

    media = get_object_or_404(Media, id=media_id, uploaded_by=request.user)

    # Download original
    resp = req_lib.get(media.cloudinary_url, timeout=30)
    resp.raise_for_status()
    img_bytes = resp.content

    api_key = os.environ.get('REMOVE_BG_API_KEY', '')
    if not api_key:
        return JsonResponse({'error': 'Chave REMOVE_BG_API_KEY não configurada no servidor.'}, status=503)

    import requests as req_api
    try:
        resp_bg = req_api.post(
            'https://api.remove.bg/v1.0/removebg',
            files={'image_file': ('image.jpg', img_bytes)},
            data={'size': 'auto'},
            headers={'X-Api-Key': api_key},
            timeout=60,
        )
    except Exception as e:
        logger.error('remove.bg request error: %s', e)
        return JsonResponse({'error': 'Erro ao contactar API de remoção de fundo.'}, status=502)

    if resp_bg.status_code == 402:
        return JsonResponse({'error': 'Créditos da API remove.bg esgotados.'}, status=402)
    if resp_bg.status_code != 200:
        logger.error('remove.bg error %s: %s', resp_bg.status_code, resp_bg.text)
        return JsonResponse({'error': f'Erro na API: {resp_bg.status_code}'}, status=502)

    from PIL import Image
    result_img = Image.open(io.BytesIO(resp_bg.content)).convert('RGBA')

    buf = io.BytesIO()
    result_img.save(buf, format='PNG')
    buf.seek(0)

    result = cloudinary.uploader.upload(
        buf,
        public_id=media.cloudinary_id,
        overwrite=True,
        invalidate=True,
        resource_type='image',
        format='png',
    )
    media.cloudinary_url = result['secure_url']
    media.save()
    return JsonResponse({'url': media.cloudinary_url})


# ── COMMENTS ─────────────────────────────────────────────────────────────────

@login_required
def media_comments_view(request, media_id):
    media = get_object_or_404(Media, id=media_id)
    if request.method == 'POST':
        body = request.POST.get('body', '').strip()
        if body:
            Comment.objects.create(user=request.user, media=media, body=body)
    comments = media.comments.select_related('user', 'user__profile').order_by('created_at')
    data = [
        {
            'id': c.id,
            'username': c.user.username,
            'name': c.user.get_full_name() or c.user.username,
            'avatar': c.user.profile.avatar_url if hasattr(c.user, 'profile') else '',
            'body': c.body,
            'created_at': c.created_at.strftime('%d/%m %H:%M'),
            'is_mine': c.user == request.user,
        }
        for c in comments
    ]
    return JsonResponse({'comments': data})


@login_required
@require_POST
def delete_comment_view(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    if comment.user == request.user or request.user.profile.is_ceo:
        comment.delete()
        return JsonResponse({'ok': True})
    return JsonResponse({'error': 'Sem permissão'}, status=403)


# ── COMMUNITY CHAT ────────────────────────────────────────────────────────────

@login_required
def community_chat_view(request, community_id):
    community = get_object_or_404(Community, id=community_id)
    is_member = CommunityMember.objects.filter(community=community, user=request.user).exists()

    if not is_member and community.is_private:
        return JsonResponse({'error': 'Sem acesso'}, status=403)

    if request.method == 'POST':
        if not is_member:
            return JsonResponse({'error': 'Apenas membros podem enviar mensagens'}, status=403)
        body = request.POST.get('body', '').strip()
        if body:
            Comment.objects.create(user=request.user, community=community, body=body)

    messages_qs = community.messages.select_related('user', 'user__profile').order_by('created_at')
    data = [
        {
            'id': c.id,
            'username': c.user.username,
            'name': c.user.get_full_name() or c.user.username,
            'avatar': c.user.profile.avatar_url if hasattr(c.user, 'profile') else '',
            'avatar_type': c.user.profile.avatar_type if hasattr(c.user, 'profile') else 'photo',
            'body': c.body,
            'created_at': c.created_at.strftime('%d/%m %H:%M'),
            'is_mine': c.user == request.user,
        }
        for c in messages_qs
    ]
    return JsonResponse({'messages': data})


# ── DOWNLOAD ──────────────────────────────────────────────────────────────────

@login_required
def download_media_view(request, media_id):
    media = get_object_or_404(Media, id=media_id)
    album = media.album
    if album.community:
        has_access = CommunityMember.objects.filter(community=album.community, user=request.user).exists()
    else:
        has_access = (
            album.created_by == request.user
            or AlbumMember.objects.filter(album=album, user=request.user).exists()
        )
    if not has_access and not request.user.profile.is_ceo:
        return JsonResponse({'error': 'Sem acesso'}, status=403)
    return redirect(media.get_download_url())


# ── FRIENDS ───────────────────────────────────────────────────────────────────

@login_required
def friends_view(request):
    friends = User.objects.filter(
        Q(sent_friend_requests__to_user=request.user, sent_friend_requests__status=FriendRequest.ACCEPTED) |
        Q(received_friend_requests__from_user=request.user, received_friend_requests__status=FriendRequest.ACCEPTED)
    ).distinct().select_related('profile')
    pending_received = FriendRequest.objects.filter(to_user=request.user, status=FriendRequest.PENDING).select_related('from_user', 'from_user__profile')
    pending_sent = FriendRequest.objects.filter(from_user=request.user, status=FriendRequest.PENDING).select_related('to_user', 'to_user__profile')
    return render(request, 'landing/friends.html', {
        'friends': friends,
        'pending_received': pending_received,
        'pending_sent': pending_sent,
    })


@login_required
@require_POST
def send_friend_request_view(request, username):
    target = get_object_or_404(User, username=username)
    if target == request.user:
        return JsonResponse({'error': 'Você não pode se adicionar'}, status=400)
    existing = FriendRequest.objects.filter(
        Q(from_user=request.user, to_user=target) |
        Q(from_user=target, to_user=request.user)
    ).first()
    if existing:
        return JsonResponse({'error': 'Solicitação já existe'}, status=400)
    FriendRequest.objects.create(from_user=request.user, to_user=target)
    return JsonResponse({'ok': True})


@login_required
@require_POST
def respond_friend_request_view(request, request_id, action):
    freq = get_object_or_404(FriendRequest, id=request_id, to_user=request.user)
    if action == 'accept':
        freq.status = FriendRequest.ACCEPTED
        freq.save()
        return JsonResponse({'ok': True, 'status': 'accepted'})
    elif action == 'reject':
        freq.status = FriendRequest.REJECTED
        freq.save()
        return JsonResponse({'ok': True, 'status': 'rejected'})
    return JsonResponse({'error': 'Ação inválida'}, status=400)


# ── COMMUNITY PRIVACY ─────────────────────────────────────────────────────────

@login_required
@require_POST
def toggle_community_privacy_view(request, community_id):
    community = get_object_or_404(Community, id=community_id, created_by=request.user)
    community.is_private = not community.is_private
    community.save(update_fields=['is_private'])
    return JsonResponse({'is_private': community.is_private})


@login_required
@require_POST
def join_community_view(request, community_id):
    community = get_object_or_404(Community, id=community_id)
    if community.is_private:
        return JsonResponse({'error': 'Comunidade privada — entre por convite'}, status=403)
    CommunityMember.objects.get_or_create(community=community, user=request.user,
                                          defaults={'role': CommunityMember.MEMBER})
    return redirect('community_detail', community_id=community.id)


# ── CEO DASHBOARD ─────────────────────────────────────────────────────────────

@login_required
def ceo_dashboard_view(request):
    if not request.user.profile.is_ceo:
        return redirect('albums_list')
    users = User.objects.select_related('profile').prefetch_related('created_albums').order_by('date_joined')
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        new_role = request.POST.get('role')
        if user_id and new_role in dict(UserProfile.ROLE_CHOICES):
            target = get_object_or_404(User, id=user_id)
            target.profile.role = new_role
            target.profile.save(update_fields=['role'])
    total_media = Media.objects.count()
    total_albums = Album.objects.count()
    total_communities = Community.objects.count()
    return render(request, 'landing/ceo_dashboard.html', {
        'users': users,
        'total_media': total_media,
        'total_albums': total_albums,
        'total_communities': total_communities,
        'role_choices': UserProfile.ROLE_CHOICES,
    })


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
