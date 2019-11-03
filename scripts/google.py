import os
import functools
import httplib2
import json
import time
import dateparser
from datetime import datetime, timedelta
from oauth2client import tools
from oauth2client.client import OAuth2WebServerFlow
from oauth2client.file import Storage
from typing import List, Union


APP_KEYS_FILE = os.path.join(os.path.dirname(
    os.path.realpath(__file__)), 'app_keys.json')
USER_OAUTH_DATA_FILE = os.path.expanduser('~/.google-reminders-cli-oauth')


@functools.total_ordering
class Reminder:
    def __init__(
        self,
        id: str,
        title: str,
        dt: datetime,
        creation_timestamp_msec: int = None,
        done: bool = False,
    ):
        if id is None:
            raise ValueError('Reminder id must not be None')
        self.id = id
        self.title = title
        self.dt = dt
        self.creation_timestamp_msec = creation_timestamp_msec
        self.done = done

    def __repr_title(self):
        """
        if reminder is not done return its title as is. otherwise return
        a strikethrough title
        """
        return (
            self.title if not self.done
            else '̶'.join(c for c in self.title)
        )

    def __lt__(self, other):
        return self.dt < other.dt

    def __str__(self):
        format = '%Y-%m-%d %H:%M'
        return f'{self.dt.strftime(format)}: {self.__repr_title()} ; id="{self.id}"'


def authenticate() -> httplib2.Http:
    """
    returns an Http instance that already contains the user credentials and is
    ready to make requests to alter user data.

    On the first time, this function will open the browser so that the user can
    grant it access to his data
    """
    with open(APP_KEYS_FILE) as f:
        app_keys = json.load(f)
    storage = Storage(USER_OAUTH_DATA_FILE)
    credentials = storage.get()
    if credentials is None or credentials.invalid:
        credentials = tools.run_flow(
            flow=OAuth2WebServerFlow(
                client_id=app_keys['APP_CLIENT_ID'],
                client_secret=app_keys['APP_CLIENT_SECRET'],
                scope=['https://www.googleapis.com/auth/reminders'],
                user_agent='google reminders cli tool',
            ),
            storage=storage,
            flags=tools.argparser.parse_args([]),
        )
    auth_http = credentials.authorize(httplib2.Http())
    return auth_http


def create_req_body(reminder: Reminder) -> dict:
    """
    returns the body of a create-reminder request
    """
    body = {
        '2': {
            '1': 7
        },
        '3': {
            '2': reminder.id
        },
        '4': {
            '1': {
                '2': reminder.id
            },
            '3': reminder.title,
            '5': {
                '1': reminder.dt.year,
                '2': reminder.dt.month,
                '3': reminder.dt.day,
                '4': {
                    '1': reminder.dt.hour,
                    '2': reminder.dt.minute,
                    '3': reminder.dt.second,
                }
            },
            '8': 0
        }
    }
    return json.dumps(body)


def get_req_body(reminder_id: str):
    """
    returns the body of a get-reminder request
    """
    body = {'2': [{'2': reminder_id}]}
    return json.dumps(body)


def delete_req_body(reminder_id: str):
    """
    returns the body of a delete-reminder request
    """
    body = {'2': [{'2': reminder_id}]}
    return json.dumps(body)


def list_req_body(num_reminders: int, max_timestamp_msec: int = 0):
    """
    returns the body of a list-reminders request.

    The body corresponds to a request that retrieves a maximum of num_reminders
    reminders, whose creation timestamp is less than max_timestamp_msec.
    max_timestamp_msec is a unix timestamp in milliseconds. if its value is 0, treat
    it as current time.
    """
    body = {
        '5': 1,  # boolean field: 0 or 1. 0 doesn't work ¯\_(ツ)_/¯
        '6': num_reminders,  # number number of reminders to retrieve
    }

    if max_timestamp_msec:
        max_timestamp_msec += int(timedelta(hours=15).total_seconds() * 1000)
        body['16'] = max_timestamp_msec
        # Empirically, when requesting with a certain timestamp, reminders with the given
        # timestamp or even a bit smaller timestamp are not returned. Therefore we increase
        # the timestamp by 15 hours, which seems to solve this...  ~~voodoo~~
        # (I wish Google had a normal API for reminders)

    return json.dumps(body)


def build_reminder(reminder_dict: dict):
    r = reminder_dict
    try:
        id = r['1']['2']
        title = r['3']
        year = r['5']['1']
        month = r['5']['2']
        day = r['5']['3']
        hour = r['5']['4']['1']
        minute = r['5']['4']['2']
        second = r['5']['4']['3']
        creation_timestamp_msec = int(r['18'])
        done = '8' in r and r['8'] == 1

        return Reminder(
            id=id,
            title=title,
            dt=datetime(year, month, day, hour, minute, second),
            creation_timestamp_msec=creation_timestamp_msec,
            done=done,
        )

    except KeyError:
        print('build_reminder failed: unrecognized reminder dictionary format')
        return None


URIs = {
    'create': 'https://reminders-pa.clients6.google.com/v1internalOP/reminders/create',
    'delete': 'https://reminders-pa.clients6.google.com/v1internalOP/reminders/delete',
    'get': 'https://reminders-pa.clients6.google.com/v1internalOP/reminders/get',
    'list': 'https://reminders-pa.clients6.google.com/v1internalOP/reminders/list'
}

HEADERS = {
    'content-type': 'application/json+protobuf',
}

HTTP_OK = 200


class RemindersClient:
    def __init__(self):
        self.auth_http = authenticate()

    @staticmethod
    def _report_error(response, content, func_name: str):
        print(f'Error in {func_name}:')
        print(f'    status code: {response.status}')
        print(f'    content: {content}')

    def create_reminder(self, reminder: Reminder) -> bool:
        """
        send a 'create reminder' request.
        returns True upon a successful creation of a reminder
        """
        response, content = self.auth_http.request(
            uri=URIs['create'],
            method='POST',
            body=create_req_body(reminder),
            headers=HEADERS,
        )
        if response.status == HTTP_OK:
            return True
        else:
            self._report_error(response, content, 'create_reminder')
            return False

    def get_reminder(self, reminder_id: str) -> Union[Reminder, None]:
        """
        retrieve information about the reminder with the given id. None if an
        error occurred
        """
        response, content = self.auth_http.request(
            uri=URIs['get'],
            method='POST',
            body=get_req_body(reminder_id),
            headers=HEADERS,
        )
        if response.status == HTTP_OK:
            content_dict = json.loads(content.decode('utf-8'))
            if content_dict == {}:
                print(f'Couldn\'t find reminder with id={reminder_id}')
                return None
            reminder_dict = content_dict['1'][0]
            return build_reminder(reminder_dict=reminder_dict)
        else:
            self._report_error(response, content, 'get_reminder')

    def delete_reminder(self, reminder_id: str) -> bool:
        """
        delete the reminder with the given id.
        Returns True upon a successful deletion
        """
        response, content = self.auth_http.request(
            uri=URIs['delete'],
            method='POST',
            body=delete_req_body(reminder_id),
            headers=HEADERS,
        )
        if response.status == HTTP_OK:
            return True
        else:
            self._report_error(response, content, 'delete_reminder')
            return False

    def list_reminders(self, num_reminders: int) -> Union[List[Reminder], None]:
        """
        returns a list of the last num_reminders created reminders, or
        None if an error occurred
        """
        response, content = self.auth_http.request(
            uri=URIs['list'],
            method='POST',
            body=list_req_body(num_reminders=num_reminders),
            headers=HEADERS,
        )
        if response.status == HTTP_OK:
            content_dict = json.loads(content.decode('utf-8'))
            if '1' not in content_dict:
                return []
            reminders_dict_list = content_dict['1']
            reminders = [
                build_reminder(reminder_dict)
                for reminder_dict in reminders_dict_list
            ]
            return reminders
        else:
            self._report_error(response, content, 'list_reminders')
            return None


def parse_time_str(time_str: str) -> Union[datetime, None]:
    dt = dateparser.parse(time_str)
    if dt is None:
        print('Unrecognizable time text. See help menu for legal formats')
        return None
    return dt


def gen_id() -> str:
    """generate a fresh reminder id"""
    # id is set according to the current unix time
    return f'cli-reminder-{time.time()}'


def remind(title, time_str):
    client = RemindersClient()
    dt = parse_time_str(time_str)
    if dt is None:
        return None
    reminder = Reminder(id=gen_id(), title=title, dt=dt)
    if reminder is not None:
        if client.create_reminder(reminder):
            print('Reminder set successfully:')
            print(reminder)
    return reminder
