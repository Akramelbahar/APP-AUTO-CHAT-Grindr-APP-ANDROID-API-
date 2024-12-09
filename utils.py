import time
import datetime
import base64
import random
import string
import random
import uuid

def random_string(length=10):
    """Generate a random alphanumeric string of a given length."""
    chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    return ''.join(random.choice(chars) for _ in range(length))
import uuid

def generate_log_token():
    # Generate a random UUID and prepend 'anon-' and append ';*;*;*;*;*'
    token = f"anon-{uuid.uuid4()};*;*;*;*;*"
    return token
def generate_timestamp():
    time.sleep(0.5)
    return int(time.time() * 1000)

def generate_token():
    # Randomize device ID (a random alphanumeric string)
    device_id = random_string(12)
    
    # Randomize app configuration (a random alphanumeric string)
    app_configuration = random_string(15)
    
    # Randomize CPU architecture (1 for x86, 2 for other architectures)
    cpu_arch = random.choice([1, 2])
    
    # Randomize total memory (in bytes) - using a random range for typical device memory (e.g., 2GB to 32GB)
    memory_info = random.randint(2 * 1024**3, 32 * 1024**3)  # Random memory between 2GB and 32GB
    
    # Randomize screen resolution (choosing random values for width and height)
    width = random.randint(720, 2560)  # Common screen widths (HD to QHD)
    height = random.randint(1280, 3840)  # Common screen heights (HD to UHD)
    resolution_str = f"{height}x{width}"
    
    # Generate a random advertising ID using UUID
    advertising_id = uuid.uuid4()
    
    # Construct the token (using semicolon-separated values)
    token = f"{device_id};{app_configuration};{cpu_arch};{memory_info};{resolution_str};{advertising_id}"
    
    return {'token':token,'deviceId':device_id}

def generate_random_string(length):
    # Generate a random string with alphanumeric characters
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def date_to_timestamp(year, month, day):
    # Create a datetime object for the given date
    dt = datetime.datetime(year, month, day)
    # Convert the datetime object to a timestamp (seconds since epoch)
    timestamp = int(time.mktime(dt.timetuple()))
    return timestamp

