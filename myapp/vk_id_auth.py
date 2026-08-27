import base64
import hashlib
import os
import secrets
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect

VK_ID_AUTHORIZE_URL = "https://id.vk.com/authorize"
VK_ID_TOKEN_URL = "https://id.vk.com/oauth2/auth"
VK_ID_USER_INFO_URL = "https://id.vk.com/oauth2/user_info"


def _generate_pkce_pair():
    code_verifier = base64.urlsafe_b64encode(os.urandom(40)).rstrip(b"=").decode("ascii")
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


def vk_login_start(request):
    """Redirects the user to VK ID authorization page."""
    code_verifier, code_challenge = _generate_pkce_pair()
    state = secrets.token_urlsafe(16)

    request.session["vk_code_verifier"] = code_verifier
    request.session["vk_oauth_state"] = state

    redirect_uri = request.build_absolute_uri("/")

    params = {
        "client_id": settings.VK_APP_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "email",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    query = urlencode(params)
    return redirect(f"{VK_ID_AUTHORIZE_URL}?{query}")


def vk_login_callback(request):
    """Handles the redirect back from VK ID, exchanges code for token, logs the user in."""
    code = request.GET.get("code")
    device_id = request.GET.get("device_id")
    state = request.GET.get("state")

    if not code or not device_id:
        return HttpResponseBadRequest("Missing code or device_id from VK ID")

    saved_state = request.session.pop("vk_oauth_state", None)
    code_verifier = request.session.pop("vk_code_verifier", None)

    if not saved_state or state != saved_state:
        return HttpResponseBadRequest("Invalid state parameter")
    if not code_verifier:
        return HttpResponseBadRequest("Missing code_verifier in session")

    redirect_uri = request.build_absolute_uri("/")

    token_response = requests.post(
        VK_ID_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": code_verifier,
            "redirect_uri": redirect_uri,
            "client_id": settings.VK_APP_ID,
            "device_id": device_id,
            "state": state,
        },
        timeout=10,
    )

    if token_response.status_code != 200:
        return HttpResponseBadRequest(f"VK token exchange failed: {token_response.text}")

    token_data = token_response.json()
    access_token = token_data.get("access_token")
    if not access_token:
        return HttpResponseBadRequest(f"No access_token in VK response: {token_data}")

    user_info_response = requests.post(
        VK_ID_USER_INFO_URL,
        data={
            "access_token": access_token,
            "client_id": settings.VK_APP_ID,
        },
        timeout=10,
    )
    user_info = user_info_response.json().get("user", {})

    vk_user_id = user_info.get("user_id") or user_info.get("id")
    first_name = user_info.get("first_name", "")
    last_name = user_info.get("last_name", "")
    email = user_info.get("email", "")

    if not vk_user_id:
        return HttpResponseBadRequest(f"No user id in VK response: {user_info}")

    username = f"vk_{vk_user_id}"
    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            "first_name": first_name,
            "last_name": last_name,
            "email": email or "",
        },
    )
    if not created:
        user.first_name = first_name or user.first_name
        user.last_name = last_name or user.last_name
        if email:
            user.email = email
        user.save()

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return redirect("home")