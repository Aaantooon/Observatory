"""
Настройка и проверка 2FA (TOTP) для /admin/ и /crm/ (01.09.2026).

Две страницы:
- /2fa/setup/  — привязать приложение-аутентификатор (QR-код), подтвердить кодом.
- /2fa/verify/ — ввести код при входе, когда REQUIRE_2FA включён.

Обе доступны только staff-пользователям (обычные посетители сюда не попадают).
"""
import base64
from io import BytesIO

import qrcode
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django_otp import login as otp_login
from django_otp.plugins.otp_totp.models import TOTPDevice


def _qr_data_uri(data: str) -> str:
    img = qrcode.make(data)
    buf = BytesIO()
    img.save(buf, format='PNG')
    encoded = base64.b64encode(buf.getvalue()).decode('ascii')
    return f'data:image/png;base64,{encoded}'


@login_required
@staff_member_required
def setup_2fa(request):
    confirmed_devices = TOTPDevice.objects.filter(user=request.user, confirmed=True)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'delete':
            device_id = request.POST.get('device_id')
            TOTPDevice.objects.filter(user=request.user, id=device_id).delete()
            messages.success(request, 'Устройство удалено.')
            return redirect('twofa_setup')

        if action == 'confirm':
            device_id = request.POST.get('device_id')
            token = request.POST.get('token', '').strip()
            try:
                device = TOTPDevice.objects.get(user=request.user, id=device_id, confirmed=False)
            except TOTPDevice.DoesNotExist:
                messages.error(request, 'Устройство для подтверждения не найдено — начни заново.')
                return redirect('twofa_setup')

            if device.verify_token(token):
                device.confirmed = True
                device.save()
                messages.success(
                    request,
                    'Готово — устройство подтверждено. Когда будешь готов включить обязательную '
                    'проверку кода при входе, попроси поставить REQUIRE_2FA=True в .env на сервере.'
                )
                return redirect('twofa_setup')
            else:
                messages.error(request, 'Код не подошёл — проверь время на телефоне и попробуй ещё раз.')

    # Показать (или создать) неподтверждённое устройство для сканирования.
    pending_device = TOTPDevice.objects.filter(user=request.user, confirmed=False).order_by('-id').first()
    if pending_device is None and request.GET.get('new') == '1':
        pending_device = TOTPDevice.objects.create(
            user=request.user,
            name=f'{request.user.username} (новое устройство)',
            confirmed=False,
        )

    qr_data_uri = None
    if pending_device is not None:
        qr_data_uri = _qr_data_uri(pending_device.config_url)

    return render(request, '2fa_setup.html', {
        'confirmed_devices': confirmed_devices,
        'pending_device': pending_device,
        'qr_data_uri': qr_data_uri,
        'require_2fa_active': settings.REQUIRE_2FA,
    })


@login_required
@staff_member_required
def verify_2fa(request):
    # Проверяем ?next= через url_has_allowed_host_and_scheme (тот же паттерн,
    # что уже используется в myapp/vk_id_auth.py::vk_login_start) — иначе
    # можно подсунуть внешний адрес и увести staff-пользователя после
    # прохождения 2FA на чужой сайт (открытый редирект).
    next_url = request.GET.get('next') or request.POST.get('next') or '/admin/'
    if not url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        next_url = '/admin/'

    if request.user.is_verified():
        return redirect(next_url)

    error = None
    if request.method == 'POST':
        token = request.POST.get('token', '').strip()
        matched_device = None
        for device in TOTPDevice.objects.filter(user=request.user, confirmed=True):
            if device.verify_token(token):
                matched_device = device
                break

        if matched_device is not None:
            otp_login(request, matched_device)
            return redirect(next_url)
        error = 'Код не подошёл. Попробуй ещё раз.'

    has_device = TOTPDevice.objects.filter(user=request.user, confirmed=True).exists()

    return render(request, '2fa_verify.html', {
        'next': next_url,
        'error': error,
        'has_device': has_device,
    })
