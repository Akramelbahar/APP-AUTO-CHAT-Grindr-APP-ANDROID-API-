accountMinutes = 5
import re
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Tuple, Optional
import traceback
from dataclasses import dataclass
from typing import Optional, Dict, List
import os
import tls_client
import subprocess
from datetime import datetime, timedelta
import threading
import requests
import json
import random
import time
from utils import date_to_timestamp 
import random
import requests
import time
import time as t
from datetime import datetime
from openai import OpenAI
import multiprocessing
from multiprocessing import Lock
from PIL import Image
os.makedirs("messagesLogs", exist_ok=True)

try :
    open("received_messages.txt" ,"r").readlines()
except:
    open("received_messages.txt" ,"w").write("")
try :
    open("handle_1.txt" ,"r").readlines()
except:
    open("handle_1.txt" ,"w").write("")
try :
    open("handle_2.txt" ,"r").readlines()
except:
    open("handle_2.txt" ,"w").write("")

class ProxyManager:
    def __init__(self, proxy_file='proxies.json'):
        self.proxy_file = proxy_file
        self.ensure_proxy_file_exists()
    
    def ensure_proxy_file_exists(self):
        if not os.path.exists(self.proxy_file):
            self.save_proxies([])
    
    def is_valid_proxy_format(self, proxy: str) -> bool:
        """
        Validate proxy URL format.
        Example format: http://username:password@hostname:port/
        """
        try:
            pattern = r'^http://[^:]+:[^@]+@[^:]+:\d+/?$'
            return bool(re.match(pattern, proxy))
        except:
            return False

    def format_proxy(self, proxy: str) -> str:
        """Ensure proxy has consistent format."""
        proxy = proxy.strip()
        if not proxy.startswith('http://'):
            proxy = 'http://' + proxy
        if not proxy.endswith('/'):
            proxy += '/'
        return proxy

    def load_proxies(self) -> List[str]:
        """Load proxies from the JSON file."""
        try:
            with open(self.proxy_file, 'r') as file:
                data = json.load(file)
                return data.get('proxies', [])
        except Exception as e:
            print(f"Error loading proxies: {str(e)}")
            return []
    
    def save_proxies(self, proxies: List[str]) -> bool:
        """Save proxies to the JSON file."""
        try:
            valid_proxies = []
            for proxy in proxies:
                formatted_proxy = self.format_proxy(proxy)
                if self.is_valid_proxy_format(formatted_proxy):
                    valid_proxies.append(formatted_proxy)
                else:
                    print(f"Invalid proxy format, skipping: {proxy}")

            with open(self.proxy_file, 'w') as file:
                json.dump({'proxies': valid_proxies}, file, indent=4)
            return True
        except Exception as e:
            print(f"Error saving proxies: {str(e)}")
            return False

    def add_proxies(self, new_proxies: List[str]) -> Tuple[int, int]:
        """
        Add new proxies to the existing list, avoiding duplicates.
        Returns tuple of (added_count, invalid_count)
        """
        current_proxies = set(self.load_proxies())
        valid_count = 0
        invalid_count = 0
        
        for proxy in new_proxies:
            formatted_proxy = self.format_proxy(proxy)
            if self.is_valid_proxy_format(formatted_proxy):
                current_proxies.add(formatted_proxy)
                valid_count += 1
            else:
                invalid_count += 1
        
        self.save_proxies(list(current_proxies))
        return valid_count, invalid_count

    def test_proxy_connection(self, proxy: str) -> Tuple[str, bool]:
        """Test if a proxy is working using a simple HTTP request."""
        try:
            parsed = urlparse(proxy)
            proxy_dict = {
                'http': proxy,
                'https': proxy
            }
            
            response = requests.get(
                'http://example.com',
                proxies=proxy_dict,
                timeout=5,
                verify=False
            )
            return proxy, response.status_code == 200
        except Exception as e:
            print(f"Error testing proxy {proxy}: {str(e)}")
            return proxy, False

    def test_all_proxies(self, max_workers: int = 10) -> Dict[str, List[str]]:
        """Test all proxies concurrently and return working/failed lists."""
        proxies = self.load_proxies()
        working = []
        failed = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(self.test_proxy_connection, proxies))
            
            for proxy, is_working in results:
                if is_working:
                    working.append(proxy)
                else:
                    failed.append(proxy)
        
        return {'working': working, 'failed': failed}

    def remove_failed_proxies(self) -> Tuple[int, int]:
        """Test all proxies and remove the failed ones."""
        results = self.test_all_proxies()
        self.save_proxies(results['working'])
        return len(results['working']), len(results['failed'])
proxy_manager = ProxyManager()

@dataclass
class GPTSettings:
    primaryApiKey: str
    secondaryApiKey: Optional[str]
    framework: str
    handles: Dict[str, List[str]]

@dataclass
class APISettings:
    accessToken: str
    version: str
    manifestVersion: str
    creator_id: str
    preset_id: str
    name: str
    age: str
    userInfo: str
    chatStyle: str
    settingDayInfo: str
    settingNightInfo: str
    ctaInfo: str
    spintax: str
    followUpSpintax: str
    followUpAfterCTA: str
    ctaScript: str
    objectionHandling: str
    enableSequence: bool
    responseLanguage: str
    responseLanguageCode: str

try:
    open("accountsWithoutCities.txt", "r").read()
except:
    open("accountsWithoutCities.txt", "w").write("")

def replace_placeholders(text, city=None, name=None , handle1=None , handle2=None):
    try :
        handle1 = random.choice(open("handle_1.txt" ,"r").readlines())
    except:
        handle1 = ''
    try:
        handle2 = random.choice(open("handle_2.txt" ,"r").readlines())
    except :
        handle2 = ""

    if not text:
        return text
    if("|" in text):
        text = random.choice(text.split("|"))
        
    replacements = {
        "{City}": city or "",
        "{name}": name or "",
        "{Handle_1}": handle1 or "",
        "{Handle_2}": handle2 or ""
    }
    
    for placeholder, value in replacements.items():
        if value:
            text = text.replace(placeholder, value)
    return text
def calculate_thumb_coords(image_path):
    image = Image.open(image_path)
    image_width, image_height = image.size
    
    shortest_side = min(image_width, image_height)    
    return f"{shortest_side},{0},{shortest_side},{0}"

file_lock = Lock()
client = OpenAI(
api_key="sk-",
)

class ChatManager:
    def __init__(self):
        self.accepted_chats = set() 
        self.last_new_chat_check = time.time()
        self.new_chat_interval = random.uniform(180, 900) 
        self.max_new_chats = random.randint(2, 8)  
        self.new_chats_processed = 0

    def should_process_new_chats(self):
        current_time = time.time()
        if current_time - self.last_new_chat_check >= self.new_chat_interval:
            self.last_new_chat_check = current_time
            self.new_chat_interval = random.uniform(180, 900)  
            self.max_new_chats = random.randint(2, 8)  
            self.new_chats_processed = 0
            return True
        return False
class ChatSettingsManager:
    def __init__(self):
        self.profile_manager = ProfileDataManager()

    def get_chat_settings(self, profile_id: str) -> dict:
        
        try:
            profile = self.profile_manager.get_profile_by_id(profile_id)
            if not profile:
                return {
                    'chatMode': 'bot',
                    'gptSettings': {},
                    'apiSettings': {}
                }
            
            return {
                'chatMode': profile.get('chatMode', 'bot'),
                'gptSettings': profile.get('gptSettings', {}),
                'apiSettings': profile.get('apiSettings', {})
            }
        except Exception as e:
            print(f"Error in get_chat_settings: {str(e)}")
            return {
                'chatMode': 'bot',
                'gptSettings': {},
                'apiSettings': {}
            }

    def update_chat_settings(self, profile_id: str, form_data: dict) -> bool:
        
        try:
            chat_mode = form_data.get('chatMode', 'bot')
            
            settings_update = {
                'chatMode': chat_mode,
                'apiSettings': {
                    'accessToken': form_data.get('accessToken'),
                    'version': form_data.get('version'),
                    'manifestVersion': form_data.get('manifestVersion'),
                    'isAPI': True,
                    'app': 'grindr',
                    'isOF': True,
                    'brand': 'cupidbotofm',
                    'product': 'ofm-grindr',
                    'isFemale': True,
                    'platformSource': 'grindr',
                    'creator_id': form_data.get('creator_id'),
                    'preset_id': form_data.get('preset_id'),
                    'name': form_data.get('name'),
                    'age': form_data.get('age'),
                    'userInfo': form_data.get('userInfo'),
                    'chatStyle': form_data.get('chatStyle', 'youth'),
                    'settingDayInfo': form_data.get('settingDayInfo'),
                    'settingNightInfo': form_data.get('settingNightInfo'),
                    'ctaInfo': form_data.get('ctaInfo'),
                    'spintax': form_data.get('spintax'),
                    'followUpSpintax': form_data.get('followUpSpintax'),
                    'followUpAfterCTA': form_data.get('followUpAfterCTA'),
                    'ctaScript': form_data.get('ctaScript'),
                    'objectionHandling': form_data.get('objectionHandling'),
                    'enableSequence': form_data.get('enableSequence') == 'on',
                    'responseLanguage': form_data.get('responseLanguage', 'English'),
                    'responseLanguageCode': self._get_language_code(form_data.get('responseLanguage', 'en'))
                }
            }

            if chat_mode == 'gpt':
                settings_update['gptSettings'] = {
                    'primaryApiKey': form_data.get('openaiKey1'),
                    'secondaryApiKey': form_data.get('openaiKey2'),
                    'framework': form_data.get('gptFramework'),
                    'handles': {
                        'handle1': [h.strip() for h in form_data.get('handle1', '').split('\n') if h.strip()],
                        'handle2': [h.strip() for h in form_data.get('handle2', '').split('\n') if h.strip()]
                    }
                }
            else:
                settings_update['gptSettings'] = None

            return self.profile_manager.update_profile(profile_id, settings_update)
        except Exception as e:
            print(f"Error updating chat settings: {str(e)}")
            return False

    def _get_language_code(self, language: str) -> str:
        language_codes = {
            'English': 'en',
            'French': 'fr',
            'Spanish': 'es'
        }
        return language_codes.get(language, 'en')

class ProfileDataManager:
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:  
                    cls._instance = super(ProfileDataManager, cls).__new__(cls)
                    cls._instance._data = []
                    cls._instance._load_data()
        return cls._instance

    def _load_data(self):
        
        try:
            if os.path.exists('accounts.json'):
                with open('accounts.json', 'r') as file:
                    self._data = json.load(file)
            else:
                self._data = []
        except json.JSONDecodeError:
            print("Error loading accounts.json")
            self._data = []
        except Exception as e:
            print(f"Error in _load_data: {str(e)}")
            self._data = []

    def get_profiles(self):
        
        with self._lock:
            try:
                self._load_data()  
                return self._data
            except Exception as e:
                print(f"Error in get_profiles: {str(e)}")
                return []

    def save_data(self):
        
        with self._lock:
            try:
                with open('accounts.json', 'w') as file:
                    json.dump(self._data, file, indent=4)
                return True
            except Exception as e:
                print(f"Error saving data: {str(e)}")
                return False

    def get_profile_by_id(self, profile_id):
        
        with self._lock:
            try:
                self._load_data()  
                return next((p for p in self._data if str(p["profile"]["id"]) == str(profile_id)), None)
            except Exception as e:
                print(f"Error in get_profile_by_id: {str(e)}")
                return None

    def update_profile(self, profile_id, new_data):
        
        with self._lock:
            try:
                self._load_data()  
                for i, profile in enumerate(self._data):
                    if str(profile["profile"]["id"]) == str(profile_id):
                        
                        updated_profile = {
                            'profile': profile['profile'],
                            'Accounts': profile['Accounts'],
                            'proxies': proxy_manager.load_proxies(),
                            'cities': profile['cities'],
                            'enabled': profile.get('enabled', False),
                            'chatMode': new_data.get('chatMode', profile.get('chatMode', 'bot')),
                            'gptSettings': new_data.get('gptSettings', profile.get('gptSettings')),
                            'apiSettings': {
                                **profile.get('apiSettings', {}),
                                **new_data.get('apiSettings', {})
                            }
                        }
                        self._data[i] = updated_profile
                        return self.save_data()
                return False
            except Exception as e:
                print(f"Error in update_profile: {str(e)}")
                return False

    def get_accounts_for_profile(self, profile_id):
        
        profile = self.get_profile_by_id(profile_id)
        return profile.get("Accounts", []) if profile else []
    
    def update_account_city(profile, account):
        
        try:
            
            with open('accounts.json', 'r') as file:
                all_data = json.load(file)
                
            profile_id = profile.get("profile", {}).get("id")
            
            
            for p in all_data:
                if str(p.get("profile", {}).get("id")) == str(profile_id):
                    
                    used_cities = {
                        acc.get("city") for acc in p.get("Accounts", [])
                        if acc.get("city") and acc["userName"] != account["userName"]
                    }
                    
                    
                    available_cities = [
                        city for city in p.get("cities", [])
                        if city["city"] not in used_cities
                    ]
                    
                    
                    try:
                        with open("accountsWithoutCities.txt", "r") as f:
                            no_city_accounts = f.read().splitlines()
                    except FileNotFoundError:
                        open("accountsWithoutCities.txt", "w").write("")
                        no_city_accounts = []

                    if account.get("userName") in no_city_accounts:
                        print(f"Account {account['userName']} is marked as having no city")
                        return False
                    
                    
                    if not available_cities:
                        if account["userName"] not in no_city_accounts:
                            with open("accountsWithoutCities.txt", "a") as f:
                                f.write(f"{account['userName']}\n")
                        print(f"No available cities for account {account['userName']}")
                        return False
                    
                    
                    city = available_cities[0]
                    
                    
                    account["city"] = city["city"]
                    account["lat"] = city["lat"]
                    account["long"] = city["long"]
                    
                    
                    for i, acc in enumerate(p["Accounts"]):
                        if acc["userName"] == account["userName"]:
                            p["Accounts"][i] = account
                            break
                    
                    
                    with open('accounts.json', 'w') as f:
                        json.dump(all_data, f, indent=4)
                        f.flush()
                        
                    print(f"Successfully assigned city {city['city']} to account {account['userName']}")
                    
                    
                    if account["userName"] in no_city_accounts:
                        removeAccountFromUnusedQueue(account["userName"])
                    
                    return True
                    
            print(f"Profile {profile_id} not found")
            return False
            
        except Exception as e:
            print(f"Error updating account city: {str(e)}")
            traceback.print_exc()
            return False

    def removeAccountFromUnusedQueue(username):
        
        try:
            with open("accountsWithoutCities.txt", "r") as f:
                accounts = f.readlines()
            
            with open("accountsWithoutCities.txt", "w") as f:
                for account in accounts:
                    if account.strip() != username:
                        f.write(account)
            
            print(f"Removed {username} from unused queue")
        except Exception as e:
            print(f"Error removing from unused queue: {str(e)}")

    def validate_city_assignments(profile):
        
        try:
            city_assignments = {}
            accounts_to_reset = []
            
            
            for account in profile.get("Accounts", []):
                city = account.get("city")
                if city:
                    if city in city_assignments:
                        
                        accounts_to_reset.append(account)
                    else:
                        city_assignments[city] = account["userName"]
            
            
            if accounts_to_reset:
                print(f"Found {len(accounts_to_reset)} accounts with duplicate cities")
                for account in accounts_to_reset:
                    account["city"] = None
                    account["lat"] = None
                    account["long"] = None
                    print(f"Reset city assignment for account {account['userName']}")
                
                return True
                
            return False
            
        except Exception as e:
            print(f"Error validating city assignments: {str(e)}")
            return False


def getAccounts():
    try:
        manager = ProfileDataManager()
        profiles = manager.get_profiles()
        if not profiles:
            print("No profiles found, returning empty list")
            return []
        return profiles
    except Exception as e:
        print(f"Error in getAccounts: {str(e)}")
        return []




BITS = [16, 8, 4, 2, 1]
BASE32 = '0123456789bcdefghjkmnpqrstuvwxyz'

def encode_geohash(latitude, longitude, precision=12):
    lat_range = [-90.0, 90.0]
    lon_range = [-180.0, 180.0]
    
    geohash = []
    bit = 0
    ch = 0
    even = True

    while len(geohash) < precision:
        if even:
            mid = (lon_range[0] + lon_range[1]) / 2
            if longitude > mid:
                ch |= BITS[bit]
                lon_range[0] = mid
            else:
                lon_range[1] = mid
        else:
            mid = (lat_range[0] + lat_range[1]) / 2
            if latitude > mid:
                ch |= BITS[bit]
                lat_range[0] = mid
            else:
                lat_range[1] = mid

        even = not even

        if bit < 4:
            bit += 1
        else:
            geohash.append(BASE32[ch])
            bit = 0
            ch = 0

    return ''.join(geohash)

def smsGetBalance():
    return requests.get('https://daisysms.com/stubs/handler_api.php?api_key='+daiseyKey+'&action=getBalance').text
def rentNumber():
    response = requests.get('https://daisysms.com/stubs/handler_api.php?api_key='+daiseyKey+'&action=getNumber&service=yw')
    return {'phone' :response.text.split(':')[-1] , 
            'id':response.text.split(':')[1]}
def getOtp(id):
    response = requests.get('https://daisysms.com/stubs/handler_api.php?api_key='+daiseyKey+'&action=getStatus&id='+id)
    if ('STATUS_WAIT_CODE' in response.text) :
        print('Otp Not Satisfied yet retrying after 3s .....')
        time.sleep(3)
        return getOtp(id)
    if('STATUS_OK' in response.text) :
        return response.text.split(':')[-1]     
session = tls_client.Session(
    client_identifier='okhttp4_android_13',
    ja3_string="771,4865-4866-4867-49195-49196-52393-49199-49200-52392-49171-49172-156-157-47-53,0-23-65281-10-11-35-16-5-13-51-45-43-21-41,29-23-24,0",
    supported_versions=["1.3", "1.2"],  
    key_share_curves=["x25519", "secp256r1"], 
    cert_compression_algo=["brotli", "zlib"], 
            connection_flow=6291456,  
    pseudo_header_order=[":method", ":authority", ":scheme", ":path", "user-agent"],
    header_order=[
        'requirerealdeviceinfo', 'l-time-zone', 'l-device-info', 'accept', 
        'user-agent', 'l-locale', 'accept-language', 
        'content-type', 'content-length', 'accept-encoding'
    ],
    supported_signature_algorithms=[
        "ecdsa_secp256r1_sha256", "rsa_pss_rsae_sha256", "rsa_pkcs1_sha256",
        "ecdsa_secp384r1_sha384", "rsa_pss_rsae_sha384", "rsa_pkcs1_sha384", 
        "rsa_pss_rsae_sha512", "rsa_pkcs1_sha512", "ecdsa_secp521r1_sha512" 
    ],
    
    force_http1=False 
)
def get_last_message(data):
    messages = data.get('messages', [])
    if not messages:
        return None  
    last_message = max(messages, key=lambda msg: msg['timestamp'])

    return last_message



def validate(response):
    if('Cloudflare' in response):
        mobile_identifiers = [
    "zalando_android_mobile",
    "zalando_ios_mobile",
    "nike_ios_mobile",
    "nike_android_mobile",
    "mms_ios",
    "mms_ios_1",
    "mms_ios_2",
    "mms_ios_3",
    "mesh_ios",
    "mesh_ios_1",
    "mesh_ios_2",
    "mesh_android",
    "mesh_android_1",
    "mesh_android_2",
    "confirmed_ios",
    "confirmed_android",
    "okhttp4_android_7",
    "okhttp4_android_8",
    "okhttp4_android_9",
    "okhttp4_android_10",
    "okhttp4_android_11",
    "okhttp4_android_12",
    "okhttp4_android_13"
    ]
        session.client_identifier = random.choice(mobile_identifiers)
        retry = 0
        while(retry !=-1 and retry<=3):
                        try:
                            session.proxies.update(random.choice({"http":proxy_manager.load_proxies()}))
                            retry = -1
                        except:
                            retry = retry +1
            
        
        return False
    else: 
        return True
    

#POINTI
def editProfile(auth,deviceInfo, userAgent , displayName , aboutMe , age , heightFrom  ,  heightTo , lookingFor , meetAt , acceptNSFWPics, acc):
        print(f"Account started to change :{auth} ")
        oldProfile = getProfile(auth,deviceInfo, userAgent )["profiles"][0]
        print(oldProfile)
        new= replace_placeholders( aboutMe, acc.get("city") )
        oldProfile["aboutMe"] = new
        oldProfile["age"] = age
        oldProfile["displayName"] = displayName
        oldProfile["height"] = random.randint(heightFrom , heightTo)
        oldProfile["lookingFor"] = lookingFor
        oldProfile["meetAt"] = meetAt
        oldProfile["acceptNSFWPics"] = acceptNSFWPics 
        r = session.put('https://grindr.mobi/v3.1/me/profile' , headers={
                                    'Host': 'grindr.mobi',
                                    'Authorization': str(auth),
                                    'L-Time-Zone': 'Unknown',
                                    'L-Grindr-Roles': '[]',
                                    'L-Device-Info': deviceInfo,
                                    'Accept': 'application/json',
                                    'User-Agent': userAgent,
                                    'L-Locale': 'en_US',
                                    'Accept-Language': 'en-US',
                                    'Content-Type': 'application/json; charset=UTF-8',
                                    'Accept-Encoding': 'gzip, deflate, br'
                                    } , json=oldProfile) 
        print(f'ProfileEditedStatusCode = {r.status_code} acc name = {acc.get("userName")}' )
           
    
def check_proxy(proxy):
    
    try:
        
        proxy_dict = {
            "http": proxy,
            "https": proxy,
        }
        response = requests.get("http://www.google.com", proxies=proxy_dict, timeout=10)
        if response.status_code == 200:
            return response.text  
    except requests.RequestException as e:
        print(f"Request failed with exception: {e}")
        return None

def find_working_proxy(proxies):
    
    for proxy in proxies:
        print(f"Checking proxy: {proxy}")
        result = check_proxy(proxy)
        if result:
            print(f"Working proxy found: {proxy}")
            return proxy
        else:
            print(f"Proxy failed: {proxy}")

    print("No working proxy found.")
    return None

def generate_random_ipv6():
    return "fe80::" + ":".join(f"{random.randint(0, 65535):x}" for _ in range(4))
def generate_random_ipv4():
    return ".".join(str(random.randint(1, 254)) for _ in range(4))
def get_public_ip():
    try:
        response = session.get('https://api.ipify.org?format=json')
        return response.json()['ip']
    except requests.RequestException as e:
        print("Error getting public IP:", e)
        return None
def get_current_timestamp():
    return int(time.time() * 1000)
def createAccount(email,password,bYear,bMonth,bDay):
    birthday = date_to_timestamp(bYear,bMonth,bDay)
    headers ={
    'requirerealdeviceinfo': 'false',
    'l-time-zone': 'Unknown',
    'accept': 'application/json',
    'user-agent': 'grindr3/24.13.0.127926;127926;Free;Android 13;SM-N935F;samsung',
    'l-locale': 'en_US',
    'accept-language': 'en-US',
    'content-type': 'application/json; charset=UTF-8',
    'accept-encoding': 'gzip',
    }
    captcha = 'captchaSolve()'
    data = {
    "birthday": 944956800000,
    "captchaToken": captcha,
    "email": email,
    "optIn": False,
    "password": password,
    "token": "c13q4hvWRSWHzBVDzB_Ajs:APA91bFP7l7cvbfrvbkP4M9yPVHqEHaNcT3Oc1jpbqWv1sU6FwABHP05LmQvmox070NGq2C6Fh7qC20hEwt8U-1TxHIylkdO1RuLOjBIwwgz83DBaGbKg6eId9AsyUA3JJqHs5_Yu6wm"
}
    while True :
        response = session.post("https://grindr.mobi/v7/users", headers=headers, json=data)
        if(validate(response.text)):
            break


    profileId = response.json()
    return response.json() 
def activateAccount(id,device_info):
    headers ={
    'host': 'grindr.mobi',
    'requirerealdeviceinfo': 'false',
    'l-time-zone': 'Unknown',
    'l-grindr-roles': '[]',
    'l-device-info': device_info,
    'accept': 'application/json',
    'user-agent': 'grindr3/24.12.0.127593;127593;Free;Android 13;SM-N935F;samsung',
    'l-locale': 'en_US',
    'accept-language': 'en-US',
    'content-type': 'application/json; charset=UTF-8',
    'accept-encoding': 'gzip',
    }
    phone = rentNumber()
    data = {"country_code":"1","phone_number":phone['phone'][1:]}
    while True :
        response = session.post("https://grindr.mobi/v4/sms/verification/"+str(id)+"/sendcode", headers=headers, json=data)
        if(validate(response.text)):
            break
    
    print('Sending Otp ...')
    print(response.status_code)
    print(response.text)
    print(response.cookies)
    print(response.headers)
    otp = getOtp(phone["id"])
    data = {"country_code":"1","phone_number":phone['phone'][1:], "code":otp} 
    while True :
        response = session.post("https://grindr.mobi/v4/sms/verification/"+str(id)+"/verifycode", headers=headers, json=data)
        if(validate(response.text)):
            break
    print('OTP satisfied :',otp)
    print(response.status_code)
    print(response.text)
    print(response.cookies)
    print(response.headers)
def Login(username,auth,token,deviceInfo,userAgent):
    headers ={
    'requirerealdeviceinfo': 'false',
    'l-time-zone': 'Unknown',
    'l-device-info': deviceInfo,
    'accept': 'application/json',
    'user-agent': userAgent,
    'l-locale': 'en_US',
    'accept-language': 'en-US',
    'content-type': 'application/json; charset=UTF-8',
    'accept-encoding': 'gzip',
    }
    data = {
    "authToken": auth,
    "email": username,
    "token": token
}
    print("Token Regenetated")
    
    while True :
        response = session.post('https://grindr.mobi/v4/sessions',headers=headers ,json=data)
        if(validate(response.text)):
            break
    print(response.text)
    if('ACCOUNT_BANNED' in response.text):
            data = getAccounts()
            for profile in data :
                for account in profile['Accounts']:
                    if(account['userName'] == username):
                        profile['Accounts'] = profile['Accounts'] - [account]
                        open('accounts.json' , 'w').write(json.dumps(data , indent=4))
                        return False
    return response.json()
def changeLocation(auth , deviceInfo ,userAgent, lat , long):
    response = session.put('https://grindr.mobi/v3/me/location',
                            headers={
                                'Host': 'grindr.mobi',
                                'Authorization': auth,
                                'L-Time-Zone': 'Unknown',
                                'L-Grindr-Roles': '[]',
                                'L-Device-Info': deviceInfo,
                                'Accept': 'application/json',
                                'User-Agent': userAgent,
                                'L-Locale': 'en_US',
                                'Accept-Language': 'en-US',
                                'Content-Type':' application/json; charset=UTF-8',
                                'Accept-Encoding':' gzip, deflate, br'},json={"geohash":encode_geohash(long,lat )})
    if(response.status_code == 200):
        print('Account Location Updated')
def getProfilesByLocation(auth , deviceInfo ,userAgent , lat , long):
    response = session.get('https://grindr.mobi/v1/cascade?nearbyGeoHash='+encode_geohash(long,lat )+'&onlineOnly=false&photoOnly=false&faceOnly=false&notRecentlyChatted=false&fresh=false&pageNumber=1&favorites=false',
                            headers={
                                'Host': 'grindr.mobi',
                                'Authorization': auth,
                                'L-Time-Zone': 'Unknown',
                                'L-Grindr-Roles': '[]',
                                'L-Device-Info': deviceInfo,
                                'Accept': 'application/json',
                                'User-Agent': userAgent,
                                'L-Locale': 'en_US',
                                'Accept-Language': 'en-US',
                                'Content-Type':' application/json; charset=UTF-8',
                                'Accept-Encoding':' gzip, deflate, br'})
    if response.status_code == 200 :
        print(response.json())
        return response.json()
def sendMessage(auth, deviceInfo, userAgent, recipientProfileId, body,proxies):
        proxies = proxy_manager.load_proxies()
        env = os.environ.copy()
        env['HTTP_PROXY'] = find_working_proxy(proxies)
        if(not env['HTTP_PROXY']):
            env['HTTP_PROXY'] = proxies[0]
        subprocess.Popen(['main.exe', auth, deviceInfo, userAgent, recipientProfileId, body] , env=env)
        print(open('received_messages.txt','r').readlines())
def openSocket(auth, deviceInfo, userAgent,proxies):
    try :
        proxies = proxy_manager.load_proxies()
        env = os.environ.copy()
        env['HTTP_PROXY'] = find_working_proxy(proxies)
        subprocess.run(['socket.exe', auth, deviceInfo, userAgent], timeout=accountMinutes*60)
        print(open('received_messages.txt','r').readlines())
    except:
        pass
def viewProfile(auth , deviceInfo , userAgent , profileId):
    time.sleep(2)
    profileId = str(profileId)
    response = session.post(
    'https://grindr.mobi/v4/views',
    headers={
        'Host': 'grindr.mobi',
        'Authorization': str(auth),
        'L-Time-Zone': 'Unknown',
        'L-Grindr-Roles': '[]',
        'L-Device-Info': deviceInfo,
        'Accept': 'application/json',
        'User-Agent': userAgent,
        'L-Locale': 'en_US',
        'Accept-Language': 'en-US',
        'Content-Type': 'application/json; charset=UTF-8',
        'Accept-Encoding': 'gzip, deflate, br'
    },
    json={
        "viewedProfileIds": [
            profileId
        ]
    }
)

    if(response.status_code == 200):
        print(profileId +' view was performed successfully. ')
        return 0 
    print('error occured during performing a view to :' + profileId)   
def inbox(auth , deviceInfo , userAgent , page):
    headers={
        'Host': 'grindr.mobi',
        'Authorization': str(auth),
        'L-Time-Zone': 'Unknown',
        'L-Grindr-Roles': '[]',
        'L-Device-Info': deviceInfo,
        'Accept': 'application/json',
        'User-Agent': userAgent,
        'L-Locale': 'en_US',
        'Accept-Language': 'en-US',
        'Content-Type': 'application/json; charset=UTF-8',
        'Accept-Encoding': 'gzip, deflate, br'
    }
    response = session.post('https://grindr.mobi/v1/inbox?page='+str(page), 
    headers=headers , json={
    "unreadOnly": False})
    if(response.status_code == 200):
        return response.json()
    print('error during receiving conversations :', response.text)
    return response.status_code
def get_random_msg(data):
    options = data.get('options', [])
    
    flattened_options = [item for sublist in options for item in sublist]
    
    if not flattened_options:
        return None  
    random_msg = random.choice(flattened_options).get('msg', None)
    
    return random_msg
class PlaceholderManager:
    
    def __init__(self):
        self.handle_1_list = self._load_handles("handle_1.txt")
        self.handle_2_list = self._load_handles("handle_2.txt")

    def _load_handles(self, filename):
        
        try:
            with open(filename, 'r') as f:
                return [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"Creating new handles file: {filename}")
            with open(filename, 'w') as f:
                f.write("")
            return []

    def replace_placeholders(self, text, profile_name=None, city=None):
        
        if not text:
            return text

        replacements = {
            "{Handle_1}": random.choice(self.handle_1_list) if self.handle_1_list else "",
            "{Handle_2}": random.choice(self.handle_2_list) if self.handle_2_list else "",
            "{City}": city or "city",
            "{name}": profile_name or "name",
        }

        
        for placeholder, value in replacements.items():
            if value:  
                text = text.replace(placeholder, value)
            
        return text
def generateMessage(profile, senderId, recipientID, city, messageId, timestamp, receipantName, messageBody, isIncoming, sequenceEnabled):
    
    try:
        settings = profile.get("apiSettings", {})
        placeholder_manager = PlaceholderManager()
        profile_name = receipantName
        
        
        processed_message = placeholder_manager.replace_placeholders(
            messageBody,
            profile_name=profile_name,
            city=city
        )
        
        
        processed_userInfo = placeholder_manager.replace_placeholders(
            settings.get("userInfo", ""),
            profile_name=profile_name,
            city=city
        )
        
        
        processed_dayInfo = placeholder_manager.replace_placeholders(
            settings.get("settingDayInfo", ""),
            profile_name=profile_name,
            city=city
        )
        
        processed_nightInfo = placeholder_manager.replace_placeholders(
            settings.get("settingNightInfo", ""),
            profile_name=profile_name,
            city=city
        )
        
        processed_ctaInfo = placeholder_manager.replace_placeholders(
            settings.get("ctaInfo", ""),
            profile_name=profile_name,
            city=city
        )
        
        timestamp_in_seconds = int(timestamp / 1000) if timestamp > 1000000000000 else int(timestamp)
        payload = {
            "accessToken": settings.get("accessToken"),
            "version": settings.get("version"),
            "manifestVersion": settings.get("manifestVersion"),
            
            "isAPI": True,
            "app": "grindr",
            "isOF": True,
            "brand": "cupidbotofm",
            "product": "ofm-grindr",
            "isFemale": True,
            "platformSource": "grindr",
            
            "accountID": settings.get("AccountID" , 'AccountID'),
            "recipientID": str(recipientID),
            "creator_id": int(settings.get("creator_id", 0)),
            "preset_id": int(settings.get("preset_id", 0)),
            "name": placeholder_manager.replace_placeholders(
                    settings.get("name"),
                    profile_name=profile_name,
                    city=city
                ),
            "age": int(settings.get("age", 18)),
            
            "userInfo": settings.get("userInfo", "")[:200], 
            "chatStyle": settings.get("chatStyle", "youth"),
            "city": str(city),
            "settingDayInfo": settings.get("settingDayInfo", "")[:200],
            "settingNightInfo": settings.get("settingNightInfo", "")[:200],
            "ctaInfo": settings.get("ctaInfo", "")[:200],
            
            "responseLanguage": settings.get("responseLanguage", "English"),
            "responseLanguageCode": {
                "English": "en",
                "French": "fr",
                "Spanish": "es"
            }.get(settings.get("responseLanguage", "English"), "en"),
            
            
            "messages": [{
                "id": str(messageId),
                "timestamp": timestamp_in_seconds,
                "msg": messageBody if messageBody else "",
                "isIncoming": bool(isIncoming)
            }],
            
            "isFollowUp": True,
            "chooseRandomCTA": True,
            
            "openerData": {
                "defaultSettings": True,
                "spintax": settings.get("spintax", "")[:200],
                "aiAugmentation": True
            },
            
            "followUpData": {
                "defaultSettings": True,
                "spintax": settings.get("followUpSpintax", "")[:200],
                "aiAugmentation": True
            },
            
            "ctaPhase": {
                "defaultSettings": True,
                "operation": "minExchanges",
                "minExchanges": 30,
                "start": "00:00",
                "end": "23:59"
            },
            
            "ctaScript": {
                "defaultSettings": True,
                "followUpData": {
                    "defaultSettings": True,
                    "spintax": settings.get("followUpAfterCTA", "")[:200],
                    "aiAugmentation": True
                }
            },
            
            "objections": {
                "defaultSettings": True,
                "handling": {
                    "defaultSettings": True,
                    "spintax": settings.get("objectionHandling", "")[:200],
                    "mediaPools": ["sexy"],
                    "aiAugmentation": True
                }
            },
            
           
        }
        
        if settings.get("spintax"):
            payload["openerData"] = {
                "defaultSettings": True,
                "spintax": placeholder_manager.replace_placeholders(
                    settings.get("spintax", ""),
                    profile_name=profile_name,
                    city=city
                )[:200]
            }

        if settings.get("followUpSpintax"):
            payload["followUpData"] = {
                "defaultSettings": True,
                "spintax": placeholder_manager.replace_placeholders(
                    settings.get("followUpSpintax", ""),
                    profile_name=profile_name,
                    city=city
                )[:200],
              
            }

        if sequenceEnabled and settings.get("ctaScript"):
            payload["sequences"] = [[{
                "defaultSettings": True,
                "spintax": placeholder_manager.replace_placeholders(
                    settings.get("ctaScript", ""),
                    profile_name=profile_name,
                    city=city
                ),
                "aiAugmentation": True
            }]]
        print(f"PrivateBotPayload:{payload}")
        response = requests.post(
            "https://chat-dot-cupidbot-382905.uc.r.appspot.com/api/generateChatResponse",
            headers={
                'User-Agent': 'Apidog/1.0.0 (https://apidog.com)',
                'Content-Type': 'application/json'
            },
            json=payload,
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            if 'options' in data:
                flattened_options = [item for sublist in data['options'] for item in sublist]
                if flattened_options:
                    return random.choice(flattened_options).get('msg')
            return None
        else:
            print(f"API error: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        print(f"Error in generateMessage: {str(e)}")
        traceback.print_exc()
        return None

def receivedTaps(auth , deviceInfo , userAgent):
    headers={
        'Host': 'grindr.mobi',
        'Authorization': str(auth),
        'L-Time-Zone': 'Unknown',
        'L-Grindr-Roles': '[]',
        'L-Device-Info': deviceInfo,
        'Accept': 'application/json',
        'User-Agent': userAgent,
        'L-Locale': 'en_US',
        'Accept-Language': 'en-US',
        'Content-Type': 'application/json; charset=UTF-8',
        'Accept-Encoding': 'gzip, deflate, br'
    }
    response = session.get('https://grindr.mobi/v2/taps/received',headers=headers)
    if (response.status_code == 200):
        return response.json()
    print('error in receivedTaps :' + response.text)
    return response.status_code
def profileViewedBy(auth , deviceInfo , userAgent):
    headers={
        'Host': 'grindr.mobi',
        'Authorization': str(auth),
        'L-Time-Zone': 'Unknown',
        'L-Grindr-Roles': '[]',
        'L-Device-Info': deviceInfo,
        'Accept': 'application/json',
        'User-Agent': userAgent,
        'L-Locale': 'en_US',
        'Accept-Language': 'en-US',
        'Content-Type': 'application/json; charset=UTF-8',
        'Accept-Encoding': 'gzip, deflate, br'
    }
    response = session.get('https://grindr.mobi/v6/views/list',headers=headers)
    if (response.status_code == 200):
        return response.json()
    print('error in profileViewedBy :' + response.text)
    return response.status_code
def get_cloudflare_cookies(headers):
    http_uri = 'https://grindr.mobi/v4/me/profile'
    response = session.get(http_uri, headers=headers)
    if response.status_code == 200:
        return response.cookies.get_dict()
    else:
        raise Exception(f"Failed to bypass Cloudflare, status code: {response.status_code}")
def getProfile(auth , deviceInfo , userAgent):
    response = session.get('https://grindr.mobi/v4/me/profile', headers={
        'Host': 'grindr.mobi',
        'Authorization': str(auth),
        'L-Time-Zone': 'Unknown',
        'L-Grindr-Roles': '[]',
        'L-Device-Info': deviceInfo,
        'Accept': 'application/json',
        'User-Agent': userAgent,
        'L-Locale': 'en_US',
        'Accept-Language': 'en-US',
        'Content-Type': 'application/json; charset=UTF-8',
        'Accept-Encoding': 'gzip, deflate, br'
          })
    if response.status_code == 200 :
        return response.json()
    raise Exception(f"Failed to bypass in getProfile: {response.status_code}")


def save_message_logs(conversation_data, logs_dir="messagesLogs"):
    """
    Save message logs for a conversation to a file.
    
    Args:
        conversation_data (dict): A dictionary containing the conversation data.
        logs_dir (str): The directory to save the logs in (default is "messagesLogs").
    """
    try:
        os.makedirs(logs_dir, exist_ok=True)
        
        conversation_id = conversation_data["entries"][0]["conversationId"].replace(":", "_")
        
        file_path = os.path.join(logs_dir, f"{conversation_id}.txt")
        
        formatted_data = format_conversation(conversation_data)
        
        with open(file_path, "w") as f:
            f.write(formatted_data)
        
        print(f"Message logs saved to: {file_path}")
    except Exception as e:
        print(f"Error saving message logs: {str(e)}")

def format_conversation(conversation_data):

    lines = []
    for entry in conversation_data["entries"]:
        conversation_id = entry["conversationId"]
        last_activity_timestamp = entry["lastActivityTimestamp"]
        unread_count = entry["unreadCount"]
        last_message_preview = entry["preview"]["text"]
        
        timestamp = datetime.fromtimestamp(last_activity_timestamp / 1000).strftime("%Y-%m-%d %H:%M:%S")
        
        lines.append(f"Conversation with {entry['name']} ({conversation_id}):")
        lines.append(f"  - Last activity timestamp: {timestamp}")
        lines.append(f"  - Unread count: {unread_count}")
        lines.append(f"  - Last message preview: \"{last_message_preview}\"")
        lines.append("")
    
    return "\n".join(lines)

def last300chat(auth, device_info, user_agent):
    not_answered_chats = []
    page = 1
    max_pages = 5
    max_chats = 150
    eight_hours_ago = time.time() - (8 * 60 * 60)  

    while len(not_answered_chats) < max_chats and page <= max_pages:
        inbox_data = inbox(auth, device_info, user_agent, page)
        if not inbox_data or 'entries' not in inbox_data or not inbox_data['entries']:
            break
        try:
            file_path = os.path.join("messagesLogs", f"{inbox_data['entries'][0].get('conversationId').replace(':',"_")}.txt")
            
            save_message_logs((inbox_data))
        except Exception as e:
            print(e)
            pass
        for entry in inbox_data['entries']:
            try:
                conversation_id = entry.get('conversationId')
                recipient_name = entry.get('name')
                recipient_id = conversation_id.split(':')[0] if conversation_id else None
                last_message_from = entry.get('preview').get('senderId')
                last_message_timestamp = entry.get('lastActivityTimestamp', 0) / 1000  
            
                if str(last_message_from) == str(recipient_id) or last_message_timestamp < eight_hours_ago:
                    try:
                        not_answered_chats.append({
                            'recipient': recipient_id,
                            'conversationId': conversation_id,
                            "name": recipient_name
                        })
                    except:
                        pass
                if len(not_answered_chats) >= max_chats :
                    break
                page += 1
            except:
                pass
    print(len((not_answered_chats)))
    return reversed(not_answered_chats)
def getMyId(auth,deviceInfo,userAgent):
    response = session.get('https://grindr.mobi/v4/me/profile',headers={
                                'Host': 'grindr.mobi',
                                'Authorization': str(auth),
                                'L-Time-Zone': 'Unknown',
                                'L-Grindr-Roles': '[]',
                                'L-Device-Info': deviceInfo,
                                'Accept': 'application/json',
                                'User-Agent': userAgent,
                                'L-Locale': 'en_US',
                                'Accept-Language': 'en-US',
                                'Content-Type': 'application/json; charset=UTF-8',
                                'Accept-Encoding': 'gzip, deflate, br'
                                }

                           )
    if(response.status_code == 200):
        return response.json()['profiles'][0]["profileId"]
    return False
def editBio(auth,deviceInfo, userAgent , bio):
    try :
        oldProfile = getProfile(auth,deviceInfo, userAgent )
        oldProfile["profiles"][0]["aboutMe"] = bio
        oldProfile = oldProfile["profiles"][0]
        if session.put('https://grindr.mobi/v3.1/me/profile' , headers={
                                    'Host': 'grindr.mobi',
                                    'Authorization': str(auth),
                                    'L-Time-Zone': 'Unknown',
                                    'L-Grindr-Roles': '[]',
                                    'L-Device-Info': deviceInfo,
                                    'Accept': 'application/json',
                                    'User-Agent': userAgent,
                                    'L-Locale': 'en_US',
                                    'Accept-Language': 'en-US',
                                    'Content-Type': 'application/json; charset=UTF-8',
                                    'Accept-Encoding': 'gzip, deflate, br'
                                    } , json=oldProfile).status_code == 200 :
            print('Bio Changed successfully ')
        else :
            raise('error')
    except:
        editBio(auth,deviceInfo, userAgent , bio)
def extract_unused_cities(data):
    
    used_cities = set()

    for account in data.get("Accounts", []):
        if "city" in account:  
            used_cities.add(account["city"])

    unused_cities = []
    for city in data.get("cities", []):
        if city["city"] not in used_cities:
            unused_cities.append(city)

    return unused_cities

def updateProfileDisplayName(auth,deviceInfo, userAgent , newName):
        oldProfile = getProfile(auth,deviceInfo, userAgent )
        oldProfile["profiles"][0]["displayName"] = newName

        oldProfile = oldProfile["profiles"][0]
        if session.put('https://grindr.mobi/v3.1/me/profile' , headers={
                                    'Host': 'grindr.mobi',
                                    'Authorization': str(auth),
                                    'L-Time-Zone': 'Unknown',
                                    'L-Grindr-Roles': '[]',
                                    'L-Device-Info': deviceInfo,
                                    'Accept': 'application/json',
                                    'User-Agent': userAgent,
                                    'L-Locale': 'en_US',
                                    'Accept-Language': 'en-US',
                                    'Content-Type': 'application/json; charset=UTF-8',
                                    'Accept-Encoding': 'gzip, deflate, br'
                                    } , json=oldProfile).status_code == 200 :
            print('Name Changed successfully ')


def upload_image_with_tls(image_path, auth_token, device_info, user_agent , proxies):
    import urllib
    print("test")
    proxies = proxy_manager.load_proxies()
    url = "https://grindr.mobi/v3/me/profile/images?thumbCoords="+urllib.parse.quote(calculate_thumb_coords(image_path))

    headers = {
        "Authorization": auth_token,
        "l-time-zone": "Africa/Casablanca",
        "l-grindr-roles": "[]",
        "l-device-info": device_info,
        "Accept": "application/json",
        "User-Agent": user_agent,
        "l-locale": "en_US",
        "Accept-Language": "en-US",
        "Content-Type": "image/jpeg"
    }

    with open(image_path, 'rb') as img:
        img_data = img.read()
        
        session.proxies.update({"http":find_working_proxy(proxies) , "https":find_working_proxy(proxies)})
        response = session.post(url, headers=headers, data=img_data)

    if response.status_code == 200:
        print("Image uploaded successfully.")
        print(response.json())
        return response.json().get("hash")
    else:
        print(f"Failed to upload image: {response.status_code} - {response.text}")

def updateAccountPictures(images, auth_token, device_info, user_agent , proxies , i=0):
    print(f"Account Pictures Started to update for {auth_token}")
    if(i >5):
        return 
    print(f"Account Pictures Started to update for {auth_token}")
    proxies =proxy_manager.load_proxies()
    hashes = []
    print(f"images : {images}")
    for img in images :
        try :
            response = upload_image_with_tls(img, auth_token, device_info, user_agent , proxies)
            print(f"response : {response}")
            hashes.append(response)
        except:
            pass
        print(hashes)
    if(session.put("https://grindr.mobi/v3/me/profile/images" ,  headers = {
                'Host': 'grindr.mobi',
                'Authorization': str(auth_token),
                'L-Time-Zone': 'Unknown',
                'L-Grindr-Roles': '[]',
                'L-Device-Info': device_info,
                'Accept': 'application/json',
                'User-Agent': user_agent,
                'L-Locale': 'en_US',
                'Accept-Language': 'en-US',
                'Content-Type': 'application/json; charset=UTF-8',
                'Accept-Encoding': 'gzip, deflate, br'
            } , json={
                        "primaryImageHash": hashes[0],
                        "secondaryImageHashes": hashes
                    }
            ).status_code == 200):
        print(f"Pictures Updated for :{auth_token}")
        
    else:
        updateAccountPictures(images, auth_token, device_info, user_agent , proxies , i+1)
    
    

def update_account_city(profile, account):
    manager = ProfileDataManager()
    if not account.get("city"):
        unused_cities = extract_unused_cities(profile)
        
        try:
            with open("accountsWithoutCities.txt", "r") as f:
                notaccount = f.read()
        except FileNotFoundError:
            open("accountsWithoutCities.txt", "w").write("")
            notaccount = ""

        if not unused_cities and str(account.get("userName")) not in notaccount:
            with open("accountsWithoutCities.txt", "a") as f:
                f.write(f"{account.get('userName')}\n")
            print("Account added to 'accountsWithoutCities.txt' since no city was available.")
            return False
        
        if unused_cities:
            account["city"] = unused_cities[0]["city"]
            account["lat"] = unused_cities[0]["lat"]
            account["long"] = unused_cities[0]["long"]
            print(f"Assigned city: {account['city']}, lat: {account['lat']}, long: {account['long']}")

            profile_id = profile.get("profile", {}).get("id")
            if profile_id:
                profiles = manager.get_profiles()
                for i, pr in enumerate(profiles):
                    if str(pr.get("profile", {}).get("id")) == str(profile_id):
                        for j, acc in enumerate(pr["Accounts"]):
                            if acc["userName"] == account["userName"]:
                                manager.update_account(profile_id, j, account)
                                return True
            
            print("Error: Could not find profile or account to update")
            return False

def removeAccountFromUnusedQueue(username):
    
    with open("accountsWithoutCities.txt", "r") as f:
        accounts = f.readlines()
    with open("accountsWithoutCities.txt", "w") as f:
        for account in accounts:
            if account.strip() != username:
                f.write(account)
class GPTHandler:
    def __init__(self, primary_api_key, secondary_api_key=None, profile_name=None):
        self.primary_api_key = primary_api_key
        self.secondary_api_key = secondary_api_key
        self.profile_name = profile_name
        self.placeholder_manager = PlaceholderManager()
        self.current_client = None
        self._initialize_client()

    def _initialize_client(self):
        try:
            self.current_client = OpenAI(api_key=self.primary_api_key)
            print("Initialized primary GPT client")
        except Exception as e:
            print(f"Error initializing primary client: {str(e)}")
            if self.secondary_api_key:
                try:
                    self.current_client = OpenAI(api_key=self.secondary_api_key)
                    print("Initialized secondary GPT client")
                except Exception as e:
                    print(f"Error initializing secondary client: {str(e)}")
                    self.current_client = None

    def _make_gpt_request(self, messages, api_key):
        try:
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error with GPT request: {str(e)}")
            return None

    def generate_response(self, conversation_history, framework, city=None):
        
        if not self.current_client:
            print("No valid GPT client available")
            return None

        
        processed_framework = self.placeholder_manager.replace_placeholders(
            framework,
            
            profile_name=f"'{self.profile_name}'",
            city=f"'{city}'"
        )

        processed_messages = []
        for msg in conversation_history:
            processed_content = self.placeholder_manager.replace_placeholders(
                msg["content"],
                profile_name=self.profile_name,
                city=city
            )
            processed_messages.append({
                "role": msg["role"],
                "content": processed_content
            })
        processed_messages = [dict(t) for t in {frozenset(d.items()) for d in processed_messages}]
        messages = [
            {"role": "system", "content": processed_framework},
            *processed_messages
        ]
        print(messages)

        response = self._make_gpt_request(messages, self.primary_api_key)
        
        if response is None and self.secondary_api_key:
            print("Primary API key failed, trying secondary")
            response = self._make_gpt_request(messages, self.secondary_api_key)
        
        if response:
            if "~" in response:
                return [msg.strip() for msg in response.split("~") if msg.strip()]
            return [response]
            
        print("Failed to generate GPT response with both API keys")
        return None
def get_last_message(data):
    
    try:
        if not data or 'messages' not in data:
            print("No messages in data")
            return None
        
        messages = data['messages']
        if not messages:
            print("Empty messages array")
            return None
            
        sorted_messages = sorted(messages, key=lambda x: x.get('timestamp', 0), reverse=True)
        if sorted_messages:
            print(f"Found last message: {sorted_messages[0].get('body', {}).get('text', '')[:50]}...")
            return sorted_messages[0]
            
        return None
    except Exception as e:
        print(f"Error getting last message: {str(e)}")
        return None


class ConversationHandler(threading.Thread):
   
    def check_and_send_followup(self, messages):
        
        try:
            if not messages:
                return False

            last_message = get_last_message(messages)
            print(f"last Message {last_message}")
            if not last_message:
                return False

            current_time = time.time()
            msg_timestamp = last_message.get('timestamp', 0)
            timestamp_in_seconds = msg_timestamp / 1000 if msg_timestamp > 1000000000000 else msg_timestamp

            
            was_from_us = str(last_message.get('senderId')) == str(self.account_id)
            time_since_last = current_time - timestamp_in_seconds

            if was_from_us and time_since_last >= self.FOLLOWUP_TIMEOUT and self.profile.get("chatMode") != "gpt":
                print(f"Last message was ours from {time_since_last/3600:.2f} hours ago, sending follow-up...")
                answer = generateMessage(
                    profile=self.profile,
                    senderId=str(self.account_id),
                    recipientID=str(self.recipient_id),
                    city=self.city,
                    messageId=str(current_time),
                    timestamp=int(current_time * 1000),
                    receipantName=self.recipient_name,
                    messageBody="",  
                    isIncoming=False,
                    sequenceEnabled=True  
                )

                if answer:
                    messages = [msg.strip() for msg in answer.split("~")] if "~" in answer else [answer]
                    if self.send_messages(messages, is_new_chat=False):
                        print(f"Successfully sent follow-up: {messages}")
                        self.last_message_time = current_time * 1000
                        self.last_sent_time = current_time
                        return True

            return False
        except Exception as e:
            print(f"Error in follow-up check: {str(e)}")
            return False

    def get_account_city(self):
        
        
            return self.acc.get("city")

    def _is_user_online(self, user_id):
        
        
        return False

    def send_message(self, message, is_new_chat=False):
        
        try:
            if not self.city:
                print(f"Cannot send message - no city assigned for account {self.account_id}")
                return False

            is_online = self._is_user_online(self.recipient_id)
            
            
            if is_online:
                delay = random.uniform(5, 10)
            else:
                delay = random.uniform(1, 5) if not is_new_chat else 0
                
            time.sleep(delay)
            
            
            with open(self.send_file, "w") as f:
                f.write(f"{self.recipient_id}:{message}")
            
            self.chat_manager.accepted_chats.add(self.conversation_id)
            return True

        except Exception as e:
            print(f"Error sending message: {str(e)}")
            return False
    def get_conversation_messages(self):
        
        try:
            headers = {
                'Host': 'grindr.mobi',
                'Authorization': str(self.auth),
                'L-Time-Zone': 'Unknown',
                'L-Grindr-Roles': '[]',
                'L-Device-Info': self.device_info,
                'Accept': 'application/json',
                'User-Agent': self.user_agent,
                'L-Locale': 'en_US',
                'Accept-Language': 'en-US',
                'Content-Type': 'application/json; charset=UTF-8',
                'Accept-Encoding': 'gzip, deflate, br'
            }
            
            url = f'https://grindr.mobi/v4/chat/conversation/{self.conversation_id}/message'
            
            print(f"Fetching messages for conversation {self.conversation_id}...")
            
            response = session.get(url, headers=headers)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    
                    
                    if 'messages' in data and data['messages']:
                        
                        messages = sorted(data['messages'], 
                                    key=lambda x: x.get('timestamp', 0))
                        
                        
                        if messages:
                            first_msg_time = messages[0].get('timestamp', 0)
                            last_msg_time = messages[-1].get('timestamp', 0)
                            print(f"Found {len(messages)} messages from "
                                f"{datetime.fromtimestamp(first_msg_time/1000 if first_msg_time > 1000000000000 else first_msg_time)} "
                                f"to {datetime.fromtimestamp(last_msg_time/1000 if last_msg_time > 1000000000000 else last_msg_time)}")
                        
                        return {
                            'messages': messages,
                            'lastReadTimestamp': data.get('lastReadTimestamp'),
                            'metadata': data.get('metadata', {}),
                            'profile': data.get('profile')
                        }
                    else:
                        print(f"No messages found in conversation {self.conversation_id}")
                        return None
                        
                except json.JSONDecodeError as e:
                    print(f"Error parsing JSON response: {str(e)}")
                    return None
                    
            elif response.status_code == 404:
                print(f"Conversation {self.conversation_id} not found")
                return None
                
            else:
                print(f"Error fetching messages, status code: {response.status_code}")
                print(f"Response: {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"Network error fetching messages: {str(e)}")
            return None
            
        except Exception as e:
            print(f"Unexpected error fetching messages: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return None

    def parse_message_timestamp(self, timestamp):
        
        if timestamp > 1000000000000:  
            return timestamp / 1000
        return timestamp

    def format_message_for_logging(self, message):
        
        try:
            timestamp = self.parse_message_timestamp(message.get('timestamp', 0))
            time_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            sender = "Bot" if str(message.get('senderId')) == str(self.account_id) else "User"
            text = message.get('body', {}).get('text', '')
            return f"[{time_str}] {sender}: {text[:50]}{'...' if len(text) > 50 else ''}"
        except Exception as e:
            return f"Error formatting message: {str(e)}"

    def get_last_message(self, messages_data):
        
        try:
            if not messages_data or 'messages' not in messages_data:
                return None
                
            messages = messages_data['messages']
            if not messages:
                return None
                
            
            sorted_messages = sorted(messages, 
                                key=lambda x: x.get('timestamp', 0), 
                                reverse=True)
            
            if sorted_messages:
                last_msg = sorted_messages[0]
                print(f"Last message: {self.format_message_for_logging(last_msg)}")
                return last_msg
                
            return None
        except Exception as e:
            print(f"Error getting last message: {str(e)}")
            return None
    def send_message(self, message, is_new_chat=False):
            try:
                if not self.city:
                    print(f"Cannot send message - no city assigned for account {self.account_id}")
                    return False

                is_online = self._is_user_online(self.recipient_id)
                
                
                if is_online:
                    delay = random.uniform(5, 10)
                else:
                    delay = random.uniform(1, 5) if not is_new_chat else 0
                    
                time.sleep(delay)
                
                
                sendMessage(
                    auth=self.auth,
                    deviceInfo=self.device_info,
                    userAgent=self.user_agent,
                    recipientProfileId=str(self.recipient_id),
                    body=message,
                    proxies=proxy_manager.load_proxies()
                )
                
                self.chat_manager.accepted_chats.add(self.conversation_id)
                return True

            except Exception as e:
                print(f"Error sending message: {str(e)}")
                return False

    def run(self):
        print(f"\n{'='*50}")
        print(f"Starting conversation handler for {self.conversation_id}")
        print(f"Initial settings - Chat mode: {self.profile.get('chatMode', 'bot')}, City: {self.city or 'Unknown'}")
        
        

        try:
            while True:
                try:
                    if not self.city:
                        print(f"[Handler] Missing city information for {self.conversation_id}")
                        time.sleep(30)
                        continue

                    messages_data = self.get_conversation_messages()
                    if not messages_data:
                        time.sleep(10)
                        continue

                    has_updates = False


                   

                    
                    if self.profile.get("chatMode") != "gpt":
                        if not self.check_and_send_followup(messages_data):
                            last_msg = self.get_last_message(messages_data)
                            if last_msg:
                                self.handle_message(last_msg, messages_data)
                                has_updates = True
                    else:
                        last_msg = self.get_last_message(messages_data)
                        if last_msg:
                            self.handle_message(last_msg, messages_data)
                            has_updates = True

                    
                    if not has_updates:
                        print(f"[{self.conversation_id}] No updates, waiting for the next loop...")
                        time.sleep(10)

                except Exception as e:
                    print(f"[Error] Error in main loop: {str(e)}")
                    traceback.print_exc()
                    time.sleep(30)

        finally:
            self._cleanup_websocket()

    def validate_conversation_timestamps(self, messages_data):
            
            try:
                if not messages_data or 'messages' not in messages_data:
                    return
                    
                messages = messages_data['messages']
                if not messages:
                    return
                    
                
                timestamps = [msg.get('timestamp', 0) for msg in messages]
                if timestamps != sorted(timestamps):
                    print("Warning: Messages are not in chronological order")
                    
                
                current_time = time.time() * 1000  
                future_messages = [msg for msg in messages 
                                if msg.get('timestamp', 0) > current_time + 60000]  
                if future_messages:
                    print(f"Warning: Found {len(future_messages)} messages with future timestamps")
                    
                
                one_year_ago = (current_time - (365 * 24 * 60 * 60 * 1000))  
                old_messages = [msg for msg in messages 
                            if msg.get('timestamp', 0) < one_year_ago]
                if old_messages:
                    print(f"Warning: Found {len(old_messages)} messages older than 1 year")
                    
            except Exception as e:
                print(f"Error validating timestamps: {str(e)}")
    def prepare_gpt_messages(self, messages_data):
            
            try:
                if not messages_data or 'messages' not in messages_data:
                    return []

                conversation_history = []
                messages = sorted(messages_data['messages'], key=lambda x: x.get('timestamp', 0))
                
                for msg in messages:
                    role = "assistant" if str(msg.get('senderId')) == str(self.account_id) else "user"
                    text = msg.get('body', {}).get('text', '')
                    if text:  
                        conversation_history.append({
                            "role": role,
                            "content": text
                        })

                return conversation_history

            except Exception as e:
                print(f"Error preparing GPT messages: {str(e)}")
                return []

    def handle_message(self, last_msg, messages_data):
            try:
                if not last_msg or not self.city:
                    return

                msg_timestamp = last_msg.get('timestamp', 0)
                
                if msg_timestamp <= self.last_message_time:
                    return

                is_incoming = str(last_msg.get('senderId')) != str(self.account_id)
                if is_incoming:
                    self.last_received_time = time.time()
                else:
                    self.last_sent_time = time.time()
                    return

                message_text = last_msg.get("body", {}).get("text", "") or "picture"
                current_time = time.time()

                
                is_new_chat = True
                if is_new_chat and not self.chat_manager.should_process_new_chats():
                    return

                if self.profile.get("chatMode") == "gpt" and self.gpt_handler:
                    
                    conversation_history = self.prepare_gpt_messages(messages_data)
                    
                    if self.gpt_framework:
                        conversation_history.insert(0, {
                            "role": "system",
                            "content": self.gpt_framework
                        })
                    
                    
                    conversation_history.append({
                        "role": "user",
                        "content": message_text
                    })
                    
                    print(f"Sending conversation to GPT with {len(conversation_history)} messages")
                    responses = self.gpt_handler.generate_response(
                        conversation_history,
                        self.gpt_framework
                    )
                    
                    if responses:
                        if self.send_messages(responses, is_new_chat):
                            
                            self.chat_history = conversation_history + [{
                                "role": "assistant",
                                "content": " ".join(responses)
                            }]
                            self.last_message_time = msg_timestamp
                            self.last_sent_time = current_time
                            if is_new_chat:
                                self.chat_manager.new_chats_processed += 1
                    
                else:
                    
                    answer = generateMessage(
                        profile=self.profile,
                        senderId=str(self.account_id),
                        recipientID=str(self.recipient_id),
                        city=self.city,
                        messageId=last_msg.get("messageId"),
                        timestamp=int(msg_timestamp),
                        receipantName=self.recipient_name,
                        messageBody=message_text,
                        isIncoming=True,
                        sequenceEnabled=False
                    )

                    if answer:
                        messages = [msg.strip() for msg in answer.split("~")] if "~" in answer else [answer]
                        if self.send_messages(messages, is_new_chat):
                            self.last_message_time = msg_timestamp
                            self.last_sent_time = current_time
                            if is_new_chat:
                                self.chat_manager.new_chats_processed += 1

            except Exception as e:
                print(f"Error handling message: {str(e)}")
                import traceback
                print(traceback.format_exc())


    def __init__(self, auth, device_info, user_agent, conversation_id, profile, account_id, recipient_id, recipient_name, proxies , acc):
        threading.Thread.__init__(self)
        
        self.auth = auth
        self.device_info = device_info
        self.user_agent = user_agent
        self.conversation_id = conversation_id
        self.profile = profile
        self.account_id = account_id
        self.recipient_id = recipient_id
        self.recipient_name = recipient_name
        self.proxies = proxy_manager.load_proxies()
        self.acc = acc
        self.city = acc.get('city')
        self.city1 = acc.get('city')
        self.last_message_time = 0
        self.last_sent_time = 0
        self.last_received_time = time.time()
        self.chat_history = []
        self.daemon = True
        self.FOLLOWUP_TIMEOUT = 28800  
        self.chat_manager = ChatManager()     
        self.messages_dir = "messages"
        os.makedirs(self.messages_dir, exist_ok=True)
        self.send_file = os.path.join(self.messages_dir, f"send_message_{self.account_id}.txt")
        self.receive_file = os.path.join(self.messages_dir, f"received_messages_{self.account_id}.txt")
                
        if not self.city:
            print(f"Warning: No city found for account {self.account_id}")

        
        self.gpt_handler = None
        self.gpt_framework = None
        if profile.get("chatMode") == "gpt":
            self._initialize_gpt()
    def _initialize_gpt(self):
        
        try:
            gpt_settings = self.profile.get("gptSettings", {})
            primary_key = gpt_settings.get("primaryApiKey")
            if not primary_key:
                print(f"Warning: GPT mode selected but no primary API key provided for conversation {self.conversation_id}")
                return

            self.gpt_handler = GPTHandler(
                primary_api_key=primary_key,
                secondary_api_key=gpt_settings.get("secondaryApiKey"), profile_name=self.recipient_name
            )
            self.gpt_framework = gpt_settings.get("framework", "")
            print(f"[{self.conversation_id}] GPT handler initialized successfully")
        except Exception as e:
            print(f"Error initializing GPT handler: {str(e)}")
            traceback.print_exc()

    def get_account_city(self):
        
        try:
            for account in self.profile.get("Accounts", []):
                if str(account.get("profileId")) == str(self.account_id):
                    city = account.get("city")
                    if city:
                        print(f"Found city {city} for account {self.account_id}")
                        return city
                    break
            return None
        except Exception as e:
            print(f"Error getting city for account {self.account_id}: {str(e)}")
            return None

    def _is_user_online(self, user_id):
        
        return False

    def _ensure_files_exist(self):
        
        try:
            for filepath in [self.send_file, self.receive_file]:
                with open(filepath, 'a+') as f:
                    pass  
        except Exception as e:
            print(f"Error ensuring files exist: {str(e)}")
            raise
    
    def prepare_gpt_messages(self, messages_data):
        """
        Prepare messages for GPT API with proper formatting and conversation history.
        """
        try:
            if not messages_data or 'messages' not in messages_data:
                return []

            messages = sorted(messages_data['messages'], key=lambda x: x.get('timestamp', 0))
            conversation_history = []

            if self.gpt_framework:
                conversation_history.append({
                    "role": "system",
                    "content": self.gpt_framework
                })

            for msg in messages:
                is_from_bot = str(msg.get('senderId')) == str(self.account_id)
                role = "assistant" if is_from_bot else "user"
                
                content = msg.get('body', {}).get('text', '')
                if not content: 
                    content = "[Media message]"
                
                timestamp = msg.get('timestamp', 0)
                timestamp_readable = datetime.fromtimestamp(
                    timestamp / 1000 if timestamp > 1000000000000 else timestamp
                ).strftime('%Y-%m-%d %H:%M:%S')

                if is_from_bot and content:
                    augmented_content = f"Previous response at {timestamp_readable}: {content}"
                    conversation_history.append({
                        "role": role,
                        "content": augmented_content,
                        "timestamp": timestamp 
                    })
                elif content:
                    augmented_content = f"User message at {timestamp_readable}: {content}"
                    conversation_history.append({
                        "role": role,
                        "content": augmented_content,
                        "timestamp": timestamp
                    })

            current_context = {
                "role": "system",
                "content": f"""Current conversation context:
    - Chat mode: {self.profile.get('chatMode', 'bot')}
    - Location: {self.city if self.city else 'Unknown'}
    - Recipient name: {self.recipient_name if self.recipient_name else 'Unknown'}
    Please maintain conversation continuity and context when responding."""
            }
            conversation_history.append(current_context)

            print(f"[GPT] Prepared {len(conversation_history)} messages for GPT")
            for i, msg in enumerate(conversation_history):
                print(f"[GPT] Message {i + 1}: Role = {msg['role']}, "
                    f"Content preview = {msg['content'][:100]}...")
            
            return conversation_history

        except Exception as e:
            print(f"[Error] Failed to prepare GPT messages: {str(e)}")
            traceback.print_exc()
            return []

    def handle_message(self, last_msg, messages_data):
        
        try:
            if not last_msg or not self.city:
                print(f"[Handler] Cannot handle message - missing data or city for {self.conversation_id}")
                return

            msg_timestamp = last_msg.get('timestamp', 0)
            if msg_timestamp <= self.last_message_time:
                return

            is_incoming = str(last_msg.get('senderId')) != str(self.account_id)
            message_text = last_msg.get("body", {}).get("text", "") or "picture"
            self._log_message_details(is_incoming, message_text)

            if is_incoming:
                self.last_received_time = time.time()
                return self._handle_incoming_message(message_text, msg_timestamp, messages_data)
            else:
                self.last_sent_time = time.time()
                print("[Handler] Outgoing message, updating timestamps")

        except Exception as e:
            print(f"[Error] Message handler error: {str(e)}")
            traceback.print_exc()

    def _handle_incoming_message(self, message_text, msg_timestamp, messages_data):
        
        try:
            if self.profile.get("chatMode") == "gpt" and self.gpt_handler:
                return self._handle_gpt_message(message_text, msg_timestamp, messages_data)
            else:
                return self._handle_bot_message(message_text, msg_timestamp)
        except Exception as e:
            print(f"[Error] Failed to handle incoming message: {str(e)}")
            return False

    def _handle_gpt_message(self, message_text, msg_timestamp, messages_data):
        
        print("[GPT] Using GPT mode for response")
        conversation_history = self.prepare_gpt_messages(messages_data)
        if self.gpt_framework:
            conversation_history.insert(0, {
                "role": "system",
                "content": self.gpt_framework
            })
        
        conversation_history.append({
            "role": "user",
            "content": message_text
        })
        
        
        responses = self.gpt_handler.generate_response(
            conversation_history,
            self.gpt_framework
        )
        
        if not responses:
            print("[GPT] No response generated")
            return False

        
        print(f"[GPT] Generated {len(responses)} responses")
        for i, resp in enumerate(responses, 1):
            print(f"[GPT] Response {i}: {resp[:100]}")
        
        if self.send_messages(responses, is_new_chat=False):
            self._update_chat_history(conversation_history, responses, msg_timestamp)
            return True
        
        print("[GPT] Failed to send responses")
        return False

    def _handle_bot_message(self, message_text, msg_timestamp):
        
        print("[Bot] Using bot mode for response")
        
        answer = generateMessage(
            profile=self.profile,
            senderId=str(self.account_id),
            recipientID=str(self.recipient_id),
            city= self.acc.get("city"),
            messageId=str(msg_timestamp),
            timestamp=int(msg_timestamp),
            receipantName=self.recipient_name,
            messageBody=message_text,
            isIncoming=True,
            sequenceEnabled=False
        )

        if not answer:
            print("[Bot] No response generated")
            return False

        print(f"[Bot] Generated response: {answer[:100]}")
        messages = [msg.strip() for msg in answer.split("~")] if "~" in answer else [answer]
        
        if len(messages) > 1:
            print(f"[Bot] Split into {len(messages)} messages")
            for i, msg in enumerate(messages, 1):
                print(f"[Bot] Message {i}: {msg[:100]}")
        
        if self.send_messages(messages, is_new_chat=False):
            self.last_message_time = msg_timestamp
            self.last_sent_time = time.time()
            return True
        
        print("[Bot] Failed to send messages")
        return False

    def _update_chat_history(self, conversation_history, responses, msg_timestamp):
        
        self.chat_history = conversation_history + [{
            "role": "assistant",
            "content": " ".join(responses)
        }]
        self.last_message_time = msg_timestamp
        self.last_sent_time = time.time()

    def _log_message_details(self, is_incoming, message_text):
        
        print("\n" + "="*50)
        print(f"[Handler] Processing message for conversation {self.conversation_id}")
        print(f"[Handler] Message from: {'User' if is_incoming else 'Bot'}")
        print(f"[Handler] Message text: {message_text[:100]}")
        print(f"[Handler] Chat mode: {self.profile.get('chatMode', 'bot')}")
    def send_message(self, message, is_new_chat=False):
        
        try:
            if not self.city:
                print(f"[Send] Cannot send message - no city assigned for account {self.account_id}")
                return False

            self._log_send_attempt(message, is_new_chat)
            
            
            delay = self._calculate_delay(is_new_chat)
            time.sleep(delay)
            
            
            sendMessage(
                auth=self.auth,
                deviceInfo=self.device_info,
                userAgent=self.user_agent,
                recipientProfileId=str(self.recipient_id),
                body=message,
                proxies=proxy_manager.load_proxies()
            )
            
            print(f"[Send] Message sent successfully to {self.recipient_id}")
            self.chat_manager.accepted_chats.add(self.conversation_id)
            return True

        except Exception as e:
            print(f"[Error] Failed to send message: {str(e)}")
            traceback.print_exc()
            return False

    def send_messages(self, messages, is_new_chat=False):
        
        try:
            for message in messages:
                if not message.strip():
                    continue
                    
                if not self.send_message(message.strip(), is_new_chat):
                    print("[Error] Failed to send message batch")
                    return False
            return True
        except Exception as e:
            print(f"[Error] Failed to send messages: {str(e)}")
            return False

    def _calculate_delay(self, is_new_chat):
        
        is_online = self._is_user_online(self.recipient_id)
        
        if is_online:
            delay = random.uniform(5, 10)
        else:
            delay = random.uniform(1, 5) if not is_new_chat else 0
        
        return delay

    def _log_send_attempt(self, message, is_new_chat):
        
        print(f"\n[Send] Preparing to send message:")
        print(f"[Send] To: {self.recipient_id}")
        print(f"[Send] Message: {message[:100]}")
        print(f"[Send] New chat: {is_new_chat}")

    def check_and_send_followup(self, messages):
        
        try:
            if not self._should_send_followup(messages):
                return False

            print(f"[Followup] Sending follow-up message...")
            return self._send_followup_message()

        except Exception as e:
            print(f"[Error] Follow-up check failed: {str(e)}")
            return False

    def _should_send_followup(self, messages):
        
        if not messages:
            return False

        last_message = get_last_message(messages)
        if not last_message:
            return False

        current_time = time.time()
        msg_timestamp = last_message.get('timestamp', 0)
        timestamp_in_seconds = msg_timestamp / 1000 if msg_timestamp > 1000000000000 else msg_timestamp

        
        was_from_us = str(last_message.get('senderId')) == str(self.account_id)
        time_since_last = current_time - timestamp_in_seconds
        should_followup = (
            was_from_us and 
            time_since_last >= self.FOLLOWUP_TIMEOUT and 
            self.profile.get("chatMode") != "gpt"
        )

        if should_followup:
            print(f"[Followup] Last message was ours from {time_since_last/3600:.2f} hours ago")
            return True
        return False

    def _send_followup_message(self):
        current_time = time.time()
        answer = generateMessage(
            profile=self.profile,
            senderId=str(self.account_id),
            recipientID=str(self.recipient_id),
            city=self.acc.get("city"),
            messageId=str(current_time),
            timestamp=int(current_time * 1000),
            receipantName=self.recipient_name,
            messageBody="",  
            isIncoming=False,
            sequenceEnabled=True
        )

        if not answer:
            return False

        messages = [msg.strip() for msg in answer.split("~")] if "~" in answer else [answer]
        if self.send_messages(messages, is_new_chat=False):
            print(f"[Followup] Successfully sent: {messages}")
            self.last_message_time = current_time * 1000
            self.last_sent_time = current_time
            return True

        return False
    def _start_websocket(self):
        
        try:
            if os.path.exists(self.websocket_pid_file):
                print(f"[WebSocket] Process already exists for account {self.account_id}")
                return True

            print(f"[WebSocket] Starting new process for account {self.account_id}")
            self.websocket_process = subprocess.Popen([
                'main.exe',
                self.auth,
                self.device_info,
                self.user_agent
            ])

            with open(self.websocket_pid_file, "w") as f:
                f.write(str(self.websocket_process.pid))
            
            return True

        except Exception as e:
            print(f"[Error] Failed to start WebSocket process: {str(e)}")
            return False

    def _cleanup_websocket(self):
        
        try:
            if os.path.exists(self.websocket_pid_file):
                os.remove(self.websocket_pid_file)
            
            if self.websocket_process:
                self.websocket_process.terminate()
                self.websocket_process = None
        except Exception as e:
            print(f"[Error] WebSocket cleanup failed: {str(e)}")

    def run(self):
        
        print(f"\n{'='*50}")
        print(f"Starting conversation handler for {self.conversation_id}")
        print(f"Initial settings - Chat mode: {self.profile.get('chatMode', 'bot')}, City: {self.city or 'Unknown'}")
        
        if not self._start_websocket():
            print("[Error] Failed to start WebSocket, exiting thread")
            return

        try:
            while True:
                try:
                    
                    if not self.city:
                        print(f"[Handler] Missing city information for {self.conversation_id}")
                        time.sleep(30)
                        continue

                    
                    messages_data = self.get_conversation_messages()
                    if not messages_data:
                        time.sleep(10)
                        continue

                    
                    if self.profile.get("chatMode") != "gpt":
                        if not self.check_and_send_followup(messages_data):
                            last_msg = self.get_last_message(messages_data)
                            if last_msg:
                                self.handle_message(last_msg, messages_data)
                    else:
                        last_msg = self.get_last_message(messages_data)
                        if last_msg:
                            self.handle_message(last_msg, messages_data)
                    
                    time.sleep(10)

                except Exception as e:
                    print(f"[Error] Error in main loop: {str(e)}")
                    traceback.print_exc()
                    time.sleep(30)

        finally:
            self._cleanup_websocket()

    def __del__(self):
        
        self._cleanup_websocket()


    def check_inactivity(self, messages_data):
        
        try:
            if not messages_data or 'messages' not in messages_data:
                return False

            current_time = time.time()
            messages = messages_data['messages']
            
            if not messages:
                return False

            
            latest_message = max(messages, key=lambda x: x.get('timestamp', 0))
            msg_timestamp = latest_message.get('timestamp', 0)
            timestamp_in_seconds = msg_timestamp / 1000 if msg_timestamp > 1000000000000 else msg_timestamp
            
            
            time_since_last = current_time - timestamp_in_seconds
            
            
            if time_since_last >= 28800:  
                print(f"[Inactivity] No messages for {time_since_last/3600:.2f} hours")
                
                if self.profile.get("chatMode") == "gpt":
                    
                    conversation_history = self.prepare_gpt_messages(messages_data)
                    conversation_history.append({
                        "role": "user", 
                        "content": ""
                    })
                    responses = self.gpt_handler.generate_response(
                        conversation_history,
                        self.gpt_framework
                    )
                    message = responses[0] if responses else "hi"
                else:
                    message = generateMessage(
                        profile=self.profile,
                        senderId=str(self.account_id),
                        recipientID=str(self.recipient_id),
                        city=self.acc.get("city"),
                        messageId=str(current_time),
                        timestamp=int(current_time * 1000),
                        receipantName=self.recipient_name,
                        messageBody="hi",
                        isIncoming=False,
                        sequenceEnabled=False
                    )
                
                
                if message and self.send_message(message, is_new_chat=False):
                    print(f"[Inactivity] Sent message after 8 hours of inactivity: {message}")
                    self.last_message_time = current_time * 1000
                    self.last_sent_time = current_time
                    return True
                    
            return False
            
        except Exception as e:
            print(f"[Error] Inactivity check failed: {str(e)}")
            return False

    def run(self):
        
        print(f"\n{'='*50}")
        print(f"Starting conversation handler for {self.conversation_id}")
        print(f"Initial settings - Chat mode: {self.profile.get('chatMode', 'bot')}, City: {self.city or 'Unknown'}")
        
        if not self._start_websocket():
            print("[Error] Failed to start WebSocket, exiting thread")
            return

        try:
            while True:
                try:
                    
                    if not self.city:
                        print(f"[Handler] Missing city information for {self.conversation_id}")
                        time.sleep(30)
                        continue

                    
                    messages_data = self.get_conversation_messages()
                    if not messages_data:
                        time.sleep(10)
                        continue

                    
                    if self.check_inactivity(messages_data):
                        time.sleep(10)  
                        continue

                    
                    if self.profile.get("chatMode") != "gpt":
                        if not self.check_and_send_followup(messages_data):
                            last_msg = self.get_last_message(messages_data)
                            if last_msg:
                                self.handle_message(last_msg, messages_data)
                    else:
                        last_msg = self.get_last_message(messages_data)
                        if last_msg:
                            self.handle_message(last_msg, messages_data)
                    
                    time.sleep(10)

                except Exception as e:
                    print(f"[Error] Error in main loop: {str(e)}")
                    traceback.print_exc()
                    time.sleep(30)

        finally:
            self._cleanup_websocket()
    def run(self):
        print(f"\n{'='*50}")
        print(f"Starting conversation handler for {self.conversation_id}")
        print(f"Initial settings - Chat mode: {self.profile.get('chatMode', 'bot')}, City: {self.city or 'Unknown'}")

        try:
            while True:
                try:
                    if not self.city:
                        print(f"[Handler] Missing city information for {self.conversation_id}")
                        time.sleep(30)
                        continue

                    messages_data = self.get_conversation_messages()

                    if self.profile.get("chatMode") != "gpt":
                        if not self.check_and_send_followup(messages_data):
                            last_msg = self.get_last_message(messages_data)
                            if last_msg:
                                self.handle_message(last_msg, messages_data)
                    else:
                        last_msg = self.get_last_message(messages_data)
                        if last_msg:
                            self.handle_message(last_msg, messages_data)

                    time.sleep(10)

                except Exception as e:
                    print(f"[Error] Error in main loop: {str(e)}")
                    traceback.print_exc()
                    time.sleep(30)

        except Exception as e:
            print(f"Fatal error in conversation handler: {str(e)}")
            traceback.print_exc()
    def check_inactivity(self, messages_data):
        """
        Check and handle conversation inactivity with full message history context.
        """
        try:
            if not messages_data or 'messages' not in messages_data:
                return False

            current_time = time.time()
            messages = messages_data['messages']
            
            if not messages:
                return False

            latest_message = max(messages, key=lambda x: x.get('timestamp', 0))
            msg_timestamp = latest_message.get('timestamp', 0)
            timestamp_in_seconds = msg_timestamp / 1000 if msg_timestamp > 1000000000000 else msg_timestamp
            
            time_since_last = current_time - timestamp_in_seconds
            
            if time_since_last >= 28800:  
                print(f"[Inactivity] No messages for {time_since_last/3600:.2f} hours")
                
                if self.profile.get("chatMode") == "gpt":
                    conversation_history = self.prepare_gpt_messages(messages_data)
                    
                    conversation_history.append({
                        "role": "system",
                        "content": f"""
                        This conversation has been inactive for {time_since_last/3600:.1f} hours.
                        Please generate a natural conversation re-engagement message.
                        Consider previous context and maintain conversation continuity.
                        Last message timestamp: {datetime.fromtimestamp(timestamp_in_seconds).strftime('%Y-%m-%d %H:%M:%S')}
                        """
                    })
                    
                    conversation_history.append({
                        "role": "user",
                        "content": "The conversation needs re-engagement after a period of inactivity."
                    })
                    
                    responses = self.gpt_handler.generate_response(
                        conversation_history=conversation_history,
                        framework=self.gpt_framework,
                        city=self.acc.get("city")
                    )
                    message = responses[0] if responses else self._generate_fallback_message()
                
                else:
                    message = generateMessage(
                        profile=self.profile,
                        senderId=str(self.account_id),
                        recipientID=str(self.recipient_id),
                        city=self.acc.get("city"),
                        messageId=str(current_time),
                        timestamp=int(current_time * 1000),
                        receipantName=self.recipient_name,
                        messageBody="", 
                        isIncoming=False,
                        sequenceEnabled=True
                    )
                

                if message and self.send_message(message, is_new_chat=False):
                    print(f"[Inactivity] Successfully sent re-engagement message: {message[:100]}...")
                    self.last_message_time = current_time * 1000
                    self.last_sent_time = current_time
                    

                    if self.profile.get("chatMode") == "gpt":
                        self._update_chat_history(conversation_history, [message], current_time * 1000)
                        
                    return True
                    
            return False
                
        except Exception as e:
            print(f"[Error] Inactivity check failed: {str(e)}")
            traceback.print_exc()
            return False

    def _generate_fallback_message(self):
        """Generate a fallback message if GPT response fails."""
        fallback_messages = [
            "Hey, how are you doing?",
            "Hope you're having a good day!",
            "Just checking in to say hi!",
            "Still around? Would love to chat more!",
            "Hope I didn't miss anything! How are things?"
        ]
        return random.choice(fallback_messages)

    def _update_chat_history(self, conversation_history, responses, msg_timestamp):
        """Update chat history with new messages."""
        try:

            response_content = " ".join(responses)
            conversation_history.append({
                "role": "assistant",
                "content": response_content,
                "timestamp": msg_timestamp
            })
            
            self.chat_history = conversation_history
            self.last_message_time = msg_timestamp
            self.last_sent_time = time.time()
            
            print(f"[GPT] Updated chat history - {len(conversation_history)} messages total")
            
        except Exception as e:
            print(f"[Error] Failed to update chat history: {str(e)}")
            traceback.print_exc()
    def _log_conversation_history(self, conversation_history, context=""):
        """
        Log the full conversation history being sent to GPT.
        """
        print(f"\n{'='*80}")
        print(f"[GPT] Conversation History - {context}")
        print(f"{'='*80}")
        print(f"Total messages: {len(conversation_history)}")
        print(f"Conversation ID: {self.conversation_id}")
        print(f"User: {self.recipient_name}")
        print(f"City: {self.city}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}")
        
        for i, msg in enumerate(conversation_history, 1):
            print(f"\nMessage {i}:")
            print(f"Role: {msg['role']}")
            print(f"Content: {msg['content']}")
            if 'timestamp' in msg:
                timestamp = msg['timestamp']
                if timestamp > 1000000000000: 
                    timestamp = timestamp / 1000
                print(f"Timestamp: {datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'-'*40}")

    def _handle_gpt_message(self, message_text, msg_timestamp, messages_data):
        """
        Handle incoming message using GPT with full conversation context.
        """
        print("[GPT] Processing new message with GPT")
        
        try:
            conversation_history = self.prepare_gpt_messages(messages_data)
            
            conversation_history.append({
                "role": "user",
                "content": f"Current message: {message_text}",
                "timestamp": msg_timestamp
            })
            
            self._log_conversation_history(conversation_history, "New Message Processing")
            
            responses = self.gpt_handler.generate_response(
                conversation_history=conversation_history,
                framework=self.gpt_framework,
                city=self.acc.get("city")
            )
            
            if not responses:
                print("[GPT] No response generated")
                return False
                
            if self.send_messages(responses, is_new_chat=False):
                self._update_chat_history(conversation_history, responses, msg_timestamp)
                return True
            
            print("[GPT] Failed to send responses")
            return False

        except Exception as e:
            print(f"[Error] GPT message handling failed: {str(e)}")
            traceback.print_exc()
            return False

    def check_inactivity(self, messages_data):
        """
        Check and handle conversation inactivity with full message history context.
        """
        try:
            if not messages_data or 'messages' not in messages_data:
                return False

            current_time = time.time()
            messages = messages_data['messages']
            
            if not messages:
                return False

            latest_message = max(messages, key=lambda x: x.get('timestamp', 0))
            msg_timestamp = latest_message.get('timestamp', 0)
            timestamp_in_seconds = msg_timestamp / 1000 if msg_timestamp > 1000000000000 else msg_timestamp
            
            time_since_last = current_time - timestamp_in_seconds
            
            if time_since_last >= 28800:  
                print(f"[Inactivity] No messages for {time_since_last/3600:.2f} hours")
                
                if self.profile.get("chatMode") == "gpt":
                    conversation_history = self.prepare_gpt_messages(messages_data)
                    
                    conversation_history.append({
                        "role": "system",
                        "content": f"""
                        This conversation has been inactive for {time_since_last/3600:.1f} hours.
                        Please generate a natural conversation re-engagement message.
                        Consider previous context and maintain conversation continuity.
                        Last message timestamp: {datetime.fromtimestamp(timestamp_in_seconds).strftime('%Y-%m-%d %H:%M:%S')}
                        """,
                        "timestamp": current_time
                    })
                    
                    conversation_history.append({
                        "role": "user",
                        "content": "The conversation needs re-engagement after a period of inactivity.",
                        "timestamp": current_time
                    })
                    
                    self._log_conversation_history(conversation_history, "Inactivity Re-engagement")
                    
                    responses = self.gpt_handler.generate_response(
                        conversation_history=conversation_history,
                        framework=self.gpt_framework,
                        city=self.acc.get("city")
                    )
                    message = responses[0] if responses else self._generate_fallback_message()
                
                else:
                    message = generateMessage(
                        profile=self.profile,
                        senderId=str(self.account_id),
                        recipientID=str(self.recipient_id),
                        city=self.acc.get("city"),
                        messageId=str(current_time),
                        timestamp=int(current_time * 1000),
                        receipantName=self.recipient_name,
                        messageBody="",
                        isIncoming=False,
                        sequenceEnabled=True
                    )
                
                if message and self.send_message(message, is_new_chat=False):
                    print(f"[Inactivity] Successfully sent re-engagement message: {message[:100]}...")
                    self.last_message_time = current_time * 1000
                    self.last_sent_time = current_time
                    
                    if self.profile.get("chatMode") == "gpt":
                        self._update_chat_history(conversation_history, [message], current_time * 1000)
                        self._log_conversation_history(self.chat_history, "Post-Inactivity Update")
                        
                    return True
                    
            return False
                
        except Exception as e:
            print(f"[Error] Inactivity check failed: {str(e)}")
            traceback.print_exc()
            return False

    def prepare_gpt_messages(self, messages_data):
        """
        Prepare messages for GPT API with proper formatting and conversation history.
        """
        try:
            conversation_history = []
            
            if self.gpt_framework:
                conversation_history.append({
                    "role": "system",
                    "content": self.gpt_framework,
                    "timestamp": time.time()
                })

            messages = sorted(messages_data.get('messages', []), 
                            key=lambda x: x.get('timestamp', 0))
            
            for msg in messages:
                timestamp = msg.get('timestamp', 0)
                is_from_bot = str(msg.get('senderId')) == str(self.account_id)
                content = msg.get('body', {}).get('text', '') or '[Media message]'
                
                conversation_history.append({
                    "role": "assistant" if is_from_bot else "user",
                    "content": content,
                    "timestamp": timestamp
                })

            self._log_conversation_history(conversation_history, "Message Preparation")
            
            return conversation_history

        except Exception as e:
            print(f"[Error] Failed to prepare GPT messages: {str(e)}")
            traceback.print_exc()
            return []

def handle_tap_message(profile, account,account_id, profile_id, tap_info, chat_mode="bot"):
   
    try:
        current_time = time.time()
        timestamp = int(current_time * 1000)
        
        if chat_mode == "gpt":
            gpt_settings = profile.get("gptSettings", {})
            gpt_handler = GPTHandler(
                primary_api_key=gpt_settings.get("primaryApiKey"),
                secondary_api_key=gpt_settings.get("secondaryApiKey"),
                profile_name=tap_info.get("displayName", "")
            )
            framework = gpt_settings.get("framework", "")
            conversation_history = [{
                "role": "system",
                "content": framework
            }, {
                "role": "user",
                "content": "User has just sent a tap"
            }]
            print(conversation_history)
            responses = gpt_handler.generate_response(
                conversation_history=conversation_history,
                framework=framework,
                city=account.get("city", "")
            )
            if responses and responses[0]:
                return responses[0]
            return None
            
        else:
            return generateMessage(
                profile=profile,
                senderId=str(account_id),
                recipientID=str(profile_id),
                city=profile.get("city", ""),
                messageId=str(current_time),
                timestamp=timestamp,
                receipantName=tap_info.get("displayName", ""),
                messageBody="", 
                isIncoming=True,
                sequenceEnabled=False
            )
            
    except Exception as e:
        print(f"Error generating tap response: {str(e)}")
        traceback.print_exc()
        return None
def thisIsGonnaBeAThread(listAccounts, profile, account, proxies):
    proxies = proxy_manager.load_proxies()
    try:
        conversation_threads = {}
        retry = 0
        while retry < 30:
            try:
                proxy = random.choice(proxies)
                proxies.remove(proxy)
                session.proxies.update({"http":proxy , "https":proxy})
                break
            except Exception as e:
                
                retry += 1
        device_info = account.get('deviceInfo')
        user_agent = account.get("userAgent")
        auth = account.get('grindrToken')
        account_id = getMyId(auth, device_info, user_agent)
        if not account_id:
            print('Account Expired')
            lg = Login(account.get('userName'), account.get('auth'), account.get('token'), device_info, user_agent)
            if not lg:
                return 0
            auth = 'Grindr3 ' + lg.get('sessionId')
            account.update({
                'grindrToken': auth,
                'profileId': lg.get('profileId'),
                'bio': getProfile(auth, device_info, user_agent).get("profiles")[0]["aboutMe"],
                'name': getProfile(auth, device_info, user_agent).get("profiles")[0]["displayName"]
            })
            with open('accounts.json', 'w') as f:
                json.dump(listAccounts, f, indent=4)
            account_id = getMyId(auth, device_info, user_agent)

        if not account.get("city"):
            if not update_account_city(profile, account):
                return

        if not account.get('lat') or not account.get('long'):
            print(f"{account_id} has no city coordinates")
            return

        changeLocation(auth, device_info, user_agent, float(account['lat']), float(account['long']))

        while True:
            try:
                taps = receivedTaps(auth, device_info, user_agent)
                for tap in taps.get('profiles', []):
                    
                    try:
                        profile_id = tap["profileId"]
                        old_conver = session.post(
                            'https://grindr.mobi/v1/inbox/conversation',
                            headers={
                                'Host': 'grindr.mobi',
                                'Authorization': str(auth),
                                'L-Time-Zone': 'Unknown',
                                'L-Grindr-Roles': '[]',
                                'L-Device-Info': device_info,
                                'Accept': 'application/json',
                                'User-Agent': user_agent,
                                'L-Locale': 'en_US',
                                'Accept-Language': 'en-US',
                                'Content-Type': 'application/json; charset=UTF-8',
                                'Accept-Encoding': 'gzip, deflate, br'
                            },
                            json=[f"{profile_id}:{account_id}"]
                        )

                        try:
                            profile_id = tap["profileId"]
                            
                            old_conver = session.post(
                                'https://grindr.mobi/v1/inbox/conversation',
                                headers={
                                    'Host': 'grindr.mobi',
                                    'Authorization': str(auth),
                                    'L-Time-Zone': 'Unknown',
                                    'L-Grindr-Roles': '[]',
                                    'L-Device-Info': device_info,
                                    'Accept': 'application/json',
                                    'User-Agent': user_agent,
                                    'L-Locale': 'en_US',
                                    'Accept-Language': 'en-US',
                                    'Content-Type': 'application/json; charset=UTF-8',
                                    'Accept-Encoding': 'gzip, deflate, br'
                                },
                                json=[f"{profile_id}:{account_id}"]
                            )

                            if old_conver.status_code == 200 and not old_conver.json():
                                answer = handle_tap_message(
                                    profile=profile,
                                    account=account,
                                    account_id=account_id,
                                    profile_id=profile_id,
                                    tap_info=tap,
                                    chat_mode=profile.get("chatMode", "bot"))
                                
                                if answer:
                                    
                                    sendMessage(
                                        auth=auth,
                                        deviceInfo=device_info,
                                        userAgent=user_agent,
                                        recipientProfileId=str(profile_id),
                                        body=answer,
                                        proxies=profile.get("proxies")
                                    )
                                    print(f"Sent tap response to {profile_id}")
                                    
                        except Exception as e:
                            print(f"Error processing individual tap: {str(e)}")
                            continue
                    except Exception as e:
                        print(f"Error processing tap: {str(e)}")
                chats = last300chat(auth, device_info, user_agent)

                print("chat")
                for chat in chats:
                    chat_id = chat.get('conversationId')
                    if chat_id not in conversation_threads or not conversation_threads[chat_id].is_alive():
                        thread = ConversationHandler(
                            auth, device_info, user_agent, chat_id,
                            profile, account_id, chat['recipient'],
                            chat.get('name', ''), proxies , account
                        )
                        
                        thread.start()
                        
                        time.sleep(random.randint(8,12))
                        conversation_threads[chat_id] = thread

                conversation_threads = {k: v for k, v in conversation_threads.items() if v.is_alive()}
                time.sleep(120)  

            except Exception as e:
                print(f"Error in main loop: {str(e)}")

    except Exception as e:
        print(f"Fatal error in thread: {str(e)}")

class AccountManager:
    def __init__(self):
        self.usernameList = []
        self.processList = []
        self.chat_queues = {}

    def checkAccount(self, listAccounts, profile, account, proxies):
        proxies = proxy_manager.load_proxies()
        username = account.get("userName")
        
        
        if username in self.usernameList:
            print(f"{username} is already running")
            
            for t in self.processList:
                if t["username"] == username and (datetime.now() - t["timestamp"]) >= timedelta(minutes=accountMinutes):
                    print(f"Terminating and restarting process for {username} due to timeout.")
                    t["process"].terminate()
                    t["process"].join()
                    new_process = multiprocessing.Process(target=thisIsGonnaBeAThread, 
                                                        args=(listAccounts, profile, account, proxy_manager.load_proxies()))
                    new_process.start()
                    t["process"] = new_process
                    t["timestamp"] = datetime.now()
        else:
            process = multiprocessing.Process(target=thisIsGonnaBeAThread, 
                                            args=(listAccounts, profile, account, proxy_manager.load_proxies()))
            process.daemon = False
            self.usernameList.append(username)
            self.processList.append({
                "username": username,
                "process": process,
                "timestamp": datetime.now()
            })
            process.start()
            print(f"Started process for account {username}")

    def __init__(self):
        self.usernameList = []
        self.processList = []
        self.chat_queues = {}

    def checkAccount(self, listAccounts, profile, account, proxies):
        proxies =proxy_manager.load_proxies()
        try:
            if not account or not isinstance(account, dict):
                print("Invalid account data provided")
                return
                
            username = account.get("userName")
            if not username:
                print("Account missing username")
                return
            
            if username in self.usernameList:
                print(f"{username} is already running")
                
                for t in self.processList:
                    if t["username"] == username:
                        time_running = datetime.now() - t["timestamp"]
                        if time_running >= timedelta(minutes=accountMinutes):
                            print(f"Terminating and restarting process for {username} due to timeout")
                            try:
                                t["process"].terminate()
                                t["process"].join(timeout=5)
                            except Exception as e:
                                print(f"Error terminating process: {e}")
                            
                            new_process = multiprocessing.Process(
                                target=thisIsGonnaBeAThread, 
                                args=(listAccounts, profile, account, proxy_manager.load_proxies())
                            )
                            new_process.start()
                            t["process"] = new_process
                            t["timestamp"] = datetime.now()
            else:
                process = multiprocessing.Process(
                    target=thisIsGonnaBeAThread, 
                    args=(listAccounts, profile, account, proxy_manager.load_proxies())
                )
                process.daemon = False
                self.usernameList.append(username)
                self.processList.append({
                    "username": username,
                    "process": process,
                    "timestamp": datetime.now()
                })
                process.start()
                print(f"Started process for account {username}")
                
        except Exception as e:
            print(f"Error in checkAccount: {e}")
            traceback.print_exc()
def aupdate_account_city(profile, account):
    
    try:
        
        with open('accounts.json', 'r') as file:
            all_data = json.load(file)
            
        profile_id = profile.get("profile", {}).get("id")
        
        
        for p in all_data:
            if str(p.get("profile", {}).get("id")) == str(profile_id):
                
                used_cities = {
                    acc.get("city") for acc in p.get("Accounts", [])
                    if acc.get("city") and acc["userName"] != account["userName"]
                }
                
                
                available_cities = [
                    city for city in p.get("cities", [])
                    if city["city"] not in used_cities
                ]
                
                
                try:
                    with open("accountsWithoutCities.txt", "r") as f:
                        no_city_accounts = f.read().splitlines()
                except FileNotFoundError:
                    open("accountsWithoutCities.txt", "w").write("")
                    no_city_accounts = []

                if account.get("userName") in no_city_accounts:
                    print(f"Account {account['userName']} is marked as having no city")
                    return False
                
                
                if not available_cities:
                    if account["userName"] not in no_city_accounts:
                        with open("accountsWithoutCities.txt", "a") as f:
                            f.write(f"{account['userName']}\n")
                    print(f"No available cities for account {account['userName']}")
                    return False
                
                
                city = available_cities[0]
                
                
                account["city"] = city["city"]
                account["lat"] = city["lat"]
                account["long"] = city["long"]
                
                
                for i, acc in enumerate(p["Accounts"]):
                    if acc["userName"] == account["userName"]:
                        p["Accounts"][i] = account
                        break
                
                
                with open('accounts.json', 'w') as f:
                    json.dump(all_data, f, indent=4)
                    
                print(f"Successfully assigned city {city['city']} to account {account['userName']}")
                
                
                if account["userName"] in no_city_accounts:
                    removeAccountFromUnusedQueue(account["userName"])
                
                return True
                
        print(f"Profile {profile_id} not found")
        return False
        
    except Exception as e:
        print(f"Error updating account city: {str(e)}")
        traceback.print_exc()
        return False

def removeAccountFromUnusedQueue(username):
    
    try:
        with open("accountsWithoutCities.txt", "r") as f:
            accounts = f.readlines()
        
        with open("accountsWithoutCities.txt", "w") as f:
            for account in accounts:
                if account.strip() != username:
                    f.write(account)
        
        print(f"Removed {username} from unused queue")
    except Exception as e:
        print(f"Error removing from unused queue: {str(e)}")

def validate_city_assignments(profile):
    
    try:
        city_assignments = {}
        accounts_to_reset = []
        
        
        for account in profile.get("Accounts", []):
            city = account.get("city")
            if city:
                if city in city_assignments:
                    
                    accounts_to_reset.append(account)
                else:
                    city_assignments[city] = account["userName"]
        
        
        if accounts_to_reset:
            print(f"Found {len(accounts_to_reset)} accounts with duplicate cities")
            for account in accounts_to_reset:
                account["city"] = None
                account["lat"] = None
                account["long"] = None
                print(f"Reset city assignment for account {account['userName']}")
            
            return True
            
        return False
        
    except Exception as e:
        print(f"Error validating city assignments: {str(e)}")
        return False
def update_account_city(profile, account):
    """
    Update city assignment for an account within the main process with detailed logging.
    """
    try:
        print("\n=== Starting City Assignment Process ===")
        print(f"Account username: {account.get('userName')}")
        print(f"Profile ID: {profile.get('profile', {}).get('id')}")
        
        if not profile or not account or not isinstance(profile, dict) or not isinstance(account, dict):
            print("Failed: Invalid profile or account data structure")
            return False
            
        try:
            with open('accounts.json', 'r') as file:
                all_data = json.load(file)
                print(f"Successfully loaded accounts.json with {len(all_data)} profiles")
        except Exception as e:
            print(f"Failed: Error loading accounts.json: {e}")
            return False
            
        profile_id = profile.get("profile", {}).get("id")
        username = account.get("userName")
        
        if not profile_id or not username:
            print(f"Failed: Missing profile ID or username")
            print(f"Profile ID: {profile_id}")
            print(f"Username: {username}")
            return False
            
        matching_profile = None
        for p in all_data:
            if str(p.get("profile", {}).get("id")) == str(profile_id):
                matching_profile = p
                break
                
        if not matching_profile:
            print(f"Failed: Could not find profile with ID {profile_id}")
            return False
            
        print(f"Found matching profile for ID {profile_id}")
        
        print("\n=== City Analysis ===")
        all_cities = matching_profile.get("cities", [])
        print(f"Total cities in profile: {len(all_cities)}")
        
        used_cities = {
            acc.get("city") for acc in matching_profile.get("Accounts", [])
            if acc.get("city") and acc["userName"] != username
        }
        print(f"Currently used cities: {len(used_cities)}")
        print(f"Used cities: {used_cities}")
        
        available_cities = [
            city for city in matching_profile.get("cities", [])
            if city.get("city") and city["city"] not in used_cities
        ]
        print(f"Available cities: {len(available_cities)}")
        if available_cities:
            print(f"First available city: {available_cities[0].get('city')}")
        
        try:
            with open("accountsWithoutCities.txt", "r") as f:
                no_city_accounts = f.read().splitlines()
                print(f"Accounts without cities: {len(no_city_accounts)}")
        except FileNotFoundError:
            print("Creating new accountsWithoutCities.txt file")
            with open("accountsWithoutCities.txt", "w") as f:
                f.write("")
            no_city_accounts = []

        if username in no_city_accounts:
            print(f"Failed: Account {username} is marked as having no city")
            return False
        
        if not available_cities:
            print(f"Failed: No available cities for account {username}")
            if username not in no_city_accounts:
                try:
                    with open("accountsWithoutCities.txt", "a") as f:
                        f.write(f"{username}\n")
                    print(f"Added {username} to no-city list")
                except Exception as e:
                    print(f"Warning: Could not add to no-city list: {e}")
            return False
        
        city = available_cities[0]
        if not all(key in city for key in ["city", "lat", "long"]):
            print(f"Failed: Invalid city data structure: {city}")
            return False
        
        print("\n=== Updating Account ===")
        print(f"Assigning city: {city['city']}")
        
        account["city"] = city["city"]
        account["lat"] = city["lat"]
        account["long"] = city["long"]
        
        updated = False
        for p in all_data:
            if str(p.get("profile", {}).get("id")) == str(profile_id):
                for acc in p["Accounts"]:
                    if(acc["userName"] == account["userName"]):
                        acc = account
                        updated = True
                        
                        with open('accounts.json', 'w') as f:
                               f.write(json.dumps(all_data))
                               f.flush()
                
        
        if not updated:
            print(f"Failed: Could not find account {username} in profile's accounts")
            return False
        
        try:
            with open('accounts.json', 'w') as f:
                json.dump(all_data, f, indent=4)
            print("Successfully saved updated account data")
        except Exception as e:
            print(f"Failed: Error saving updated account data: {e}")
            return False
            
        print(f"\nSuccess: Assigned city {city['city']} to account {username}")
        
        if username in no_city_accounts:
            try:
                with open("accountsWithoutCities.txt", "r") as f:
                    accounts = f.readlines()
                with open("accountsWithoutCities.txt", "w") as f:
                    for account_name in accounts:
                        if account_name.strip() != username:
                            f.write(account_name)
                print(f"Removed {username} from no-city list")
            except Exception as e:
                print(f"Warning: Error updating no-city list: {e}")
        
        print("=== City Assignment Complete ===\n")
        return True
        
    except Exception as e:
        print(f"Critical Error: {str(e)}")
        traceback.print_exc()
        return False
def validate_city_assignments(profile):
    
    try:
        if not profile or not isinstance(profile, dict):
            print("Invalid profile data")
            return False
            
        city_assignments = {}
        accounts_to_reset = []
        
        
        for account in profile.get("Accounts", []):
            if not account or not isinstance(account, dict):
                continue
                
            city = account.get("city")
            if city:
                if city in city_assignments:
                    
                    accounts_to_reset.append(account)
                else:
                    city_assignments[city] = account.get("userName", "Unknown")
        
        
        if accounts_to_reset:
            print(f"Found {len(accounts_to_reset)} accounts with duplicate cities")
            for account in accounts_to_reset:
                account["city"] = None
                account["lat"] = None
                account["long"] = None
                print(f"Reset city assignment for account {account.get('userName', 'Unknown')}")
            
            return True
            
        return False
        
    except Exception as e:
        print(f"Error validating city assignments: {str(e)}")
        traceback.print_exc()
        return False

def main():
    account_manager = AccountManager()
    print("Starting bot main process...")
    while True:
        try:
            listAccounts = getAccounts()
            if not listAccounts:
                print("No accounts found, waiting before retry...")
                time.sleep(60)
                continue
            for profile in listAccounts:
                if not profile:
                    continue
                if not profile.get("enabled", True):
                    continue
                profile_name = profile.get('profile', {}).get('name', 'Unknown Profile')
                print(f"Processing profile: {profile_name}")
                
                if validate_city_assignments(profile):
                    try:
                        with open('accounts.json', 'w') as f:
                            json.dump(listAccounts, f, indent=4)
                    except Exception as e:
                        print(f"Error saving account data: {e}")
                        continue
                
               
                proxies = proxy_manager.load_proxies()
                for proxy in profile.get('proxies', []):
                    if proxy and isinstance(proxy, str):
                        proxies.append({'http': proxy, 'https': proxy})
                
                if not proxies:
                    print(f"No valid proxies for profile {profile_name}")
                    continue
                
                
                for account in profile.get("Accounts", []):
                    if not account:
                        continue
                    if not account.get("active", True):
                        
                        
                        print(f"Account {account.get('userName', 'Unknown')} is not active, skipping")
                        continue
                    
                    
                    if not account.get("city"):
                        print(f"Assigning city to {account.get('userName', 'Unknown')}")
                        
                        if not ProfileDataManager.update_account_city(profile, account):
                            print(f"Failed to assign city to account, skipping")
                            continue
                    
                    
                    account_manager.checkAccount(listAccounts, profile, account, proxy_manager.load_proxies())
            
            time.sleep(30)
            
        except Exception as e:
            pass