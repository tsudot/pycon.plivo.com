import os
import urllib, urllib2
import random
import simplejson as json

from flask import Flask, request, make_response, render_template
from config import PLIVO_AUTH_ID, PLIVO_AUTH_TOKEN, PUSHER_APP_ID, PUSHER_KEY, PUSHER_SECRET
import redis
import plivo
import pusher

from utils import clean_phone_number

app = Flask(__name__)
app.debug = True

BASE_URL = 'http://pycon.plivo.com/'
PLIVO_NUMBER = '18554075486'

CONFERENCE_NAME = 'pycon'

def get_plivo_connection():
    p = plivo.RestAPI(PLIVO_AUTH_ID, PLIVO_AUTH_TOKEN)
    return p

def get_pusher_connection():
    pr = pusher.Pusher(app_id=PUSHER_APP_ID, 
                        key=PUSHER_KEY,
                        secret=PUSHER_SECRET)
    return pr

@app.errorhandler(404)
def page_not_found(error):
    return render_template('not_found.html')

@app.route('/', methods=['GET'])
def index():
    return render_template('home.html')

def make_json_response(data):
    response = make_response(json.dumps(data))
    response.headers['Content-Type'] = 'application/json'
    return response

@app.route('/conference/', methods=['GET', 'POST'])
def conference(number=None):
    number = number or request.args.get('number')
    if not number:
        response = make_json_response({'error':'No number'})
        return response

    #number = clean_phone_number(number)

    call_params = {
            'to':number,
            'from':PLIVO_NUMBER,
            'answer_url':BASE_URL + '/response/conf/',
            'answer_method':'GET', 
            }

    p = get_plivo_connection()
    status, response = p.make_call(call_params)
    import pdb;pdb.set_trace()

    if status == 201:
        response = make_json_response({'success': True})
        return response

    response = make_json_response({'error':True})
    return response

@app.route('/response/conf/', methods=['GET', 'POST'])
def conference_response():
    r = plivo.Response()
    r.addSpeak('Hi, welcome to plivo realtime conference. You\'ll be placed into conference right away.', voice='WOMAN')
    conference_params = {
            'enterSound':'beep:1',
            'waitSound':BASE_URL + 'response/conf/music/',
            'timeLimit':'8400',
            'action':BASE_URL + 'response/conf/action/',
            'callbackUrl':BASE_URL + 'response/conf/callback/',
            'callbackMethod':'GET',
            }
    r.addConference(CONFERENCE_NAME, **conference_params)

    response = make_response(r.to_xml())
    response.headers['Content-Type'] = 'text/xml'
    return response

@app.route('/response/conf/callback/', methods=['GET', 'POST'])
def conference_callback():
    pr = get_pusher_connection()
    p = get_plivo_connection()

    conference_params = {
            'conference_name': CONFERENCE_NAME,
            }
    status, response = p.get_live_conference(conference_params)
    members = response['members']
    print members

    numbers = []
    for member in members:
        numbers.append(member['to'])

    pr['pycon.plivo'].trigger('show_members', json.dumps(numbers))

    return ''

app.run('0.0.0.0',port=5000)
