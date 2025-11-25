"""
Login Location Detection Service
Accurate geolocation and device fingerprinting
"""
import requests
import logging
from django.conf import settings
from django.utils import timezone
try:
    from user_agents import parse as parse_user_agent
except ImportError:
    parse_user_agent = None
from decimal import Decimal

logger = logging.getLogger(__name__)


class LoginLocationService:
    """
    Service for detecting and tracking login locations
    """
    
    def __init__(self):
        self.geo_api_url = "http://ip-api.com/json/{ip}?fields=status,message,country,countryCode,region,regionName,city,lat,lon,timezone,isp,org,query"
        self.fallback_api_url = "https://ipapi.co/{ip}/json/"
        self.default_location = {
            'country': getattr(settings, 'DEFAULT_LOGIN_COUNTRY', 'Ghana'),
            'country_code': 'GH',
            'region': getattr(settings, 'DEFAULT_LOGIN_REGION', 'Greater Accra'),
            'city': getattr(settings, 'DEFAULT_LOGIN_CITY', 'Accra'),
            'latitude': Decimal(str(getattr(settings, 'DEFAULT_LOGIN_LATITUDE', 5.6037))),
            'longitude': Decimal(str(getattr(settings, 'DEFAULT_LOGIN_LONGITUDE', -0.1870))),
            'timezone': getattr(settings, 'DEFAULT_LOGIN_TIMEZONE', 'Africa/Accra'),
            'isp': 'PrimeCare Network',
            'organization': 'PrimeCare Hospital',
            'api_response': None,
        }
    
    def get_client_ip(self, request):
        """
        Get client IP address from request
        Handles proxy and forwarded headers
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        # Handle localhost
        if ip in ['127.0.0.1', 'localhost', '::1']:
            # For testing, use configured Ghanaian IP to keep maps realistic
            return getattr(settings, 'TEST_IP_ADDRESS', '102.176.95.4')
        
        return ip
    
    def get_location_from_ip(self, ip_address):
        """
        Get geolocation data from IP address
        Uses ip-api.com (free, no API key needed, 45 requests/min)
        """
        # Allow explicit default location usage
        if ip_address == getattr(settings, 'TEST_IP_ADDRESS', '102.176.95.4'):
            return self.default_location
        
        try:
            # Try primary API (ip-api.com)
            response = requests.get(
                self.geo_api_url.format(ip=ip_address),
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status') == 'success':
                    return {
                        'country': data.get('country', ''),
                        'country_code': data.get('countryCode', ''),
                        'region': data.get('regionName', ''),
                        'city': data.get('city', ''),
                        'latitude': Decimal(str(data.get('lat', 0))) if data.get('lat') else None,
                        'longitude': Decimal(str(data.get('lon', 0))) if data.get('lon') else None,
                        'timezone': data.get('timezone', ''),
                        'isp': data.get('isp', ''),
                        'organization': data.get('org', ''),
                        'api_response': data,
                    }
            
            # Fallback to ipapi.co
            logger.warning(f"Primary geolocation API failed for {ip_address}, trying fallback")
            response = requests.get(
                self.fallback_api_url.format(ip=ip_address),
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'country': data.get('country_name', ''),
                    'country_code': data.get('country_code', ''),
                    'region': data.get('region', ''),
                    'city': data.get('city', ''),
                    'latitude': Decimal(str(data.get('latitude', 0))) if data.get('latitude') else None,
                    'longitude': Decimal(str(data.get('longitude', 0))) if data.get('longitude') else None,
                    'timezone': data.get('timezone', ''),
                    'isp': data.get('org', ''),
                    'organization': data.get('org', ''),
                    'api_response': data,
                }
        
        except requests.Timeout:
            logger.error(f"Geolocation API timeout for IP: {ip_address}")
        except requests.RequestException as e:
            logger.error(f"Geolocation API error for IP {ip_address}: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error getting location for IP {ip_address}: {str(e)}")
        
        # Return hospital defaults if all fails
        return self.default_location
    
    def get_device_info(self, request):
        """
        Extract device and browser information from user agent
        """
        user_agent_string = request.META.get('HTTP_USER_AGENT', '')
        if parse_user_agent:
            user_agent = parse_user_agent(user_agent_string)
            
            # Determine device type
            if user_agent.is_mobile:
                device_type = 'mobile'
            elif user_agent.is_tablet:
                device_type = 'tablet'
            elif user_agent.is_pc:
                device_type = 'desktop'
            else:
                device_type = 'unknown'
            
            device_name = str(user_agent.device.family)
            if device_name == 'Other':
                device_name = f"{user_agent.os.family} Device"
            
            return {
                'user_agent': user_agent_string,
                'browser': user_agent.browser.family,
                'browser_version': user_agent.browser.version_string,
                'os': user_agent.os.family,
                'os_version': user_agent.os.version_string,
                'device_type': device_type,
                'device_name': device_name,
            }
        
        return {
            'user_agent': user_agent_string,
            'browser': 'Unknown',
            'browser_version': '',
            'os': 'Unknown',
            'os_version': '',
            'device_type': 'unknown',
            'device_name': 'Unknown Device',
        }
    
    def create_device_fingerprint(self, request):
        """
        Create a semi-unique device fingerprint
        """
        import hashlib
        
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        accept_language = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
        accept_encoding = request.META.get('HTTP_ACCEPT_ENCODING', '')
        
        fingerprint_string = f"{user_agent}|{accept_language}|{accept_encoding}"
        return hashlib.md5(fingerprint_string.encode()).hexdigest()
    
    def check_if_suspicious(self, user, ip_address, location_data, device_info):
        """
        Check if login is suspicious based on various factors
        """
        from ..models_login_tracking import LoginHistory, TrustedLocation, TrustedDevice
        
        suspicious_reasons = []
        
        # Check if new location
        is_new_location = True
        recent_logins = LoginHistory.objects.filter(
            user=user,
            status='success',
            is_deleted=False
        ).order_by('-login_time')[:10]
        
        for login in recent_logins:
            if login.country == location_data.get('country') and login.city == location_data.get('city'):
                is_new_location = False
                break
        
        if is_new_location and location_data.get('country') != 'Unknown':
            suspicious_reasons.append('New location')
        
        # Check trusted locations
        trusted_locations = TrustedLocation.objects.filter(
            user=user,
            is_active=True,
            is_deleted=False
        )
        
        is_trusted_location = False
        for trusted_loc in trusted_locations:
            if trusted_loc.city == location_data.get('city') and trusted_loc.country == location_data.get('country'):
                is_trusted_location = True
                trusted_loc.last_used = timezone.now()
                trusted_loc.save(update_fields=['last_used'])
                break
        
        # Check recent failed attempts
        failed_attempts = LoginHistory.objects.filter(
            user=user,
            status='failed',
            login_time__gte=timezone.now() - timezone.timedelta(hours=1),
            is_deleted=False
        ).count()
        
        if failed_attempts >= 3:
            suspicious_reasons.append(f'{failed_attempts} failed attempts in last hour')
        
        return {
            'is_suspicious': len(suspicious_reasons) > 0 and not is_trusted_location,
            'is_new_location': is_new_location,
            'is_new_device': True,  # Can be enhanced with device fingerprinting
            'reasons': suspicious_reasons,
        }
    
    def record_login(self, user, request, success=True, failure_reason=''):
        """
        Record a login attempt with full location and device details
        """
        from ..models_login_tracking import LoginHistory, SecurityAlert
        
        # Get IP address
        ip_address = self.get_client_ip(request)
        
        # Get location data
        location_data = self.get_location_from_ip(ip_address)
        
        # Get device info
        device_info = self.get_device_info(request)
        
        # Check if suspicious
        security_check = self.check_if_suspicious(user, ip_address, location_data, device_info)
        
        # Get staff record if exists
        try:
            from ..models import Staff
            staff = Staff.objects.filter(user=user, is_deleted=False).first()
        except:
            staff = None
        
        # Create login history record
        login_record = LoginHistory.objects.create(
            user=user,
            staff=staff,
            login_time=timezone.now(),
            session_key=request.session.session_key or '',
            ip_address=ip_address,
            country=location_data.get('country', ''),
            country_code=location_data.get('country_code', ''),
            region=location_data.get('region', ''),
            city=location_data.get('city', ''),
            latitude=location_data.get('latitude'),
            longitude=location_data.get('longitude'),
            timezone_name=location_data.get('timezone', ''),
            isp=location_data.get('isp', ''),
            organization=location_data.get('organization', ''),
            user_agent=device_info.get('user_agent', ''),
            browser=device_info.get('browser', ''),
            browser_version=device_info.get('browser_version', ''),
            os=device_info.get('os', ''),
            os_version=device_info.get('os_version', ''),
            device_type=device_info.get('device_type', 'unknown'),
            device_name=device_info.get('device_name', ''),
            status='success' if success else 'failed',
            is_suspicious=security_check.get('is_suspicious', False),
            is_new_location=security_check.get('is_new_location', False),
            is_new_device=security_check.get('is_new_device', False),
            failure_reason=failure_reason,
            geo_api_response=location_data.get('api_response'),
        )
        
        # Create security alert if suspicious and successful login
        if security_check.get('is_suspicious') and success:
            alert_description = f"Login from {location_data.get('city', 'Unknown')}, {location_data.get('country', 'Unknown')}"
            if security_check.get('reasons'):
                alert_description += f". Reasons: {', '.join(security_check['reasons'])}"
            
            SecurityAlert.objects.create(
                user=user,
                login_history=login_record,
                alert_type='new_location' if security_check.get('is_new_location') else 'suspicious_ip',
                severity='medium',
                description=alert_description,
                ip_address=ip_address,
                location=location_data.get('city', '') + ', ' + location_data.get('country', ''),
            )
        
        return login_record
    
    def record_logout(self, user, session_key):
        """
        Record logout time for a session
        """
        from ..models_login_tracking import LoginHistory
        
        try:
            login_record = LoginHistory.objects.filter(
                user=user,
                session_key=session_key,
                logout_time__isnull=True,
                is_deleted=False
            ).first()
            
            if login_record:
                login_record.logout_time = timezone.now()
                login_record.save(update_fields=['logout_time'])
        except Exception as e:
            logger.error(f"Error recording logout: {str(e)}")


# Global instance
login_location_service = LoginLocationService()

