from django.contrib import admin
from django.contrib.admin import AdminSite
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin, GroupAdmin
from django.utils.translation import gettext_lazy as _

# Регистрируем модели из bot_api
from bot_api.models import User as VKUser, Exercise, Result, ExerciseProgress, Notification, Review, Channel, Post

from bot_api.admin import (
    UserAdmin, ExerciseAdmin, ResultAdmin, ExerciseProgressAdmin, NotificationAdmin, ReviewAdmin,
    ChannelAdmin, PostAdmin,
)
# Регистрируем модели из myapp
try:
    from myapp.models import Module, UserCourseProgress, GameAssociation, UserStreak, ModuleComment, UserProfile, MindMapNodePosition
    from myapp.admin import ModuleAdmin, UserCourseProgressAdmin, GameAssociationAdmin, UserStreakAdmin, ModuleCommentAdmin, UserProfileAdmin, MindMapNodePositionAdmin
except ImportError:
    pass


class CustomAdminSite(AdminSite):
    site_header = "🔦 Путь наблюдателя"
    site_title = "Путь наблюдателя"
    index_title = "📋 Панель управления"
    site_url = "/"

    def get_app_list(self, request):
        app_list = super().get_app_list(request)
        
        app_names = {
            'bot_api': '📊 Основные данные',
            'myapp': '📚 Курс и прогресс',
            'auth': '👤 Пользователи',
            'authtoken': '🔑 Токены',
            'social_django': '🔗 Социальные сети',
            'machina': '💬 Форум',
            'machina_forum_conversation': '💬 Форум',
            'machina_forum_attachments': '💬 Форум',
            'machina_forum_polls': '💬 Форум',
            'machina_forum_tracking': '💬 Форум',
            'machina_forum_permission': '💬 Форум',
            'machina_forum_member': '💬 Форум',
        }
        
        for app in app_list:
            app_name = app.get('app_label', '')
            if app_name in app_names:
                app['name'] = app_names[app_name]
        
        return app_list


admin_site = CustomAdminSite(name='observatory_admin')

admin_site.register(VKUser, UserAdmin)
admin_site.register(Exercise, ExerciseAdmin)
admin_site.register(Result, ResultAdmin)
admin_site.register(ExerciseProgress, ExerciseProgressAdmin)
admin_site.register(Notification, NotificationAdmin)
admin_site.register(Review, ReviewAdmin)
admin_site.register(Channel, ChannelAdmin)
admin_site.register(Post, PostAdmin)

try:
    admin_site.register(Module, ModuleAdmin)
    admin_site.register(UserCourseProgress, UserCourseProgressAdmin)
    admin_site.register(GameAssociation, GameAssociationAdmin)
    admin_site.register(UserStreak, UserStreakAdmin)
    admin_site.register(ModuleComment, ModuleCommentAdmin)
    admin_site.register(UserProfile, UserProfileAdmin)
    admin_site.register(MindMapNodePosition, MindMapNodePositionAdmin)
except NameError:
    pass

admin_site.register(User, DjangoUserAdmin)
admin_site.register(Group, GroupAdmin)