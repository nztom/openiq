from django.contrib import admin
from django.urls import path
from guilds import views,discord_auth,capture_api
urlpatterns=[path('capture/<int:guild_id>/<str:session>/',capture_api.ingest),path('healthz/',views.health),path('readyz/',views.ready),path('recover/',views.recover),path('events/shared/<uuid:token>/',views.ally_event),path('onboard/',views.onboard),path('auth/discord/',discord_auth.begin),path('auth/discord/callback/',discord_auth.callback),path('',views.index),path('login/',discord_auth.login_entry),path('logout/',discord_auth.logout_entry),path('admin/',admin.site.urls),path('api/<int:guild_id>/state/',views.state),path('api/<int:guild_id>/<str:module>/<str:name>/',views.action),path('ocr/<int:guild_id>/',views.ocr_view),path('recap/<uuid:token>/',views.recap)]
