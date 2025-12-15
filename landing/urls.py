from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('results/', views.results, name='results'),
    path('api/chat/', views.chat_api, name='chat_api'),
    path('resource/', views.resource_viewer, name='resource_viewer'),
    path('avatar/', views.avatar_creation, name='avatar_creation'),
    path('avatar/generate/', views.generate_avatar, name='generate_avatar'),
    path('avatar/download/<int:avatar_id>/', views.download_avatar, name='download_avatar'),
    path('wishlist/', views.wishlist_signup, name='wishlist_signup'),
    path('api/feedback/', views.submit_feedback, name='submit_feedback'),
    path('api/partner/', views.submit_partner_interest, name='submit_partner_interest'),
]
