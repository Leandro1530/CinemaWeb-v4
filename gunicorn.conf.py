# gunicorn.conf.py - Configuración de Gunicorn para producción

import multiprocessing
import os

# Configuración del servidor
bind = "127.0.0.1:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 120
keepalive = 5
max_requests = 1000
max_requests_jitter = 50
preload_app = True

# Configuración de archivos
chdir = "/var/www/cinema"
user = "www-data"
group = "www-data"
tmp_upload_dir = None

# Logging
accesslog = "/var/log/cinema/access.log"
errorlog = "/var/log/cinema/error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# PID file
pidfile = "/var/run/cinema/gunicorn.pid"

# SSL (si se usa directamente)
# keyfile = "/etc/ssl/private/your-domain.key"
# certfile = "/etc/ssl/certs/your-domain.crt"

# Configuración de proceso
daemon = False
proc_name = "cinema_app"

# Hooks
def on_starting(server):
    server.log.info("Iniciando Cinema App")

def on_reload(server):
    server.log.info("Recargando Cinema App")

def worker_int(worker):
    worker.log.info("Worker recibió INT o QUIT signal")

def pre_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_worker_init(worker):
    worker.log.info("Worker inicializado (pid: %s)", worker.pid)

def worker_abort(worker):
    worker.log.info("Worker recibió SIGABRT signal")