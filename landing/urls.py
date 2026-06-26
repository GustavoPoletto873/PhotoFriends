from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),

    # Auth
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('verify-email/', views.verify_email_view, name='verify_email'),
    path('resend-verification/', views.resend_verification_view, name='resend_verification'),
    path('uploads/', views.my_uploads_view, name='my_uploads'),

    # Communities
    path('communities/', views.communities_list_view, name='communities_list'),
    path('communities/<int:community_id>/', views.community_detail_view, name='community_detail'),
    path('communities/<int:community_id>/invite/', views.invite_to_community_view, name='invite_to_community'),
    path('communities/<int:community_id>/leave/', views.leave_community_view, name='leave_community'),
    path('communities/<int:community_id>/delete/', views.delete_community_view, name='delete_community'),

    # Albums
    path('albums/', views.albums_list_view, name='albums_list'),
    path('albums/<int:album_id>/', views.album_detail_view, name='album_detail'),
    path('albums/<int:album_id>/upload/', views.upload_media_view, name='upload_media'),
    path('albums/<int:album_id>/invite/', views.invite_member_view, name='invite_member'),
    path('albums/<int:album_id>/delete/', views.delete_album_view, name='delete_album'),

    # Media
    path('media/<int:media_id>/delete/', views.delete_media_view, name='delete_media'),
]
