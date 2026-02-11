# pppoe-dashboard

A lightweight dashboard designed to visualize connected subscribers (L2TP, PPPoE, and PPPoE over L2TP) for network environments where RADIUS API access is unavailable.

## Background
I work with network gear daily rather than writing code, I built this tool to bridge a gap: our backend billing system changed to a RADIUS setup without API access. This dashboard allows for visibility into subscriber connectivity with a 5 minute delay.

Currently, this is tested and running on **2x Cisco ASR1001-X** routers, handling approximately **5,000 subscribers**. A full data collection run typically completes in under **30 seconds**.

I thought there may be a use for this for other people in a similar situation, so here it is.

### Future Goals
- Extend support to other BNGs (specifically Mikrotik for smaller ISP environments).

---

## Quick and Dirty Setup

### 1. Install Dependencies
This project uses SQLite for data storage.
```bash
sudo apt update && sudo apt install sqlite3
````

### 2. Configure Apache

Add the following configuration to your site config (e.g., /etc/apache2/sites-enabled/000-default.conf):
```bash
Alias /online "/opt/online/app" 
DocumentRoot /opt/online/app

<Directory "/opt/online/app">
    Options Indexes FollowSymLinks
    AllowOverride None
    Require all granted
</Directory>

# Route requests to `/api/` to Gunicorn
<Location /api/>
    ProxyPreserveHost On
    ProxyPass http://127.0.0.1:5000/api/
    ProxyPassReverse http://127.0.0.1:5000/api/
</Location>
````
Now enable proxy module and restart apache
````bash
sudo a2enmod proxy proxy_http
````
### 3. Setup your app location and install python modules, I use /opt/online
```bash
cd /opt/online
python3 -m venv /opt/online/venv
source venv/bin/activate
pip3 install --upgrade pip
pip3 install -r requirements.txt
````

### 4. Edit the .env file with your router dns name/ip and login details

Now start the collector it should show some output like so:
```bash
python3 collect_pppoe_stats.py
````

```bash
#INFO:__main__:=== STARTING DATA COLLECTION ===
#INFO:__main__:=== PROCESSING ROUTER: ter-bng1 ===
#INFO:__main__: Mapped 3319 IP addresses.
#INFO:__main__: Mapped 3177 MAC addresses.
#INFO:__main__: Updated 3336 subscribers for ter-bng1
#INFO:__main__: === FINISHED PROCESSING ROUTER: ter-bng1
````

This will poll the devices every 5mins to run it in the backgroup add & at the end

### 5. Open a new terminal and check there is data in the db
```bash
cd /opt/online/db
python3 sql-query1.py
````
You should see around 100 results of data if not check there are no errors running the collector script

### 6. Start the API
```bash
cd /opt/online/app
gunicorn -w 4 --bind 127.0.0.1:5000 api:app &
````

### 7. Access dashboard 
replace <host> with the dns/ip of this box, you should see data
```bash
http://<host>/online/dashboard.html
````

