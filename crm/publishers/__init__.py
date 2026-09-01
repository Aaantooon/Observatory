"""Реестр адаптеров публикации по платформам — по одному модулю на
платформу, каждый реализует publish(channel, post) -> (bool, str).

Сейчас реализован только VK. Telegram и MAX — добавить сюда модулем с
такой же сигнатурой publish() и зарегистрировать в PUBLISHERS ниже,
остальной код (management-команда publish_due_posts, CRM-форма) их
подхватит без изменений."""
from . import vk

PUBLISHERS = {
    'vk': vk,
}
