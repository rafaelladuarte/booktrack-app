from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('', views.library_view, name='library'),
    path('book/<int:book_id>/', views.book_detail_view, name='book_detail'),
]
