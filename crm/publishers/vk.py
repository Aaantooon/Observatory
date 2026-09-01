"""VK-адаптер публикации постов на стену сообщества.

Публикует Post.text в группу VK через wall.post. Токен и ID группы
берутся из модели Channel (bot_api.models) — их вводит психолог через
/admin/ (защищено 2FA), эта сессия их не видит и не вводит сама.

Токен должен быть выпущен именно для сообщества (Управление сообществом →
Работа с API → Ключи доступа) с правом «wall» — не личный токен
пользователя.
"""
import logging

import vk_api
from vk_api.exceptions import ApiError

logger = logging.getLogger(__name__)


def publish(channel, post):
    """Публикует post на стену VK-сообщества channel.

    Возвращает (True, external_post_id) при успехе,
    (False, текст_ошибки) при неудаче — вызывающая сторона (management-
    команда) сама решает, что делать с ошибкой (записать в
    PostChannelStatus.error_message, залогировать и т.д.), сюда сеть/API
    не поднимаются исключением наружу.
    """
    try:
        group_id = abs(int(channel.external_id))
    except (TypeError, ValueError):
        return False, f"Некорректный ID группы в канале «{channel.name}»: {channel.external_id!r}"

    if not channel.access_token:
        return False, f"У канала «{channel.name}» не задан токен доступа"

    try:
        session = vk_api.VkApi(token=channel.access_token)
        api = session.get_api()
        response = api.wall.post(
            owner_id=-group_id,
            from_group=1,
            message=post.text,
        )
    except ApiError as e:
        logger.error(f"VK publish failed: канал {channel.id}, пост {post.id}: {e}")
        return False, str(e)
    except Exception as e:
        logger.error(f"VK publish: неожиданная ошибка, канал {channel.id}, пост {post.id}: {e}")
        return False, str(e)

    post_id = response.get('post_id') if isinstance(response, dict) else None
    external_id = f"-{group_id}_{post_id}" if post_id is not None else ""
    return True, external_id
