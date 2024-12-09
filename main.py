import re
from threading import Thread
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed 
from typing import Dict, List, Tuple, Optional
from flask import Flask, render_template, request, redirect, flash, url_for, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
import flask
from dataclasses import dataclass
from typing import Optional, Dict, List
import json
import os
import glob
from Auth import *
import multiprocessing
from multiprocessing import Lock
import shutil
app = Flask(__name__)
app.secret_key = 'some_secret_key'  
chat_settings_manager = ChatSettingsManager()
BASE_UPLOAD_FOLDER = 'images'
ALLOWED_EXTENSIONS = {'jpg', 'jpeg'}
lock = multiprocessing.Lock()  

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


@app.route('/proxy-management')
def proxy_management():
    """Global proxy management page."""
    proxies = proxy_manager.load_proxies()
    return render_template('proxy_management.html', 
                         proxies=proxies,
                         proxy_status={}) 

@app.route('/bulk-import-proxies', methods=['POST'])
def bulk_import_proxies():
    """Handle bulk import of proxies."""
    proxies = request.form.get('proxies', '').strip().split('\n')
    proxies = [p.strip() for p in proxies if p.strip()]
    
    if not proxies:
        flash('No valid proxies provided', 'error')
        return redirect(url_for('proxy_management'))
    
    valid_count, invalid_count = proxy_manager.add_proxies(proxies)
    
    if valid_count > 0:
        flash(f'Successfully imported {valid_count} proxies' + 
              (f' ({invalid_count} invalid proxies skipped)' if invalid_count > 0 else ''),
              'success')
    else:
        flash(f'No valid proxies found in input' + 
              (f' ({invalid_count} invalid proxies skipped)' if invalid_count > 0 else ''),
              'error')
    
    return redirect(url_for('proxy_management'))

@app.route('/test-proxies', methods=['POST'])
def test_proxies():
    """Test all proxies and store results."""
    results = proxy_manager.test_all_proxies()
    flash(f'Proxy test complete. Working: {len(results["working"])}, Failed: {len(results["failed"])}', 'success')
    return redirect(url_for('proxy_management'))

@app.route('/delete-failed-proxies', methods=['POST'])
def delete_failed_proxies():
    """Remove all non-working proxies."""
    working, failed = proxy_manager.remove_failed_proxies()
    flash(f'Removed {failed} non-working proxies. {working} proxies remaining.', 'success')
    return redirect(url_for('proxy_management'))

@app.route('/delete-all-proxies', methods=['POST'])
def delete_all_proxies():
    """Delete all proxies."""
    if proxy_manager.save_proxies([]):
        flash('Successfully deleted all proxies', 'success')
    else:
        flash('Error deleting proxies', 'error')
    return redirect(url_for('proxy_management'))


def get_files_in_folder(folder_path):
    return [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def ensure_folder_exists(folder_path):
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

def get_profile_image_folder(profile_id):
    folder = os.path.join(BASE_UPLOAD_FOLDER, str(profile_id))
    ensure_folder_exists(folder)
    return folder

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
def ensure_folder_exists(folder_path):
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
def get_profile_image_folder(profile_id):
    folder = os.path.join(BASE_UPLOAD_FOLDER, str(profile_id))
    ensure_folder_exists(folder)
    return folder
@app.route('/profile/<id>/uploadPictures', methods=['POST'])
def upload_pictures(id):
    picturesCount = request.form.get("picturesCount")
    data = load_data()
    if(picturesCount):
        for profile in data:
            if str(profile["profile"]['id']) == str(id):
                profile_found = True                
                profile["picturesCount"] = picturesCount
                break
        save_data(data)

    if 'pictures' not in request.files:
        flash('No files provided', 'error')
        return redirect(f'/profile/{id}')
    
    files = request.files.getlist('pictures')
    if not files or all(file.filename == '' for file in files):
        flash('No files selected', 'error')
        return redirect(f'/profile/{id}')
    
    
    upload_folder = get_profile_image_folder(id)
    
    data = load_data()
    profile_found = False

    for profile in data:
        if str(profile["profile"]['id']) == str(id):
            profile_found = True
            
            existing_pictures = profile.get('pictures', [])
            for old_pic in existing_pictures:
                try:
                    old_pic_path = os.path.join(upload_folder, old_pic)
                    if os.path.exists(old_pic_path):
                        os.remove(old_pic_path)
                except Exception as e:
                    print(f"Error removing old picture {old_pic}: {str(e)}")
            
            profile['pictures'] = []
            for file in files:
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    base, ext = os.path.splitext(filename)

                    counter = 1
                    while os.path.exists(os.path.join(upload_folder, filename)):
                        filename = f"{base}_{counter}{ext}"
                        counter += 1

                    file_path = os.path.join(upload_folder, filename)
                    file.save(file_path)
                    
                    profile['pictures'].append(filename)

            save_data(data)
            flash('Previous pictures removed and new pictures uploaded successfully', 'success')
            break

    if not profile_found:
        flash('Profile not found', 'error')

    return redirect(f'/profile/{id}')
@app.route('/image/<profile_id>/<filename>')
def serve_image(profile_id, filename):
    try:
        
        if filename.startswith('file:///'):
            filename = os.path.basename(filename)
            
        folder = get_profile_image_folder(profile_id)
        return send_file(
            os.path.join(folder, filename),
            mimetype='image/jpeg'
        )
    except Exception as e:
        print(f"Error serving image: {str(e)}")
        return 'Image not found', 404

@app.route('/profile/<id>/deletePicture', methods=['POST'])
def delete_picture(id):
    filename = request.form.get('filename')
    if not filename:
        flash('No picture specified', 'error')
        return redirect(f'/profile/{id}')

    if filename.startswith('file:///'):
        filename = os.path.basename(filename)

    data = load_data()
    for profile in data:
        if str(profile["profile"]['id']) == str(id):
            profile_pics = profile.get('pictures', [])
            pic_filenames = [os.path.basename(p) if p.startswith('file:///') else p for p in profile_pics]
            
            if filename in pic_filenames:
                idx = pic_filenames.index(filename)
                profile['pictures'].pop(idx)
                
                if 'used_pictures' in profile and filename in profile['used_pictures']:
                    profile['used_pictures'].remove(filename)
                
                used_path = os.path.join(get_profile_image_folder(id), 'used', filename)
                if os.path.exists(used_path):
                    try:
                        os.remove(used_path)
                    except Exception as e:
                        print(f"Error removing used picture: {str(e)}")
                
                save_data(data)
                flash('Picture deleted successfully', 'success')
            else:
                flash('Picture not found', 'error')
            break
    
    return redirect(f'/profile/{id}')

def migrate_picture_paths():
    data = load_data()
    for profile in data:
        profile_id = profile['profile']['id']
        if 'pictures' in profile:
            new_pictures = []
            for pic in profile['pictures']:
                if pic.startswith('file:///'):
                    
                    filename = os.path.basename(pic)
                    
                    old_path = pic[8:]  
                    new_path = os.path.join(get_profile_image_folder(profile_id), filename)
                    if os.path.exists(old_path) and not os.path.exists(new_path):
                        shutil.copy2(old_path, new_path)
                    new_pictures.append(filename)
                else:
                    new_pictures.append(pic)
            profile['pictures'] = new_pictures
    save_data(data)



def load_data():
    if os.path.exists('accounts.json'):
        with open('accounts.json', 'r') as file:
            return json.load(file)
    else:
        return {"proxies": [], "Accounts": [], "cities": []}
def remove_duplicates(data):
    for entry in data:
        
        entry["proxies"] = list(set(entry["proxies"]))

        
        seen_usernames = set()
        unique_accounts = []
        
        for account in entry.get("Accounts", []):
            if account["userName"] not in seen_usernames:
                seen_usernames.add(account["userName"])
                unique_accounts.append(account)
        
        entry["Accounts"] = unique_accounts

    return data

def save_data(data):
    data = remove_duplicates(data)
    with open('accounts.json', 'w') as file:
        json.dump(data, file, indent=4)
        return True
def save_data2(data):
    with open('accounts.json', 'w') as file:
        json.dump(data, file, indent=4)
        return True
@app.route('/')
def index():
    data = load_data()
    profiles = []
    for i in data :
        i['profile']['id'] = str(i['profile']['id'])
        profiles.append(i['profile'])
    return render_template('index.html',   profiles=profiles)
@app.route('/profile/<id>/delete', methods=['POST'])
def delete_profile(id):
    data = load_data()  
    profile_found = False

    
    for i, profile in enumerate(data):
        if str(profile["profile"]['id']) == str(id):
            profile_found = True
            del data[i]  
            save_data2(data)  
            flash(f"Profile '{profile['profile']['name']}' deleted successfully!", 'success')
            break

    if not profile_found:
        flash('Profile not found. Unable to delete.', 'error')

    return redirect('/')

@app.route('/newProfile', methods=['GET', 'POST'])
def newProfile():
    if flask.request.method == 'GET':
        data = load_data()
        profiles = []
        for i in data:
            i['profile']['id'] = str(i['profile']['id'])
            profiles.append(i['profile'])
        return render_template('addNewProfile.html', profiles=profiles)
        
    if flask.request.method == 'POST':
        form_data = request.form.to_dict()
        data = load_data()

        
        pictures = request.files.getlist('profilePictures')
        picture_paths = []
        if pictures:
            for picture in pictures:
                if picture and picture.filename:
                    filename = secure_filename(picture.filename)
                    picture_path = os.path.join('Pictures', filename)
                    picture.save(picture_path)
                    picture_paths.append(picture_path)

        
        def process_accounts(accounts_str):
            accounts = []
            for line in accounts_str.split('\n'):
                line = line.strip()
                if not line:
                    continue
                try:
                    parts = line.split(':')
                    if len(parts) >= 6:
                        accounts.append({
                            "userName": parts[0],
                            "active": True,
                            "auth": parts[1],
                            "token": parts[2]+":"+parts[3],
                            "deviceInfo": parts[4],
                            "userAgent": parts[5]
                        })
                except Exception as e:
                    print(f"Failed to process account line: {line}. Error: {str(e)}")
            return accounts

        def process_cities(cities_str):
            cities = []
            for line in cities_str.split('\n'):
                line = line.strip()
                if not line:
                    continue
                try:
                    parts = line.split(':')
                    if len(parts) >= 3:
                        cities.append({
                            "city": parts[0],
                            "lat": parts[1],
                            "long": parts[2]
                        })
                except Exception as e:
                    print(f"Failed to process city line: {line}. Error: {str(e)}")
            return cities

        def process_proxies(proxies_str):
            return [p.strip() for p in proxies_str.split('\n') if p.strip() and len(p.strip().split(':')) == 4]

        
        ValidAccounts = process_accounts(form_data.get('accounts', ''))
        ValidProxies = process_proxies(form_data.get('proxies', ''))
        formattedCities = process_cities(form_data.get('cities', ''))

        
        try:
            height_from = int(form_data.get('heightFrom', 140))
            height_to = int(form_data.get('heightTo', 220))
            height = random.randint(min(height_from, height_to), max(height_from, height_to))
        except:
            height = 170  

        
        api_settings = {
            
            "isAPI": True,
            "app": "grindr",
            "isOF": True,
            "brand": "cupidbotofm",
            "product": "ofm-grindr",
            "isFemale": True,
            "platformSource": "grindr",
            "chooseRandomCTA": True,
            "defaultSettings": True,
            "aiAugmentation": True,
            "mediaRate": 1,
            "mediaPools": "sexy",
            "messagingFromAnotherAccountDelay": 4,
            "isFollowUp": True,
            
            
            "accessToken": form_data.get('accessToken', ''),
            "version": form_data.get('version', ''),
            "manifestVersion": form_data.get('manifestVersion', ''),
            "creator_id": form_data.get('creator_id', ''),
            "preset_id": form_data.get('preset_id', ''),
            "chatStyle": form_data.get('chatStyle', 'youth'),
            "userInfo": form_data.get('userInfo', ''),
            "settingDayInfo": form_data.get('settingDayInfo', ''),
            "settingNightInfo": form_data.get('settingNightInfo', ''),
            "ctaInfo": form_data.get('ctaInfo', ''),
            
            
            "spintax": form_data.get('spintax', ''),
            "followUpSpintax": form_data.get('followUpSpintax', ''),
            "followUpAfterCTA": form_data.get('followUpAfterCTA', ''),
            "ctaScript": form_data.get('ctaScript', ''),
            "objectionHandling": form_data.get('objectionHandling', ''),
            
            
            "enableSequence": form_data.get('enableSequence') == 'on',
            "responseLanguage": form_data.get('responseLanguage', 'English'),
            "responseLanguageCode": form_data.get('responseLanguageCode', 'en'),
            "typoRate": form_data.get('typoRate', 0)
        }

        
        new_profile = {
            "profile": {
                "id": str(len(data) + 1),
                "name": form_data.get('profileName', f'Profile {len(data) + 1}')
            },
            "displayName": form_data.get('displayName', ''),
            "aboutMe": form_data.get('aboutMe', ''),
            "age": int(form_data.get('age', 18)),
            "height": height,
            "lookingFor": form_data.get('lookingFor', ''),
            "meetAt": form_data.get('meetAt', ''),
            "acceptNSFWPics": form_data.get('acceptNSFWPics', ''),
            "pictures": picture_paths,
            "Accounts": ValidAccounts,
            "proxies": ValidProxies,
            "cities": formattedCities,
            "enabled": False,
            "chatMode": form_data.get('chatMode', 'bot'),
            "apiSettings": api_settings
        }

        
        if form_data.get('chatMode') == 'gpt':
            new_profile["gptSettings"] = {
                "primaryApiKey": form_data.get('openaiKey1', ''),
                "secondaryApiKey": form_data.get('openaiKey2', ''),
                "framework": form_data.get('gptFramework', ''),
                "handles": {
                    "handle1": [h.strip() for h in form_data.get('handle1', '').split('\n') if h.strip()],
                    "handle2": [h.strip() for h in form_data.get('handle2', '').split('\n') if h.strip()]
                }
            }

        data.append(new_profile)
        save_data2(data)
        return redirect("/")
@app.route('/profile/<id>')
def accounts(id):
    manager = ProfileDataManager()
    profile = manager.get_profile_by_id(id)
    if not profile:
        flash('Profile not found', 'error')
        return redirect('/')
    
    chat_settings = chat_settings_manager.get_chat_settings(id)
    pic = []
    prx = []
    for proxy in profile.get('proxies', []):
        prx.append(proxy)
        if(len(prx) >100):
            break
    for p in profile.get("pictures", []) :
        pic.append(f'file:///{os.getcwd()}/images/{p}'.replace("\\", '/'))
    return render_template('accounts.html',
                         proxies=prx,
                         profileStatus=(profile.get("enabled") == True),
                         cta=chat_settings,
                         profile=profile,  
                         accounts=profile.get("Accounts", []),
                         cities=profile.get("cities", []),
                         pictures=pic,
                         profile_id=str(id))



@app.route('/profile/<id>/update_profile_form', methods=['POST'])
def update_profile_form(id):
    try:
        data = load_data()
        profile_updated = False
        
        for p in data:
            if str(p["profile"]["id"]) == str(id):
                
                p.update({
                    'displayName': request.form.get('displayName', ''),
                    'aboutMe': request.form.get('aboutMe', ''),
                    'age': int(request.form.get('age', 18)),
                    'heightFrom': int(request.form.get('heightFrom', 140)),
                    'heightTo': int(request.form.get('heightTo', 220)),
                    'lookingFor': request.form.getlist('lookingFor'),
                    'meetAt': request.form.getlist('meetAt'),
                    'acceptNSFWPics': request.form.get('acceptNSFWPics', '0')
                })
                profile_updated = True
                break
        
        if profile_updated:
            save_data2(data)
            flash('Profile updated successfully!', 'success')
        else:
            flash('Profile not found', 'error')
            
        return redirect(f'/profile/{id}')
        
    except Exception as e:
        flash(f'Error updating profile: {str(e)}', 'error')
        return redirect(f'/profile/{id}')

@app.route('/profile/<id>/saveAccountsData', methods=['GET'])
def update_profile_data(id):
    try:
        data = load_data()
        profile_updated = False
        
        for p in data:
            
            if str(p["profile"]["id"]) == str(id):
                data = p
                break
        
        for acc in data.get("Accounts"):
                    Thread(target=editProfile , args=(acc["grindrToken"] , acc["deviceInfo"] , acc["userAgent"] , p.get("displayName") , 
                                p.get("aboutMe") , p.get("age") , p.get("heightFrom") , p.get("heightTo") ,
                                p.get("lookingFor") , p.get("meetAt") , p.get("acceptNSFWPics") , acc)).start()
        profile_updated = True
                
        if profile_updated:
            
            flash('Profile Updating started!', 'success')
        else:
            flash('Profile not found', 'error')
            
        return redirect(f'/profile/{id}')
        
    except Exception as e:
        flash(f'Error updating profile: {str(e)}', 'error')
        return redirect(f'/profile/{id}')


@app.route('/profile/<id>/disable', methods=['GET'])
def disableProfile(id): 
    data = load_data()
    for d in data:
        if str(d["profile"]['id']) == str(id):
            d["enabled"] = False
            save_data2(data)          

    return redirect("/profile/"+id)


@app.route('/profile/<id>/enable', methods=['GET'])
def enableProfile(id): 
    data = load_data()
    for d in data:
        if str(d["profile"]['id']) == str(id):
            d["enabled"] = True
            save_data2(data)          
    return redirect("/profile/"+id)

@app.route('/profile/<id>/save-chat-setting', methods=['POST'])
def saveChatSetting(id):
    try:
        print(f"Received save-chat-setting request for profile {id}")
        form_data = request.form.to_dict()
        data = load_data()
        profile_found = False
        for i, profile in enumerate(data):
            if str(profile["profile"]['id']) == str(id):
                profile_found = True
                chat_mode = form_data.get('chatMode', 'bot')
                
                
                updated_profile = {
                    'profile': profile['profile'],
                    'Accounts': profile['Accounts'],
                    'proxies': profile['proxies'],
                    'cities': profile['cities'],
                    'enabled': profile.get('enabled', False),
                    'chatMode': chat_mode,  
                    'apiSettings': {
                        'accessToken': form_data.get('accessToken'),
                        "AccountID":form_data.get("AccountID"),
                        'version': form_data.get('version'),
                        'manifestVersion': form_data.get('manifestVersion'),
                        'isAPI': True,
                        'app': "grindr",
                        'isOF': True,
                        'brand': "cupidbotofm",
                        'product': "ofm-grindr",
                        'isFemale': True,
                        'platformSource': "grindr",
                        'creator_id': form_data.get('creator_id'),
                        'preset_id': form_data.get('preset_id'),
                        'name': form_data.get('name'),
                        'age': form_data.get('age'),
                        'typo_rate' : form_data.get('typoRate'),
                        'userInfo': form_data.get('userInfo'),
                        'chatStyle': form_data.get('chatStyle'),
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
                        'responseLanguageCode': {
                            'English': 'en',
                            'French': 'fr',
                            'Spanish': 'es'
                        }.get(form_data.get('responseLanguage', 'English'), 'en')
                    }
                }

                if chat_mode == 'gpt':
                    updated_profile['gptSettings'] = {
                        'primaryApiKey': form_data.get('openaiKey1'),
                        'secondaryApiKey': form_data.get('openaiKey2'),
                        'framework': form_data.get('gptFramework'),
                        'handles': {
                            'handle1': [h.strip() for h in form_data.get('handle1', '').split('\n') if h.strip()],
                            'handle2': [h.strip() for h in form_data.get('handle2', '').split('\n') if h.strip()]
                        }
                    }
                else:
                    updated_profile['gptSettings'] = None

                
                data[i] = updated_profile
                
                
                print("Saving updated profile")
                save_data2(data)
                flash('Chat settings saved successfully!', 'success')
                break
        if not profile_found:
            flash('Profile not found!', 'error')
        return redirect(f'/profile/{id}')
    except Exception as e:
        print(f"Error saving chat settings: {str(e)}")
        flash(f'Error saving chat settings: {str(e)}', 'error')
        return redirect(f'/profile/{id}')

@app.route('/profile/<id>/name', methods=['POST'])
def profileName(id): 
    data = load_data()
    name = request.form.get("name")
    for d in data:
        if str(d["profile"]['id']) == str(id):
            d["profile"]["name"] = name
            save_data2(data)         
            return redirect("/profile/"+id)
    return redirect("/profile/"+id)
def get_files_in_folder(id):
    folder_path = os.path.join(os.getcwd(), "images", id)
    files = glob.glob(os.path.join(folder_path, "*"))  
    return files
def ensure_used_pictures_field(data):
    """Ensure each profile has a used_pictures field"""
    for profile in data:
        if 'used_pictures' not in profile:
            profile['used_pictures'] = []
    return data

def cleanup_used_folder(id, used_pictures):
    """Remove pictures from used folder that are no longer in used_pictures list"""
    used_dir = f"images/{id}/used"
    if os.path.exists(used_dir):
        for file in os.listdir(used_dir):
            if file not in used_pictures:
                try:
                    os.remove(os.path.join(used_dir, file))
                except Exception as e:
                    print(f"Error removing file {file}: {str(e)}")

def update_used_pictures_tracking(id, selected_pics):
    """Update the used_pictures tracking in accounts.json"""
    data = load_data()
    for profile in data:
        if str(profile["profile"]['id']) == str(id):
            if 'used_pictures' not in profile:
                profile['used_pictures'] = []
            profile['used_pictures'].extend(selected_pics)
            profile['used_pictures'] = list(set(profile['used_pictures'])) 
            save_data(data)
            break

@app.route("/profile/<id>/updatePictures", methods=['GET'])
def updateProfilePictures(id):
    data = load_data()
    profile = None
    
    for d in data:
        if str(d["profile"]['id']) == str(id):
            profile = d
            try:
                pic_count = int(d.get("picturesCount", 3))
            except (ValueError, TypeError):
                pic_count = 3
            break
    
    if not profile or not profile.get("pictures"):
        flash('No profile found or no pictures available', 'error')
        return redirect(f"/profile/{id}")

    if 'used_pictures' not in profile:
        profile['used_pictures'] = []

    available_pics = [pic for pic in profile["pictures"] if pic not in profile['used_pictures']]

    if len(available_pics) < pic_count:
        profile['used_pictures'] = []  
        available_pics = profile["pictures"]
        used_dir = f"images/{id}/used"
        if os.path.exists(used_dir):
            shutil.rmtree(used_dir)  
        os.makedirs(used_dir, exist_ok=True)
        flash('All pictures have been used, resetting used pictures tracking', 'info')

    try:
        selected_pics = random.sample(available_pics, k=pic_count)
        
        paths = []
        for pic in selected_pics:
            src_path = f"images/{id}/{pic}"
            dst_path = f"images/{id}/used/{pic}"
            
            if os.path.exists(src_path):
                shutil.copy2(src_path, dst_path)
                paths.append(src_path)
                
                update_used_pictures_tracking(id, [pic])
            else:
                flash(f'Warning: Picture {pic} not found', 'warning')

        if paths:
            for account in profile.get("accounts", []):
                Thread(
                    target=updateAccountPictures,
                    args=(
                        paths,
                        account.get("grindrToken"),
                        account.get("deviceInfo"),
                        account.get("userAgent"),
                        profile.get("proxies")
                    )
                ).start()
            flash('Pictures are updating in threads', 'success')
        else:
            flash('No valid pictures found to update', 'error')

    except Exception as e:
        flash(f'Error updating pictures: {str(e)}', 'error')
        
    return redirect(f"/profile/{id}")


def test_proxy(proxy: str) -> Tuple[str, bool]:
    
    try:
        proxies = {
            'http': proxy,
            'https': proxy
        }
        
        
        response = requests.get(
            'http://example.com',
            proxies=proxies,
            timeout=3,  
            verify=False
        )
        return proxy, response.status_code == 200
    except Exception as e:
        print(f"Proxy {proxy} failed: {str(e)}")
        return proxy, False

def validate_proxies(proxies: List[str], max_workers: int = 5) -> Tuple[List[str], List[str]]:
    
    working = []
    failed = []
    
    
    proxies = [p.strip() for p in proxies if p.strip()]
    
    
    if len(proxies) <= 3:
        for proxy in proxies:
            _, is_working = test_proxy(proxy)
            if is_working:
                working.append(proxy)
            else:
                failed.append(proxy)
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_proxy = {executor.submit(test_proxy, proxy): proxy for proxy in proxies}
            for future in as_completed(future_to_proxy):
                proxy, is_working = future.result()
                if is_working:
                    working.append(proxy)
                else:
                    failed.append(proxy)
                
    return working, failed


@app.route('/profile/<id>/validateProxies', methods=['POST'])
def validate_profile_proxies(id):
    
    try:
        data = load_data()
        for profile in data:
            if str(profile["profile"]['id']) == str(id):
                if not profile['proxies']:
                    flash('No proxies to validate!', 'warning')
                    return redirect(f"/profile/{id}")
                
                
                working_proxies, failed_proxies = validate_proxies(profile['proxies'])
                
                
                profile['proxies'] = working_proxies
                save_data(data)
                
                
                if failed_proxies:
                    flash(f'Removed {len(failed_proxies)} non-working proxies. {len(working_proxies)} proxies remaining.', 'success')
                else:
                    flash('All proxies are working!', 'success')
                break
                
        return redirect(f"/profile/{id}")
        
    except Exception as e:
        flash(f'Error validating proxies: {str(e)}', 'error')
        return redirect(f"/profile/{id}")

@app.route('/profile/<id>/addProxy', methods=['POST'])
def add_proxy(id):
    new_proxy = request.form.get('proxy')
    
    if not new_proxy:
        flash('Proxy cannot be empty!', 'error')
        return redirect("/profile/"+id)
    
    data = load_data()
    profile_found = False  

    for d in data:
        if str(d["profile"]['id']) == str(id):
            profile_found = True  
            if new_proxy in d['proxies']:
                flash('This proxy already exists!', 'error')
            else:
                d['proxies'].append(new_proxy)
                save_data(data)
                flash('Proxy added successfully!', 'success')
            break  

    if not profile_found:
        flash('Profile not found!', 'error')  

    return redirect("/profile/"+id)

@app.route('/profile/<id>/deleteProxy/<int:proxy_index>', methods=['POST'])
def delete_proxy(id, proxy_index):
    data = load_data()
    
    try:
        
        deleted_proxy = None
        profile_to_update = None
        
        for profile in data:
            if str(profile.get("profile", {}).get("id")) == str(id):
                deleted_proxy = profile['proxies'].pop(proxy_index)
                profile_to_update = profile
                break
        
        if deleted_proxy is None:
            flash('Profile not found!', 'error')
            return redirect(f"/profile/{id}")
        
        
        if profile_to_update and 'pictures' in profile_to_update:
            
            os.makedirs('used_Pictures', exist_ok=True)
            
            for picture_path in profile_to_update.get('pictures', []):
                try:
                    if picture_path and os.path.exists(picture_path):
                        used_picture_path = os.path.join('used_Pictures', os.path.basename(picture_path))
                        shutil.move(picture_path, used_picture_path)
                except Exception as pic_error:
                    print(f"Error moving picture {picture_path}: {str(pic_error)}")
        
        
        save_data(data)
        flash(f'Proxy {deleted_proxy} deleted successfully!', 'success')
        
    except IndexError:
        flash('Failed to delete proxy, index out of range.', 'error')
    except Exception as e:
        flash(f'An error occurred: {str(e)}', 'error')
        print(f"Error in delete_proxy: {str(e)}")  
    
    return redirect(f"/profile/{id}")

@app.route('/profile/<id>/editProxy/<int:proxy_index>', methods=['POST'])
def edit_proxy(id, proxy_index):
    new_proxy_value = request.form.get('proxy')
    data = load_data()
    deleted_proxy = None
    for i in data:
            if(str(i["profile"]['id']) == str(id)):
                if proxy_index < len(i['proxies']):
                    i['proxies'][proxy_index] = new_proxy_value
                    deleted_proxy = save_data(data)
                    flash('Proxy updated successfully!', 'success')
                else:
                    flash('Invalid proxy index', 'error')
    
    if delete_proxy == None:
        flash('Profile not found!', 'error')
        return redirect("/profile/"+id)
    return redirect("/profile/"+id)

@app.route('/profile/<id>/proxies', methods=['POST'])
def bulkImportProxy(id):
    form_data = request.form.to_dict()
    proxies = form_data["proxies"].replace('\r','').split('\n')    
    data = load_data()
    for i in data:
            if(str(i["profile"]['id']) == str(id)):
                    i['proxies'] = i['proxies'] + proxies
    flash('Proxy updated successfully!', 'success')
    save_data(data)
    return redirect("/profile/"+id)

@app.route('/profile/<id>/accounts', methods=['POST'])
def bulkImportAccount(id):
    form_data = request.form.to_dict()
    raw_accounts = form_data.get("accounts", "").replace('\r', '').split('\n')
    accounts = []
    
    for acc in raw_accounts:
        parts = acc.split(":")
        if len(parts) == 6:
            account = {
                "userName": parts[0],
                "auth": parts[1],
                "token": parts[2]+":"+parts[3],
                "deviceInfo": parts[4],
                "userAgent": parts[5]
            }
            accounts.append(account)
        else:
            
            continue
    
    data = load_data()
    for profile in data:
        if str(profile["profile"]['id']) == str(id):
            
            existing_accounts = {acc["userName"]: acc for acc in profile['Accounts']}
            
            for new_acc in accounts:
                existing_accounts[new_acc["userName"]] = new_acc
            
            profile['Accounts'] = list(existing_accounts.values())
            break

    flash('Proxy updated successfully!', 'success')
    save_data(data)
    return redirect(f"/profile/{id}")


@app.route('/profile/<id>/addAccount', methods=['POST'])
def add_account(id ):
    
    username = request.form.get('username')
    auth_token = request.form.get('authToken')
    device_token = request.form.get('token')
    device_info = request.form.get('deviceInfo')
    user_agent = request.form.get('userAgent')
    city_name = request.form.get('city')
    data = load_data()
    for profile in data:
        if str(profile["profile"]['id']) == str(id):
            selected_city = next((city for city in profile['cities'] if city['city'] == city_name), None)
            if selected_city:
                lat = selected_city['lat']
                long = selected_city['long']
            else:
                lat = ""
                long = ""

            if not (username and auth_token and device_token and device_info and user_agent  ):
                flash('All fields must be filled out to add an account!', 'error')
                return redirect(f'/profile/{id}')
            if any(account['userName'] == username for account in profile['Accounts']):
                flash('An account with this username already exists!', 'error')
            else:
                new_account = {
                    "userName": username,
                    "auth": auth_token,
                    "token": device_token,
                    "deviceInfo": device_info,
                    "userAgent": user_agent,
                    "city": city_name,
                    "lat": lat,
                    "long": long,
                    "banStatus": "False",
                    "profileId": None,
                    "name": None,
                    "active": True ,
                }
                profile['Accounts'].append(new_account)
                save_data(data)
                flash('Account added successfully!', 'success')

            return redirect(f'/profile/{id}')

@app.route('/profile/<id>/deactivateAccount/<int:account_index>', methods=['POST'])
def deactivate_account(id , account_index):
    data = load_data()
    for profile in data:
        if str(profile["profile"]['id']) == str(id):
            try:
                profile['Accounts'][account_index]['active'] = False
                save_data(data)
                flash(f"Account {profile['Accounts'][account_index]['userName']} deactivated successfully!", 'success')
            except IndexError:
                flash('Failed to deactivate account, index out of range.', 'error')

    
    return redirect("/profile/"+id)

@app.route('/profile/<id>/activateAccount/<int:account_index>', methods=['POST'])
def activate_account(id , account_index):
    data = load_data()
    for profile in data:
        if str(profile["profile"]['id']) == str(id):
            try:
                profile['Accounts'][account_index]['active'] = True
                save_data(data)
                flash(f"Account {profile['Accounts'][account_index]['userName']} deactivated successfully!", 'success')
            except IndexError:
                flash('Failed to deactivate account, index out of range.', 'error')
    return redirect("/profile/"+id)




@app.route('/profile/<id>/editAccount/<int:account_index>', methods=['GET'])
def show_edit_account(account_index, id ):
    data = load_data()
    for profile in data:
        if str(profile["profile"]['id']) == str(id):
            if account_index >= len(profile['Accounts']):
                flash('Invalid account index', 'error')
                return redirect(url_for('index'))
            account = profile['Accounts'][account_index]
            cities = profile.get('cities', [])
            return render_template('edit_account.html', account=account, profile_id=id,account_index=account_index, cities=cities)
@app.route('/profile/<id>/editAccount/<int:account_index>', methods=['POST'])
def edit_account(account_index, id):
    data = load_data()

    for profile in data:
        if str(profile["profile"]['id']) == str(id):
            if account_index >= len(profile['Accounts']):
                flash('Invalid account index', 'error')
                return redirect(url_for('index'))
            account = profile['Accounts'][account_index]
            account['userName'] = request.form.get('username') or account['userName']
            account['auth'] = request.form.get('authToken') or account['auth']
            account['token'] = request.form.get('token') or account['token']
            account['deviceInfo'] = request.form.get('deviceInfo') or account['deviceInfo']
            account['userAgent'] = request.form.get('userAgent') or account['userAgent']
            city_name = request.form.get('city') or account.get('city', '')
            selected_city = next((city for city in profile.get('cities', []) if city['city'] == city_name), None)
            if selected_city:
                account['city'] = city_name
                account['lat'] = selected_city['lat']
                account['long'] = selected_city['long']            
            account['bio'] = request.form.get('bio') or account.get('bio', '')
            if account['bio']:
                lg = Login(account['userName'], account['auth'], account['token'], account['deviceInfo'], account['userAgent'])
                if lg.get('sessionId'):
                    editBio(f"Grindr3 {lg['sessionId']}", account['deviceInfo'], account['userAgent'], account['bio'])
                else:
                    flash('Failed to update bio, session ID not found.', 'error')
            
            save_data(data)
            flash(f"Account {account['userName']} updated successfully!", 'success')
            return redirect("/profile/" + id)
    
    flash('Profile not found', 'error')
    return redirect(url_for('index'))

@app.route('/profile/<id>/deleteAccount/<int:account_index>', methods=['POST'])
def delete_account(id, account_index):
    data = load_data()
    profile_found = False
    for profile in data:
        if str(profile["profile"]['id']) == str(id):
            profile_found = True
            if 0 <= account_index < len(profile['Accounts']):
                deleted_account = profile['Accounts'].pop(account_index)
                save_data(data)
                flash(f"Account {deleted_account['userName']} deleted successfully!", 'success')
            else:
                flash('Failed to delete account, index out of range.', 'error')
            return redirect(f"/profile/{id}")
    if not profile_found:
        flash(f'Profile with ID {id} not found.', 'error')
    return  redirect("/")
@app.route('/profile/<id>/addCity', methods=['POST'])
def add_city(id):
    city_name = request.form.get('city')
    lat = request.form.get('lat')
    long = request.form.get('long')

    if not (city_name and lat and long):
        flash('All fields must be filled out to add a city!', 'error')
        redirect("/profile/"+id)

    data = load_data()
    for profile in data:
        if str(profile["profile"]['id']) == str(id):
            if any(city['city'] == city_name for city in profile['cities']):
                flash('A city with this name already exists!', 'error')
            else:
                new_city = {
                    "city": city_name,
                    "lat": lat,
                    "long": long
                }
                profile['cities'].append(new_city)
                save_data2(data)
                flash('City added successfully!', 'success')
    return  redirect("/profile/"+id)

@app.route('/profile/<id>/deleteCity/<int:city_index>', methods=['POST'])
def delete_city(id ,city_index):
    data = load_data()
    for profile in data:
        if str(profile["profile"]['id']) == str(id):
            try:
                deleted_city = profile['cities'].pop(city_index)
                save_data(data)
                flash(f'City {deleted_city["city"]} deleted successfully!', 'success')
            except IndexError:
                flash('Failed to delete city, index out of range.', 'error')

    return redirect("/profile/"+id)

@app.route('/profile/<id>/cities', methods=['POST'])
def bulkImportCities(id):
    form_data = request.form.to_dict()
    cities = form_data["cities"].replace('\r','').split('\n')    
    data = load_data()
    for i in data:
            if( not i.get("cities")):
                i["cities"] = []
            if(str(i["profile"]['id']) == str(id)):
                    for city in cities :
                        try :
                            city = city.split(":")
                            cityName = city[0]
                            lat = city[1]
                            long = city[2]
                            i["cities"].append({
                                "city":cityName,
                                "lat":lat,
                                "long":long
                                })
                        except:
                            pass                
    flash('List  updated successfully!', 'success')
    save_data(data)
    return redirect("/profile/"+id)
def assign_cities_to_accounts(profiles):
    for profile in profiles:
        used_cities = {acc.get("city") for acc in profile["Accounts"] if "city" in acc}
        
        available_cities = [city for city in profile["cities"] if city["city"] not in used_cities]
        
        for account in profile["Accounts"]:
            if "city" not in account and available_cities:
                city_to_assign = available_cities.pop(0) 
                account["city"] = city_to_assign["city"]
                account["lat"] = city_to_assign["lat"]
                account["long"] = city_to_assign["long"]
                print(f"Assigned city {city_to_assign['city']} to account {account['userName']}")
            elif not available_cities:
                print(f"No available cities left to assign for account {account['userName']} in profile {profile['profile']['name']}")
    return profiles
def run_flask_app():
    app.run(port=5000 )

if __name__ == '__main__':  
    try:
        if (len(json.loads(open("accounts.json","r").read())) == 0):
            open("accounts.json","w").write(json.dumps([]))
    except:
        open("accounts.json","w").write(json.dumps([]))
                        
    flask_process = multiprocessing.Process(target=run_flask_app)
    bot_process = multiprocessing.Process(target=main)
    bot_process.start()
    flask_process.start()
    while(True):
        save_data2(assign_cities_to_accounts(json.loads(open("accounts.json","r").read())))
        time.sleep(10)