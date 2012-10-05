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
#app.debug = True

BASE_URL = 'http://pycon.plivo.com/'
PLIVO_NUMBER = '18554075486'

CONFERENCE_NAME = 'pycon'
PLIVO_MUSIC = 'http://s3.amazonaws.com/plivocloud/music.mp3'

def get_plivo_connection():
    p = plivo.RestAPI(PLIVO_AUTH_ID, PLIVO_AUTH_TOKEN)
    return p

def get_pusher_connection():
    pr = pusher.Pusher(app_id=PUSHER_APP_ID, 
                        key=PUSHER_KEY,
                        secret=PUSHER_SECRET)
    return pr

def get_redis_connection():
    rd = redis.StrictRedis(host='localhost',
                port=6379)
    return rd

@app.errorhandler(404)
def page_not_found(error):
    return render_template('not_found.html')

@app.errorhandler(500)
def page_not_found(error):
    return render_template('custom_500.html')

@app.route('/', methods=['GET'])
def index():
    return render_template('home.html')

def make_json_response(data):
    response = make_response(json.dumps(data))
    response.headers['Content-Type'] = 'application/json'
    return response

@app.route('/call/', methods=['GET', 'POST'])
def call(number_call=None):
    number = number_call or request.args.get('number_call')
    if not number:
        response = make_json_response({'error':'No number'})
        return response

    call_params = {
            'to':number,
            'from':PLIVO_NUMBER,
            'ring_url':BASE_URL + 'response/call/ring/',
            'ring_method':'GET',
            'answer_url':BASE_URL + 'response/conf/music/',
            'answer_method':'GET', 
            }

    p = get_plivo_connection()
    status, response = p.make_call(call_params)

    if status == 201:
        response = make_json_response({'success': True})
        return response

    response = make_json_response({'error':'Call cannot be established, please verify your number'})
    return response

@app.route('/call/play/', methods=['GET', 'POST'])
def call_play():
    call_uuid = request.args.get('call_uuid');
    tts_msg = request.args.get('tts_msg');

    p = get_plivo_connection()
    p.speak({'call_uuid':call_uuid, 'text':tts_msg})
    return ''


@app.route('/response/call/ring/', methods=['GET', 'POST'])
def call_ring():
    call_uuid = request.args.get('CallUUID')
    number = request.args.get('To')

    rd = get_redis_connection()
    rd.set(number, call_uuid)

    number_call_uuid = {number:call_uuid}
    pr = get_pusher_connection()

    pr['pycon.plivo'].trigger('in_call', json.dumps(number_call_uuid))

@app.route('/conference/', methods=['GET', 'POST'])
def conference(number=None):
    number = number or request.args.get('number')
    if not number:
        response = make_json_response({'error':'No number'})
        return response

    members = get_conference_members(CONFERENCE_NAME)
    for member in members:
        if number == member['to']:
            response = make_json_response({'error':'Already in conference'})
            return response

    call_params = {
            'to':number,
            'from':PLIVO_NUMBER,
            'answer_url':BASE_URL + 'response/conf/',
            'answer_method':'GET', 
            }

    p = get_plivo_connection()
    status, response = p.make_call(call_params)

    if status == 201:
        response = make_json_response({'success': True})
        return response

    response = make_json_response({'error':'Call cannot be established, please verify your number'})
    return response

@app.route('/response/conf/', methods=['GET', 'POST'])
def conference_response():
    r = plivo.Response()
    r.addSpeak('Welcome to the world of top class conferencing! You are being placed into a conference.', voice='WOMAN')
    conference_params = {
            'enterSound':'beep:1',
            'waitSound':BASE_URL + 'response/conf/music/',
            'timeLimit':'8400',
            'callbackUrl':BASE_URL + 'response/conf/callback/',
            'callbackMethod':'GET',
            }
    r.addConference(CONFERENCE_NAME, **conference_params)

    response = make_response(r.to_xml())
    response.headers['Content-Type'] = 'text/xml'
    return response

@app.route('/response/conf/callback/', methods=['GET', 'POST'])
def conference_callback():
    """
    Refresh the list of member on receiving any callback
    """
    event = request.args.get('Event') or None

    pr = get_pusher_connection()

    members = get_conference_members(CONFERENCE_NAME)

    pr['pycon.plivo'].trigger('show_members', json.dumps(members))
    response = make_json_response({'success': True})
    return response


@app.route('/response/conf/music/', methods=['GET', 'POST'])
def conference_music():
    r = plivo.Response()
    play_parameters = {
            'loop':'50',
            }
    r.addPlay(PLIVO_MUSIC, **play_parameters)
    response = make_response(r.to_xml())
    response.headers['Content-Type'] = 'text/xml'
    return response

@app.route('/conference/members/', methods=['GET', 'POST'])
def conference_members():
    pr = get_pusher_connection()

    members = get_conference_members(CONFERENCE_NAME)

    response = make_json_response(json.dumps(members))
    return response

@app.route('/conference/kick/', methods=['GET', 'POST'])
def conference_kick():
    member_id = request.args.get('member_id')

    p = get_plivo_connection()

    member_params = {
            'member_id': member_id,
            'conference_name': CONFERENCE_NAME,
            'callback_url':BASE_URL + 'response/conf/callback/',
            'callback_method':'GET',
            }
    p.kick_member(member_params)
    return 'Done'

@app.route('/conference/mute/', methods=['GET', 'POST'])
def conference_mute():
    member_id = request.args.get('member_id')

    p = get_plivo_connection()

    member_params = {
            'member_id': member_id,
            'conference_name': CONFERENCE_NAME,
            'callback_url':BASE_URL + 'response/conf/callback/',
            'callback_method':'GET',
            }
    p.mute_member(member_params)
    return 'Done'

@app.route('/conference/unmute/', methods=['GET', 'POST'])
def conference_unmute():
    member_id = request.args.get('member_id')

    p = get_plivo_connection()

    member_params = {
            'member_id': member_id,
            'conference_name': CONFERENCE_NAME,
            'callback_url':BASE_URL + 'response/conf/callback/',
            'callback_method':'GET',
            }
    print p.unmute_member(member_params)
    return 'Done'


@app.route('/conference/deaf/', methods=['GET', 'POST'])
def conference_deaf():
    member_id = request.args.get('member_id')

    p = get_plivo_connection()

    member_params = {
            'member_id': member_id,
            'conference_name': CONFERENCE_NAME,
            'callback_url':BASE_URL + 'response/conf/callback/',
            'callback_method':'GET',
            }
    p.deaf_member(member_params)
    return 'Done'

@app.route('/conference/undeaf/', methods=['GET', 'POST'])
def conference_undeaf():
    member_id = request.args.get('member_id')

    p = get_plivo_connection()

    member_params = {
            'member_id': member_id,
            'conference_name': CONFERENCE_NAME,
            'callback_url':BASE_URL + 'response/conf/callback/',
            'callback_method':'GET',
            }
    print p.undeaf_member(member_params)
    return 'Done'

def get_conference_members(conference_name):
    p = get_plivo_connection()
    conference_params = {
            'conference_name': CONFERENCE_NAME,
            }
    status, response = p.get_live_conference(conference_params)
    try:
        members = response['members']
    except:
        members = []

    return members


app.run('127.0.0.1', port=8000)
