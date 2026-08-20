import os
import ssl
from socketserver import ThreadingMixIn
from wsgiref.simple_server import make_server, WSGIServer

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()


class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


def run(host='127.0.0.1', port=443, certfile='localhost.crt', keyfile='localhost.key'):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=certfile, keyfile=keyfile)

    httpd = make_server(host, port, application, server_class=ThreadingWSGIServer)
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)

    print(f"Serving HTTPS on https://{host}:{port}/ ...")
    print("Нажмите Ctrl+C для остановки.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nОстановлено.")


if __name__ == '__main__':
    run()