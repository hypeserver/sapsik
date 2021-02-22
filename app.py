import os
import datetime

from slack_bolt import App
from flask import Flask, request
from slack_bolt.adapter.flask import SlackRequestHandler

import image as im
from sheets import Sheet as pins_sheet

token = os.environ.get("SLACK_BOT_TOKEN")
secret = os.environ.get("SLACK_SIGNING_SECRET")

app = App(
    token=token,
    signing_secret=secret,
    process_before_response=True
)
flask_app = Flask(__name__)
handler = SlackRequestHandler(app)

@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    return handler.handle(request)

@app.middleware  # or app.use(log_request)
def log_request(logger, body, next):
    retry = request.headers.environ.get('HTTP_X_SLACK_RETRY_NUM', 0)
    if not retry:
        return next()

@app.event('file_shared')
def file_shared(body, client, context, logger):
    context.ack()
    
    file_id = body["event"]["file_id"]
    file_info = client.files_info(file=file_id)

    if file_info['file']['filetype'] not in ['jpg']:
        return

    url = file_info['file']['url_private']

    image = im.open_url(url, token)

    mirrored = im.mirror(image)
    mirrored.save('/tmp/%s.jpg'%file_id)

    with open('/tmp/%s.jpg'%file_id, 'rb') as file_content:
        response = client.files_upload(
            file=file_content,
            channels="sapsik"
            )

@app.event('pin_added')
def pin_added(body, client, context, logger):
    event = body['event']
    channel_id = event['channel_id']
    channel_name = client.conversations_info(channel=channel_id)['channel']['name']
    pinned_at = datetime.datetime.fromtimestamp(event['item']['created'])
    pinned_at = pinned_at.strftime('%d/%m/%Y %H:%M:%S')
    pinned_by = event['user']
    pinned_by = client.users_info(user=event['user'])
    message = event['item']['message']['text']
    message_by = client.users_info(user=event['item']['message']['user'])
    message_username = message_by['user']['profile']['display_name']
    permalink = event['item']['message']['permalink']
    message_type = event['item']['message']['type']

    row = [pinned_at, channel_name, message_username, message, permalink]

    pins_sheet.append(row)

# Only for local debug
if __name__ == "__main__":
    flask_app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))

