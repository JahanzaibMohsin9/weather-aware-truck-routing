from django.urls import path

from . import views

urlpatterns = [
    path("health", views.health),
    path("places", views.places),
    path("plan", views.plan),
    path("plan/stream", views.plan_stream),
    path("heatmap", views.heatmap),
]
