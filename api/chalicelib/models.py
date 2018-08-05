from datetime import datetime

import google_auth_httplib2
from pynamodb.models import Model
from pynamodb.attributes import UnicodeAttribute, UTCDateTimeAttribute, JSONAttribute
from google.oauth2 import credentials
from apiclient import discovery


Credentials = credentials.Credentials

_DEFAULT_AWS_REGION = 'ap-southeast-2'


class Space(Model):
    class Meta:
        table_name = 'team2-space'
        region = _DEFAULT_AWS_REGION
    name = UnicodeAttribute(hash_key=True)  # event['space']['name']
    type = UnicodeAttribute(null=False)


class UserRegister(Model):
    class Meta:
        table_name = 'team2-user-register'
        region = _DEFAULT_AWS_REGION


class User(Model):
    class Meta:
        table_name = 'team2-user'
        region = _DEFAULT_AWS_REGION
    name = UnicodeAttribute(hash_key=True)  # event['user']['name']
    credentials = JSONAttribute(null=False)
    display_name = UnicodeAttribute(null=True)
    given_name = UnicodeAttribute(null=True)
    family_name = UnicodeAttribute(null=True)
    email = UnicodeAttribute(null=True)
    picture = UnicodeAttribute(null=True)
    google_id = UnicodeAttribute(null=True)
    updated_timestamp = UTCDateTimeAttribute(null=False)

    def get_credentials(self):
        return Credentials(**self.credentials)

    def get_profile(self):
        creds = self.get_credentials()
        http = google_auth_httplib2.AuthorizedHttp(creds)
        oauth_api = discovery.build('oauth2', 'v2', http=http)
        try:
            user_info = oauth_api.userinfo().get().execute()
            return user_info
        except Exception as e:
            return None

    def populate_from_profile(self):
        profile = self.get_profile()
        if profile:
            self.email = profile.get('email')
            self.display_name = profile.get('display_name')
            self.given_name = profile.get('given_name')
            self.family_name = profile.get('family_name')
            self.picture = profile.get('picture')
            self.google_id = profile.get('id')

    def put_credentials(self, creds: Credentials) -> None:
        """Stores OAuth2 credentials for a user.

        Args:
            user_name (str): The identifier for the associated user.
            creds (Credentials): The OAuth2 credentials obtained for the user.
        """
        self.credentials = {
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': creds.scopes,
        }

    def save(self, **kwargs):
        self.updated_timestamp = datetime.now()
        return super().save(**kwargs)