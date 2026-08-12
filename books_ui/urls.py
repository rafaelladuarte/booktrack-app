from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('', views.library_view, name='library'),
    path('book/create/', views.create_book_view, name='create_book'),
    path('book/<int:book_id>/', views.book_detail_view, name='book_detail'),
    path('book/<int:book_id>/edit-book/', views.edit_book_view, name='edit_book'),
    path('book/<int:book_id>/edit-reading/', views.edit_reading_view, name='edit_reading'),
    path('book/<int:book_id>/delete/', views.delete_book_view, name='delete_book'),
    path('api/create-entity/<str:entity_type>/', views.create_entity_ajax_view, name='create_entity_ajax'),
]
