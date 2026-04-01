"""
Troubleshoot server from Database, Software, and Network perspectives.
Run: python manage.py troubleshoot_server [--host 192.168.2.216] [--port 8000]
"""
import socket
import sys
from django.core.management.base import BaseCommand
from django.db import connection
from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from io import StringIO


class Command(BaseCommand):
    help = 'Troubleshoot server: database, application config, and network (DB/software/network engineer style)'

    def add_arguments(self, parser):
        parser.add_argument('--host', default='192.168.2.216', help='Host to check (e.g. server IP)')
        parser.add_argument('--port', type=int, default=8000, help='Port to check')
        parser.add_argument('--skip-network', action='store_true', help='Skip network checks (e.g. when DB is remote)')

    def _section(self, title, icon=''):
        self.stdout.write('')
        self.stdout.write(self.style.HTTP_INFO('=' * 70))
        self.stdout.write(self.style.HTTP_INFO('  %s %s' % (icon, title)))
        self.stdout.write(self.style.HTTP_INFO('=' * 70))

    def _ok(self, msg):
        self.stdout.write(self.style.SUCCESS('  [OK] %s' % msg))

    def _fail(self, msg):
        self.stdout.write(self.style.ERROR('  [FAIL] %s' % msg))

    def _warn(self, msg):
        self.stdout.write(self.style.WARNING('  [WARN] %s' % msg))

    def _info(self, msg):
        self.stdout.write('  %s' % msg)

    def handle(self, *args, **options):
        host = options['host']
        port = options['port']
        skip_network = options['skip_network']
        issues = []

        # --- DATABASE ENGINEER CHECKS ---
        self._section('DATABASE (DB Engineer)', '[DB]')
        db = settings.DATABASES.get('default', {})
        engine = db.get('ENGINE', '')
        name = db.get('NAME', '')
        db_host = db.get('HOST', 'localhost')
        db_port = db.get('PORT', '5432')

        self._info('Engine: %s' % engine)
        self._info('Name: %s' % name)
        self._info('Host: %s' % (db_host or 'localhost'))
        self._info('Port: %s' % (db_port or 'default)'))

        if 'postgresql' not in engine:
            self._fail('Only PostgreSQL is supported. Engine: %s' % engine)
            issues.append('Database engine not PostgreSQL')
        else:
            self._ok('Engine is PostgreSQL')

        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                self._ok('Connection test (SELECT 1) succeeded')
        except Exception as e:
            self._fail('Connection failed: %s' % e)
            issues.append('Database connection failed')

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT version();")
                row = cursor.fetchone()
                self._info('Server: %s' % (row[0][:80] + '...' if row and len(row[0]) > 80 else (row[0] if row else '?')))
        except Exception as e:
            self._warn('Could not get version: %s' % e)

        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT count(*) FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'hospital_screeningchecktemplate'
                """)
                row = cursor.fetchone()
                if row and row[0] > 0:
                    self._ok('Screening tables exist (hospital_screeningchecktemplate)')
                else:
                    self._warn('Screening tables missing. Run: python manage.py migrate hospital')
                    issues.append('Screening migration not applied')
        except Exception as e:
            self._warn('Could not check screening table: %s' % e)

        try:
            out = StringIO()
            call_command('showmigrations', 'hospital', '--list', stdout=out, verbosity=0)
            unapplied = [line for line in out.getvalue().splitlines() if '[ ]' in line]
            if unapplied:
                self._warn('%d unapplied migration(s) in hospital' % len(unapplied))
                issues.append('Pending migrations')
            else:
                self._ok('No unapplied hospital migrations')
        except Exception as e:
            self._warn('Could not check migrations: %s' % e)

        # --- SOFTWARE ENGINEER CHECKS ---
        self._section('APPLICATION (Software Engineer)', '[APP]')
        self._info('DEBUG: %s' % settings.DEBUG)
        self._info('ALLOWED_HOSTS: %s' % (settings.ALLOWED_HOSTS[:5] if len(settings.ALLOWED_HOSTS) > 5 else settings.ALLOWED_HOSTS))
        if host and host not in settings.ALLOWED_HOSTS:
            try:
                # PermissiveHostMiddleware may add private IPs in DEBUG
                from django.http import HttpRequest
                req = HttpRequest()
                req.META['HTTP_HOST'] = host
                # Check if middleware would allow it
                if settings.DEBUG and host.startswith(('192.168.', '10.')):
                    self._warn('%s not in ALLOWED_HOSTS but may be allowed in DEBUG (private IP)' % host)
                else:
                    self._fail('%s not in ALLOWED_HOSTS' % host)
                    issues.append('Host not in ALLOWED_HOSTS')
            except Exception:
                self._warn('%s not in ALLOWED_HOSTS' % host)
        else:
            self._ok('Host %s allowed' % host)

        try:
            cache.set('troubleshoot_test', 1, 10)
            if cache.get('troubleshoot_test') == 1:
                self._ok('Cache (set/get) OK')
            else:
                self._warn('Cache test failed')
        except Exception as e:
            self._warn('Cache: %s' % e)

        # URL conf: screening routes
        try:
            from django.urls import reverse
            reverse('hospital:screening_dashboard')
            self._ok('URL reverse hospital:screening_dashboard OK')
        except Exception as e:
            self._warn('URL screening_dashboard: %s' % e)
            issues.append('Screening URL not resolvable')

        # --- NETWORK ENGINEER CHECKS ---
        if not skip_network:
            self._section('NETWORK (Network Engineer)', '[NET]')
            self._info('Target: %s:%s' % (host, port))

            # DNS / resolution
            try:
                socket.gethostbyname(host)
                self._ok('Resolved %s' % host)
            except socket.gaierror as e:
                self._fail('Could not resolve %s: %s' % (host, e))
                issues.append('Host resolution failed')
            except Exception as e:
                self._warn('Resolution: %s' % e)

            # TCP connect
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                sock.connect((host, port))
                sock.close()
                self._ok('TCP connection to %s:%s succeeded (service is listening)' % (host, port))
            except socket.timeout:
                self._fail('Connection to %s:%s timed out (firewall or service down)' % (host, port))
                issues.append('Port %s unreachable (timeout)' % port)
            except ConnectionRefusedError:
                self._fail('Connection refused to %s:%s (nothing listening on port)' % (host, port))
                issues.append('Connection refused - start Django on server: python manage.py runserver 0.0.0.0:%s' % port)
            except Exception as e:
                self._fail('TCP connect failed: %s' % e)
                issues.append('Network connect failed')
        else:
            self._section('NETWORK', '[NET]')
            self._info('Skipped (--skip-network)')

        # --- SUMMARY ---
        self._section('SUMMARY', '')
        if issues:
            self._warn('Issues found: %s' % len(issues))
            for i in issues:
                self.stdout.write(self.style.ERROR('  - %s' % i))
            self.stdout.write('')
            self._info('Next steps:')
            if 'Database connection failed' in issues:
                self._info('  - Check DATABASE_URL / .env and that PostgreSQL is running')
            if 'Pending migrations' in issues or 'Screening migration not applied' in issues:
                self._info('  - Run: python manage.py migrate hospital')
            if 'Connection refused' in str(issues):
                self._info('  - On server: python manage.py runserver 0.0.0.0:%s' % port)
                self._info('  - Or: gunicorn --bind 0.0.0.0:%s hms.wsgi:application' % port)
            if 'Host not in ALLOWED_HOSTS' in str(issues):
                self._info('  - Add server IP to ALLOWED_HOSTS or set DEBUG=True for private IPs')
            sys.exit(1)
        else:
            self._ok('All checks passed.')
            self.stdout.write('')
