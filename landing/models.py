import random
import string
from django.db import models
from django.contrib.auth.models import User

ALBUM_GRADIENTS = [
    'linear-gradient(135deg,#667eea,#764ba2)',
    'linear-gradient(135deg,#f093fb,#f5576c)',
    'linear-gradient(135deg,#4facfe,#00f2fe)',
    'linear-gradient(135deg,#43e97b,#38f9d7)',
    'linear-gradient(135deg,#fa709a,#fee140)',
    'linear-gradient(135deg,#a18cd1,#fbc2eb)',
    'linear-gradient(135deg,#fccb90,#d57eeb)',
    'linear-gradient(135deg,#e0c3fc,#8ec5fc)',
    'linear-gradient(135deg,#fd7043,#ff8f00)',
    'linear-gradient(135deg,#26c6da,#00838f)',
]

ALBUM_TAB_COLORS = [
    '#667eea', '#f093fb', '#4facfe', '#43e97b', '#fa709a',
    '#a18cd1', '#fccb90', '#e0c3fc', '#fd7043', '#26c6da',
]


class UserProfile(models.Model):
    STANDARD = 'standard'
    PRO = 'pro'
    CEO = 'ceo'
    ROLE_CHOICES = [(STANDARD, 'Padrão'), (PRO, 'Pro'), (CEO, 'CEO')]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar_url = models.CharField(max_length=500, blank=True)
    avatar_id = models.CharField(max_length=200, blank=True)
    avatar_type = models.CharField(max_length=10, default='photo')  # photo, video, gif
    bio = models.TextField(blank=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=STANDARD)
    email_verified = models.BooleanField(default=False)
    verification_code = models.CharField(max_length=6, blank=True)
    verification_sent_at = models.DateTimeField(null=True, blank=True)
    reset_code = models.CharField(max_length=6, blank=True)
    reset_code_sent_at = models.DateTimeField(null=True, blank=True)

    def generate_code(self, field='verification'):
        code = ''.join(random.choices(string.digits, k=6))
        if field == 'verification':
            self.verification_code = code
        else:
            self.reset_code = code
        return code

    @property
    def is_ceo(self):
        return self.role == self.CEO

    def __str__(self):
        return f'Profile({self.user.username})'


class Community(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    cover_url = models.CharField(max_length=500, blank=True)
    cover_id = models.CharField(max_length=200, blank=True)
    is_private = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_communities')
    members = models.ManyToManyField(User, through='CommunityMember', related_name='communities', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'communities'

    def __str__(self):
        return self.name

    @property
    def gradient(self):
        return ALBUM_GRADIENTS[self.id % len(ALBUM_GRADIENTS)]

    @property
    def tab_color(self):
        return ALBUM_TAB_COLORS[self.id % len(ALBUM_TAB_COLORS)]


class CommunityMember(models.Model):
    ADMIN = 'admin'
    MEMBER = 'member'
    ROLE_CHOICES = [(ADMIN, 'Admin'), (MEMBER, 'Membro')]

    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='community_memberships')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('community', 'user')

    def __str__(self):
        return f'{self.user.username} → {self.community.name} ({self.role})'


class Album(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    cover_url = models.CharField(max_length=500, blank=True)
    community = models.ForeignKey(
        Community, null=True, blank=True,
        on_delete=models.CASCADE, related_name='albums',
    )
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_albums')
    members = models.ManyToManyField(User, through='AlbumMember', related_name='shared_albums', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def gradient(self):
        return ALBUM_GRADIENTS[self.id % len(ALBUM_GRADIENTS)]

    @property
    def tab_color(self):
        return ALBUM_TAB_COLORS[self.id % len(ALBUM_TAB_COLORS)]


class AlbumMember(models.Model):
    album = models.ForeignKey(Album, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('album', 'user')


class Media(models.Model):
    PHOTO = 'photo'
    VIDEO = 'video'
    TYPE_CHOICES = [(PHOTO, 'Foto'), (VIDEO, 'Vídeo')]

    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name='media')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    cloudinary_url = models.CharField(max_length=500)
    cloudinary_id = models.CharField(max_length=200)
    # Backup da imagem original (preenchido no primeiro edit destrutivo; vazio = nunca editada)
    original_url = models.CharField(max_length=500, blank=True, default='')
    media_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    filename = models.CharField(max_length=200, blank=True)
    taken_at = models.DateTimeField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f'{self.media_type}: {self.filename}'

    @property
    def display_date(self):
        return self.taken_at or self.uploaded_at

    def get_download_url(self):
        if self.media_type == 'video':
            return self.cloudinary_url.replace('/video/upload/', '/video/upload/fl_attachment/')
        return self.cloudinary_url.replace('/image/upload/', '/image/upload/fl_attachment/')


class Comment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    media = models.ForeignKey(Media, on_delete=models.CASCADE, related_name='comments', null=True, blank=True)
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name='messages', null=True, blank=True)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.user.username}: {self.body[:40]}'


class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorites')
    media = models.ForeignKey(Media, on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'media')
        ordering = ['-created_at']


class FriendRequest(models.Model):
    PENDING = 'pending'
    ACCEPTED = 'accepted'
    REJECTED = 'rejected'
    STATUS_CHOICES = [(PENDING, 'Pendente'), (ACCEPTED, 'Aceito'), (REJECTED, 'Recusado')]

    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_friend_requests')
    to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_friend_requests')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('from_user', 'to_user')

    def __str__(self):
        return f'{self.from_user.username} → {self.to_user.username} ({self.status})'
