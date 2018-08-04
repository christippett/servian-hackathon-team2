import json
import logging

from chalice import Chalice, Response
from google.oauth2 import credentials
import google_auth_httplib2
from apiclient import discovery

from ssm_parameter_store import EC2ParameterStore

from chalicelib import models, utils, auth, messages


# Logging
logging.basicConfig(
    level=logging.INFO,
    style='{',
    format='{levelname:.1} [{asctime} {filename}:{lineno}] {message}')

# Get application configuration from SSM Parameter Store
store = EC2ParameterStore(region_name='ap-southeast-2')
parameters = store.get_parameters_by_path('/team2/', strip_path=True)
EC2ParameterStore.set_env(parameters)  # add parameters to os.environ before calling Chalice()

# Google credentials
Credentials = credentials.Credentials

# Initiate app
app = Chalice(app_name='timesheet-bot', debug=True)


# Routes
@app.route('/')
def index():
    request = app.current_request
    logging.info(request.__dict__)
    return {
        'base_url': utils.get_base_url(request),
        'current_url': utils.get_current_url(request)
    }


# Routes
@app.route('/test')
def test():
    request = app.current_request
    logging.info(request.__dict__)
    return {
        'base_url': utils.get_base_url(request),
        'current_url': utils.get_current_url(request)
    }


@app.route('/bot', methods=['POST'])
def bot_event():
    """Handler for events from Hangouts Chat."""
    request = app.current_request
    event = request.json_body
    space_name = event['space']['name']
    space_type = event['space']['type']

    if event['type'] == 'ADDED_TO_SPACE':
        # Register new space in DB
        space = models.Space(space_name, type=space_type)
        space.save()
        print(f'Registered {space_name} to DynamoDB')
        # Prompt registration
        if event['space']['type'] == 'DM':
            return {
                'text': 'Hey - thanks for adding me!'
            }

    if event['type'] == 'MESSAGE' or (
            event['type'] == 'ADDED_TO_SPACE' and 'message' in event):
        message_text = event['message']['text']
        if message_text == 'login':
            resp = check_user_authenticated(event)
        else:
            resp = messages.create_card_response(message_text)

    elif event['type'] == 'CARD_CLICKED':
        action_name = event['action']['actionMethodName']
        parameters = event['action']['parameters']
        resp = messages.respond_to_interactive_card_click(action_name, parameters)

    elif event['type'] == 'REMOVED_FROM_SPACE':
        # Delete space from DB
        try:
            space = models.Space.get(event['space']['name'])
            space.delete()
        except models.Space.DoesNotExist:
            pass
        # Logout user (delete from DB and invalidate token)
        auth.logout(event['user']['name'])
        return {}

    logging.info(resp)
    return resp


@app.route('/auth/callback')
def oauth2_callback():
    request = app.current_request
    if request.query_params.get('error'):
        return Response(
            status_code=301,
            body='',
            headers={'Location': 'https://timesheets.servian.fun/register/error'})
    auth.on_oauth2_callback(request)
    return Response(
        status_code=301,
        body='',
        headers={'Location': 'https://timesheets.servian.fun/register/config'})


def check_user_authenticated(event: dict) -> dict:
    """Handles a mention from Hangouts Chat."""
    request = app.current_request
    user_name = event['user']['name']
    try:
        user = models.User.get(user_name)
    except models.User.DoesNotExist:
        logging.info('Requesting credentials for user %s', user_name)
        oauth2_url = auth.get_authorization_url(event, request)
        return {
            'actionResponse': {
                'type': 'REQUEST_CONFIG',
                'url': oauth2_url,
            }
        }
    user_credentials = user.get_credentials()
    logging.info('Found existing auth credentials for user %s', user_name)
    return {'text': "You're authenticated and ready to go!"}
    # return produce_profile_message(user_credentials)


# def on_logout(event: dict) -> dict:
#     """Handles logging out the user."""
#     user_name = event['user']['name']
#     try:
#         auth.logout(user_name)
#     except Exception as e:
#         logging.exception(e)
#         return {'text': 'Failed to log out user %s: ```%s```' % (user_name, e)}
#     else:
#         return {'text': 'Logged out.'}


# def produce_profile_message(creds: Credentials):
#     """Generate a message containing the users profile inforamtion."""
#     http = google_auth_httplib2.AuthorizedHttp(creds)
#     people_api = discovery.build('people', 'v1', http=http)
#     try:
#         person = people_api.people().get(
#             resourceName='people/me',
#             personFields=','.join([
#                 'names',
#                 'addresses',
#                 'emailAddresses',
#                 'phoneNumbers',
#                 'photos',
#             ])).execute()
#     except Exception as e:
#         logging.exception(e)
#         return {
#             'text': 'Failed to fetch profile info: ```%s```' % e,
#         }
#     card = {}
#     if person.get('names') and person.get('photos'):
#         card.update({
#             'header': {
#                 'title': person['names'][0]['displayName'],
#                 'imageUrl': person['photos'][0]['url'],
#                 'imageStyle': 'AVATAR',
#             },
#         })
#     widgets = []
#     for email_address in person.get('emailAddresses', []):
#         widgets.append({
#             'keyValue': {
#                 'icon': 'EMAIL',
#                 'content': email_address['value'],
#             }
#         })
#     for phone_number in person.get('phoneNumbers', []):
#         widgets.append({
#             'keyValue': {
#                 'icon': 'PHONE',
#                 'content': phone_number['value'],
#             }
#         })
#     for address in person.get('addresses', []):
#         if 'formattedValue' in address:
#             widgets.append({
#                 'keyValue': {
#                     'icon': 'MAP_PIN',
#                     'content': address['formattedValue'],
#                 }
#             })
#     if widgets:
#         card.update({
#             'sections': [
#                 {
#                     'widgets': widgets,
#                 }
#             ]
#         })
#     if card:
#         return {'cards': [card]}
#     return {
#         'text': 'Hmm, no profile information found',
#     }


# @app.on_sqs_message(queue='team2-sqs-app-data')
# def handler(event):
#     for record in event:
#         print("Message body: %s" % record.body)


# @app.on_s3_event(bucket='mybucket')
# def handler(event):
#     print("Object uploaded for bucket: %s, key: %s"
#           % (event.bucket, event.key))


# The view function above will return {"hello": "world"}
# whenever you make an HTTP GET request to '/'.
#
# Here are a few more examples:
#
# @app.route('/hello/{name}')
# def hello_name(name):
#    # '/hello/james' -> {"hello": "james"}
#    return {'hello': name}
#
# @app.route('/users', methods=['POST'])
# def create_user():
#     # This is the JSON body the user sent in their POST request.
#     user_as_json = app.current_request.json_body
#     # We'll echo the json body back to the user in a 'user' key.
#     return {'user': user_as_json}
#
# See the README documentation for more examples.
#
