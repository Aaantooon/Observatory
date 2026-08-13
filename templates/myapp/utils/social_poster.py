import requests
from django.conf import settings

def send_telegram(token, chat_id, text, image_path=None):
    """Отправляет сообщение в Telegram."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    if image_path:
        files = {'photo': open(image_path, 'rb')}
        data = {'chat_id': chat_id, 'caption': text}
        resp = requests.post(f"https://api.telegram.org/bot{token}/sendPhoto", data=data, files=files)
    else:
        resp = requests.post(url, json={'chat_id': chat_id, 'text': text})
    return resp.json()

def send_vk(token, owner_id, text, image_path=None):
    """Отправляет пост на стену ВКонтакте."""
    # Загрузка фото (если есть)
    attachments = ''
    if image_path:
        # Получаем сервер для загрузки
        upload_url = requests.get(
            'https://api.vk.com/method/photos.getWallUploadServer',
            params={'access_token': token, 'v': '5.131'}
        ).json().get('response', {}).get('upload_url')
        if upload_url:
            files = {'photo': open(image_path, 'rb')}
            upload_resp = requests.post(upload_url, files=files).json()
            # Сохраняем фото
            save_params = {
                'photo': upload_resp['photo'],
                'server': upload_resp['server'],
                'hash': upload_resp['hash'],
                'access_token': token,
                'v': '5.131'
            }
            save_resp = requests.get('https://api.vk.com/method/photos.saveWallPhoto', params=save_params).json()
            if 'response' in save_resp:
                photo = save_resp['response'][0]
                attachments = f"photo{photo['owner_id']}_{photo['id']}"
    # Отправка поста
    params = {
        'access_token': token,
        'owner_id': owner_id,
        'message': text,
        'v': '5.131'
    }
    if attachments:
        params['attachments'] = attachments
    resp = requests.get('https://api.vk.com/method/wall.post', params=params)
    return resp.json()