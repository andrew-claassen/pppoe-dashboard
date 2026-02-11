# pppoe-dashboard
First off I am not a programmer, I work on network gear all day long and there are probably better ways todo this but that is why I like to build these to keep learning.

Some background: recently the company I work for changed the backend billing system which came with it's own RADIUS but with no API access and since I like to learn by doing I wanted to build a dashboard to show all current connected subscribers ( L2TP, PPPoE and PPPoE over LT2P )

This is currently working pulling data from 2x Cisco ASR1001x's with around 5k subscribers and it completes a run in under 30s.

I thought there may be a use for this for other people in a similar situation, so here it is.

The plan is to extend this to support other BNG's probably Mikrotik since I see that is used by smaller ISP's.

Quick and dirty howto:
#I am using sqlite so install this:
sudo apt install sqlite3

#I used Apache, add this to your config:
#/etc/apache2/sites-enabled/000-default.conf
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

#I put the files into /opt/online
#Setup a virtual env for python:
cd /opt/online
python3 -m venv /opt/online/venv
source venv/bin/activate
pip3 install --upgrade pip

#Edit the .env file with your router dns name/ip and login details
#Now start the collector it should show some output like so:
#INFO:__main__:=== STARTING DATA COLLECTION ===
#INFO:__main__:=== PROCESSING ROUTER: ter-bng1 ===
#INFO:__main__: Mapped 3319 IP addresses.
#INFO:__main__: Mapped 3177 MAC addresses.
#INFO:__main__: Updated 3336 subscribers for ter-bng1
#INFO:__main__: === FINISHED PROCESSING ROUTER: ter-bng1
python3 collect_pppoe_stats.py
#This will poll the devices every 5mins to run it in the backgroup add & at the end

#Open a new terminal and check there is data in the db
cd /opt/online/db
python3 sqlite.py
#You should see around 100 results of data if not check there are no errors running the collector script

#Start the API
cd /opt/online/app
gunicorn -w 4 --bind 127.0.0.1:5000 api:app &

#access dashboard replace <host> with the dns/ip of this box, you should see data
http://<host>/online/dashboard.html

