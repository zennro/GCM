import urllib, urllib2
from bottle import route, run, error
import sqlite3
import json
import os

VERSION="0.1"
KEY='AIzaSyBnHtItNkWffz8NT3A1fEOfqM1Ho-Q_-y8'
DB_FILE = 'GCM.db'

INDEX="""<html><head><title>GCM.py</title></head>
<body><pre>
<h1>GCM.py v%s</h1><hr/><h2>Availables commands:</h2><h4>Devices:</h4><ul>
<li>List all the registered devices: <a href="/devices/list">/devices/list</a></li>
<li>Add a device: <a href="/devices/add/">/devices/add/[id]:[token]</a></li>
<li>Delete a device: <a href="/devices/del/">/devices/del/[id]</a></li></ul>
<h4>Messages:</h4><ul>
<li>List all the messages already sent: <a href="/messages/list">/messages/list</a></li>
<li>Send a message to all devices: <a href="/messages/send/">/messages/send/[payload]</a></li>
<li>Send a message to a specific device: <a href="/messages/send/[id]/">/messages/send/[id]/[payload]</a></li>
<li>Flush all messages: <a href="/messages/flush">/messages/flush</a></li></ul>
made by <a href="http://twitter.com/vieux">@vieux</a>, from me on <a href="http://github.com/vieux/GCM">github</pre></body></html>""" % VERSION

##
# CUSTOM CLASSES
## 
class GCM():     
    def __init__(self):
        self.url = 'https://android.googleapis.com/gcm/send'
        self.key = KEY
         
    def sendMessage(self, tokens, data):
        if tokens == None or data == None: return False        
        values = {'registration_ids' : tokens, 'data' : json.loads(data) }        
        headers = {'Authorization': 'key=' + self.key, 'Content-Type':'application/json'}
        request = urllib2.Request(self.url, json.dumps(values).encode('utf-8'), headers)
        try:
            response = urllib2.urlopen(request)
            result = json.loads(response.read())
            return result['success']
        except urllib2.HTTPError, e:
            return None

class JsonError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return json.dumps({'status': 'KO', 'message': self.value})

def init_tables():
    try:
        cursor.execute("SELECT 1 FROM devices")
    except sqlite3.OperationalError:
        cursor.execute("CREATE TABLE devices (id TEXT UNIQUE, token TEXT UNIQUE)")
        db.commit()
    try:
        cursor.execute("SELECT 1 FROM messages")
    except sqlite3.OperationalError:
        cursor.execute("CREATE TABLE messages (payload TEXT, device_id TEXT)")
        db.commit()

##
# ERRORS
##
@error(404)
def error404(error):
    return JsonError('No such method').__str__()

@error(500)
def error500(error):
    return JsonError('An error occured').__str__()

##
# DEVICES
##
@route('/devices/list')
@route('/devices/list/')
def list_devices():
    cursor.execute("SELECT rowid, id, token FROM devices")
    devices = []
    for tuple in cursor.fetchall():
        devices.append({'rowid': tuple[0], 'id': tuple[1], 'token': tuple[2]})
    return json.dumps(devices)

@route('/devices/add')
@route('/devices/add/')
@route('/devices/add/<device>')
def add_device(device = None):
    try:
        if device is None : raise JsonError('device parameter is missing')
        device = device.split(':')
        if len(device) is not 2: raise JsonError('[device] parameter should be like [id]:[token]')
        if device[0].strip() == '': raise JsonError('[id] parameter is empty')
        if device[1].strip() == '': raise JsonError('[token] parameter is empty')
        try:
            cursor.execute("INSERT INTO devices VALUES (?, ?)", (device[0].strip(),device[1].strip()))
            db.commit()
        except sqlite3.IntegrityError: return JsonError('This token is already registered').__str__()
        return json.dumps({'status': 'OK', 'message':'The token was succesfully added'})
    except JsonError as e: return e.__str__()

@route('/devices/del')
@route('/devices/del/')
@route('/devices/del/<id>')
def del_device(id = None):
    if id is None or id.strip() is '': return JsonError('[id] parameter is missing').__str__()
    try:
        cursor.execute("DELETE FROM devices WHERE id=?", (id,))
        db.commit()
    except sqlite3.IntegrityError: return JsonError('An error occured while deleting the device').__str__()
    return json.dumps({'status': 'OK', 'message':'The device was succesfully removed'})

##
# MESSAGES
##
@route('/messages/list')
@route('/messages/list/')
def list_messages():
    cursor.execute("SELECT rowid, payload, device_id FROM messages")
    messages = []
    for tuple in cursor.fetchall():
        messages.append({'rowid': tuple[0], 'payload': tuple[1], 'device_id': tuple[2]})
    return json.dumps(messages)

@route('/messages/send')
@route('/messages/send/')
@route('/messages/send/<payload>')
def send_messages(payload = None):
    return send_message(None, payload)

@route('/messages/send/<id>')
@route('/messages/send/<id>/')
@route('/messages/send/<id>/<payload>')
def send_message(id = None, payload = None):
    if payload is None or payload.strip() == '': return JsonError('[payload] parameter is missing').__str__()
    if id is None: 
        devices = cursor.execute("SELECT id, token FROM devices").fetchall()
        if len(devices) == 0: return JsonError('No device in the database').__str__() 
    else:
        devices = cursor.execute("SELECT id, token FROM devices WHERE id=?", (id,)).fetchall()
        if len(devices) == 0: return JsonError('No such device ' + id).__str__()
    ids=[elt[0] for elt in devices]
    tokens=[elt[1] for elt in devices]
    sender = GCM()
    sent = sender.sendMessage(tokens, payload)
    if sent != len(ids): return json.dumps({'status': 'KO', 'success': sent, 'failure': len(ids) - sent, 'message': 'Message not sent correctly'})    
    for _id in ids:
        try:
            cursor.execute("INSERT INTO messages VALUES (?, ?)", (payload, _id))
            db.commit()
        except sqlite3.IntegrityError: pass     
    return json.dumps({'status': 'OK', 'success': sent, 'failure': len(ids) - sent, 'message':'The message was sent'})

@route('/messages/flush')
@route('/messages/flush/')
def flush_messages():
    #cursor.execute("DELETE FROM messages WHERE 1")
    cursor.execute("DROP TABLE IF EXISTS messages")
    db.commit()
    init_tables()
    return json.dumps({'status': 'OK', 'message':'All the messages were flushed'})

@route('/erase')
@route('/erase/')
def erase():
    global cursor
    global db
    cursor.close()
    db.close()
    os.remove(DB_FILE)
    db = sqlite3.connect(os.environ['HOME'] +  '/data/GCM.db')
    db.isolation_level = None
    cursor = db.cursor()
    init_tables()
    return json.dumps({'status': 'OK', 'message':'Database erased'})

##
# INDEX
##
@route('/')
def index():
    return INDEX

##
# INIT
##
db = sqlite3.connect(DB_FILE)
db.isolation_level = None
cursor = db.cursor()
init_tables()

##
# MAIN
##
if __name__ == "__main__": 
    run(host='0.0.0.0', port=8080, reloader=True)


