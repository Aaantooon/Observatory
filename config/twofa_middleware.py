"""
2FA-гейт для /admin/ и /crm/ (01.09.2026).

Работает поверх django-otp: OTPMiddleware уже проставил request.user.is_verified()
(True, если в текущей сессии введён и принят код от подтверждённого TOTP-устройства).
Эта миддлварь просто решает, ОБЯЗАТЕЛЕН ли этот код прямо сейчас, и если да —
перенаправляет на страницу ввода кода вместо того, чтобы пускать staff-пользователя
дальше по одному лишь логину/паролю.

Управляется settings.REQUIRE_2FA (переменная REQUIRE_2FA в .env, по умолчанию
выключено) — см. комментарий рядом с REQUIRE_2FA в settings.py про безопасный
порядок включения и путь отката, если что-то пойдёт не так.
"""
from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

# Пути, которые должны оставаться доступны БЕЗ прохождения гейта — иначе
# невозможно будет ни залогиниться, ни настроить/ввести код.
_EXEMPT_PREFIXES = (
    '/admin/login/',
    '/admin/logout/',
    '/2fa/',
    '/static/',
)


class TwoFactorGateMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._gate_applies(request):
            return redirect(f"{reverse('twofa_verify')}?next={request.get_full_path()}")
        return self.get_response(request)

    def _gate_applies(self, request):
        if not getattr(settings, 'REQUIRE_2FA', False):
            return False
        path = request.path
        if not (path.startswith('/admin/') or path.startswith('/crm/')):
            return False
        if path.startswith(_EXEMPT_PREFIXES):
            return False
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated or not user.is_staff:
            # Не наш случай — обычный login_required/staff_member_required
            # сам решит, что делать с неавторизованным/не-staff пользователем.
            return False
        if user.is_verified():
            return False
        # Staff залогинен паролем, но код 2FA в этой сессии ещё не подтверждён.
        return True
