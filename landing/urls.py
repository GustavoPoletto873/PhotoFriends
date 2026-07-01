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

    # Profile
    path('profile/', views.edit_profile_view, name='edit_profile'),
    path('profile/<str:username>/', views.profile_view, name='profile'),

    # Favorites
    path('favorites/', views.favorites_view, name='favorites'),
    path('media/<int:media_id>/favorite/', views.toggle_favorite_view, name='toggle_favorite'),

    # Comments
    path('media/<int:media_id>/comments/', views.media_comments_view, name='media_comments'),
    path('comments/<int:comment_id>/delete/', views.delete_comment_view, name='delete_comment'),

    # Download
    path('media/<int:media_id>/download/', views.download_media_view, name='download_media'),

    # Friends
    path('friends/', views.friends_view, name='friends'),
    path('friends/request/<str:username>/', views.send_friend_request_view, name='send_friend_request'),
    path('friends/respond/<int:request_id>/<str:action>/', views.respond_friend_request_view, name='respond_friend_request'),

    # Communities
    path('communities/', views.communities_list_view, name='communities_list'),
    path('communities/<int:community_id>/', views.community_detail_view, name='community_detail'),
    path('communities/<int:community_id>/invite/', views.invite_to_community_view, name='invite_to_community'),
    path('communities/<int:community_id>/leave/', views.leave_community_view, name='leave_community'),
    path('communities/<int:community_id>/delete/', views.delete_community_view, name='delete_community'),
    path('communities/<int:community_id>/privacy/', views.toggle_community_privacy_view, name='toggle_community_privacy'),
    path('communities/<int:community_id>/join/', views.join_community_view, name='join_community'),
    path('communities/<int:community_id>/chat/', views.community_chat_view, name='community_chat'),

    # Albums
    path('albums/', views.albums_list_view, name='albums_list'),
    path('albums/<int:album_id>/', views.album_detail_view, name='album_detail'),
    path('albums/<int:album_id>/upload/', views.upload_media_view, name='upload_media'),
    path('albums/<int:album_id>/invite/', views.invite_member_view, name='invite_member'),
    path('albums/<int:album_id>/delete/', views.delete_album_view, name='delete_album'),

    # Media
    path('media/<int:media_id>/delete/', views.delete_media_view, name='delete_media'),
    path('media/<int:media_id>/edit/', views.edit_media_view, name='edit_media'),
    path('media/<int:media_id>/remove-bg/', views.remove_bg_view, name='remove_bg'),

    # CEO
    path('ceo/', views.ceo_dashboard_view, name='ceo_dashboard'),
]
