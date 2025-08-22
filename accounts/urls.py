from django.urls import path
from accounts.views import auth_connect,tokens,callback,smartvaultcallback,smartvault_auth,smartvault_refresh,smartvaultauth_connect,SmartVaultWebhookView


urlpatterns = [
    path("auth/connect/", auth_connect, name="oauth_connect"),
    path("auth/tokens/", tokens, name="oauth_tokens"),
    path("auth/callback/", callback, name="oauth_callback"),
    path("smartvault/callback/", smartvaultcallback),


    path("smartvault/connect/", smartvaultauth_connect, name="oauth_connect"),
    path("smartvault/auth/", smartvault_auth, name="smartvault-auth"),
    path("smartvault/refresh/", smartvault_refresh, name="smartvault-refresh"),

    path('smartvault/webhook/', SmartVaultWebhookView.as_view(), name='smartvault_webhook'),
]