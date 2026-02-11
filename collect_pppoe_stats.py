import os
from dotenv import load_dotenv
import sqlite3
from netmiko import ConnectHandler
import time
import threading
import re
from datetime import datetime
import logging
from threading import Lock

# Global state for connection pooling
CONNECTION_LOCK = Lock()
router_connections = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("paramiko").setLevel(logging.WARNING)
logging.getLogger("netmiko").setLevel(logging.WARNING)

load_dotenv()

def get_db():
    db_dir = "/opt/online/db"
    os.makedirs(db_dir, exist_ok=True)
    db_path = os.path.join(db_dir, "subscribers.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            router TEXT,
            username TEXT UNIQUE,
            interface TEXT,
            framed_ip TEXT,
            mac_address TEXT,
            download_speed TEXT,
            upload_speed TEXT,
            up_time TEXT
        )
    """)
    conn.commit()
    return conn

def get_router_connection(router_info):
    with CONNECTION_LOCK:
        if router_info['router'] not in router_connections:
            try:
                net_connect = ConnectHandler(
                    ip=router_info['router'],
                    username=router_info['username'],
                    password=router_info['password'],
                    device_type=router_info['device_type'],
                    timeout=60,
                    fast_cli=False
                )
                net_connect.send_command("terminal length 0")
                router_connections[router_info['router']] = net_connect
            except Exception as e:
                logger.error(f"Failed to establish connection for {router_info['router']}: {e}")
                return None
        else:
            try:
                router_connections[router_info['router']].is_alive()
            except Exception:
                del router_connections[router_info['router']]
                return get_router_connection(router_info) 
    return router_connections[router_info['router']]

def collect_data():
    logger.info("=== STARTING DATA COLLECTION ===")
    
    routers = []
    env_prefix = "ROUTER_"
    for i in range(1, 100):
        key = f"{env_prefix}{i}_ROUTER"
        if key not in os.environ:
            break
        router = os.getenv(key)
        username = os.getenv(f"{env_prefix}{i}_USERNAME")
        password = os.getenv(f"{env_prefix}{i}_PASSWORD")
        device_type = os.getenv(f"{env_prefix}{i}_DEVICE_TYPE", "cisco_ios")
        if router and username and password:
            routers.append({
                'router': router,
                'username': username,
                'password': password,
                'device_type': device_type
            })

    db_conn = get_db()
    cursor = db_conn.cursor()

    for router_info in routers:
        net_connect = get_router_connection(router_info)
        if not net_connect:
            continue

        try:
            logger.info(f"=== PROCESSING ROUTER: {router_info['router']} ===")
            
            # STEP 1: Map interface -> IP
            output_users = net_connect.send_command("show users")
            interface_to_ip = {}
            user_pattern = r"^(Vi\S+)\s+.*?\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
            for line in output_users.splitlines():
                match = re.search(user_pattern, line.strip())
                if match:
                    iface, ip = match.groups()
                    interface_to_ip[iface] = ip

            logger.info(f" Mapped {len(interface_to_ip)} IP addresses.")

            # STEP 2: Map interface -> MAC
            output_pppoe = net_connect.send_command("show pppoe session")
            interface_to_mac = {}
            pppoe_pattern = r"\d+\s+\d+\s+([0-9a-fA-F\.]+)\s+\S+\s+\d+\s+(Vi\S+)"
            for line in output_pppoe.splitlines():
                match = re.search(pppoe_pattern, line.strip())
                if match:
                    mac, iface = match.groups()
                    interface_to_mac[iface] = mac
                    
            logger.info(f" Mapped {len(interface_to_mac)} MAC addresses.")

            # STEP 3: Map Uniq ID -> SSS session identifier
            output_qos = net_connect.send_command("show policy-map session | i SSS|Service-policy")
            qos_map = {}
            current_id = None
            
            for line in output_qos.splitlines():
                # Find the Uniq ID
                id_match = re.search(r"SSS session identifier (\d+)", line)
                if id_match:
                    current_id = id_match.group(1)
                    if current_id not in qos_map:
                        qos_map[current_id] = {'up': 'N/A', 'down': 'N/A'}
                
                # Find input (Upload)
                input_match = re.search(r"Service-policy input:\s+(\S+)", line)
                if input_match and current_id:
                    qos_map[current_id]['up'] = input_match.group(1)
                
                # Find output (Download)
                output_match = re.search(r"Service-policy output:\s+(\S+)", line)
                if output_match and current_id:
                    qos_map[current_id]['down'] = output_match.group(1)

            # STEP 4: Process subscriber sessions
            output_subscriber = net_connect.send_command("show subscriber session")
            lines = output_subscriber.splitlines()
            
            # Capture Uniq ID
            sub_pattern = r"^(\d+)\s+(Vi\S+)\s+\S+\s+\S+\s+(\S+)\s+\d+"

            count_updated = 0
            for i, line in enumerate(lines):
                match = re.search(sub_pattern, line.strip())
                if match:
                    uniq_id = match.group(1)
                    interface = match.group(2)
                    up_time = match.group(3)
                    
                    # Extract username
                    remainder = line[match.end():].strip()
                    username = None
                    if remainder:
                        username = remainder
                    elif i + 1 < len(lines):
                        next_line = lines[i+1].strip()
                        if not re.match(r"^\d+\s+Vi", next_line): 
                            username = next_line
                    if username:
                        username = username.split()[0] 

                    if not username:
                        continue

                    # Data join
                    framed_ip = interface_to_ip.get(interface, "N/A")
                    mac_address = interface_to_mac.get(interface, "N/A")
                    
                    # Fetch QoS from the map using the captured Uniq ID
                    speeds = qos_map.get(uniq_id, {'up': 'N/A', 'down': 'N/A'})
                    upload = speeds['up']
                    download = speeds['down']

                    if framed_ip == "N/A" and mac_address == "N/A":
                        continue

                    cursor.execute("""
                        REPLACE INTO subscribers
                        (timestamp, router, username, interface, framed_ip, mac_address, download_speed, upload_speed, up_time)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        router_info['router'],
                        username,
                        interface,
                        framed_ip,
                        mac_address,
                        download,
                        upload,
                        up_time
                    ))
                    count_updated += 1
            
            db_conn.commit()
            logger.info(f" Updated {count_updated} subscribers for {router_info['router']}")

        except Exception as e:
            logger.error(f" Error processing router {router_info['router']}: {e}")
        finally:
            if net_connect in router_connections.values():
                try:
                    net_connect.disconnect()
                    with CONNECTION_LOCK:
                        del router_connections[router_info['router']]
                        logger.info(f" === FINISHED PROCESSING ROUTER: {router_info['router']}")
                except Exception:
                    pass

    db_conn.close()

def run_scheduler():
    def collect_data_wrapper():
        collect_data()
        threading.Timer(300, collect_data_wrapper).start()
    collect_data_wrapper()

scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
scheduler_thread.start()

if __name__ == "__main__":
    while True:
        time.sleep(1)
