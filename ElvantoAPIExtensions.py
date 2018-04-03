# region ElvantoAPI | github.com/elvanto/api-py
# import ElvantoAPI
import json

import requests

oauth_url = "https://api.elvanto.com/oauth"
token_url = "https://api.elvanto.com/oauth/token"
api_url = "https://api.elvanto.com/v1/"


class ElvantoAPI:
    def _AuthorizeURL(ClientID, RedirectURI, Scope, IsWebApp, State=None):
        """
        Function to gain the URL needed for users to log in to your integration.
        Web Apps and Non Web Apps both use this function, it simply returns a different URL
        Non Web Apps don't use the state argument
        :param ClientID: int - The Client ID of your integration
        :param RedirectURI: str - The URL to redirect users to after they have logged on
        :param Scope: list or str - Scope the Web App requires to function
        :param State: (optional) str - Only use if needed in your redirection call
        :param IsWebApp: bool - Web Apps and Non WebApps have different URLs they send users to
        :return: str - Application authorization url
        """
        if type(Scope) == list:  # Convert list to comma delimited string
            Scope = ','.join(Scope)
        info = {
            'id': str(ClientID),
            'uri': RedirectURI,
            'scope': Scope
        }
        if IsWebApp:
            return oauth_url + '?type=web_server&client_id={id}&redirect_uri={uri}&scope={scope}'.format(**info) + (
                ('&state=' + State) if State else '')
        else:
            return oauth_url + '?type=user_agent&client_id={id}&redirect_uri={uri}&scope={scope}'.format(**info)

    def _GetTokens(ClientID, ClientSecret, Code, RedirectURI):
        """
        Gets the acccess tokens, after the user has logged into the Web App via URL provided in the getURL function
        :param ClientID: int - Client ID of your integration
        :param ClientSecret: str - Client Secret of your integration
        :param Code: int - The Code returned after user logs in
        :param RedirectURI: str - The redirect_uri specified in getURL
        :return: dict - {"access_token": str, "expires_in": int, "refresh_token": str}
        """
        global token_url
        info = {
            'client_id': ClientID,
            'client_secret': ClientSecret,
            'code': Code,
            'redirect_uri': RedirectURI
        }
        params = 'grant_type=authorization_code&client_id={client_id}&client_secret={client_secret}&code={code}&redirect_uri={redirect_uri}'.format(
            **info)
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        data = requests.post(token_url, data=params, headers=headers)
        return json.loads(data.text)

    class Connection():
        def __init__(self, **auth):
            """
            Basic Connection Object.
            To automatically refresh tokens, you need to provide the client_id client_secret and redirect_uri needed for the _GetTokens function.
            :param auth: For API Key Authentication; APIKey = str
            :param auth: For OAuth Authentication; AccessToken = str
            :param auth: To enable Token Refresh for OAuth, RefreshToken = str
            """
            self.s = requests.Session()
            if 'APIKey' in auth:
                self.API_Key = requests.auth.HTTPBasicAuth(auth['APIKey'], '')

            elif 'AccessToken' in auth:
                self.OAuth = {
                    'Authorization': 'Bearer %s' % auth['AccessToken']
                }
                self.refresh_token = auth['RefreshToken'] if 'RefreshToken' in auth else None

            else:  # If neither of these, invalid Auth. Raise Syntax Error
                raise SyntaxError(
                    'Invalid Auth method. Please use APIKey (string) or AccessToken (string), ExpiresIn (float)')

        def _RefreshToken(self):
            """
            Function to refresh the tokens.
            :return: int - Expiry time in seconds
            """
            global token_url
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            params = 'grant_type=refresh_token&refresh_token=' + self.refresh_token
            data = requests.post(token_url, data=params, headers=headers)
            new_tokens = json.loads(data.text)
            self.__init__(AccessToken=new_tokens['access_token'], RefreshToken=new_tokens['refresh_token'])
            return new_tokens['expires_in']

        def _Post(self, endpoint, **kwargs):
            """
            How the wrapper does the API Calls.
            :param endpoint: Endpoint of the API Call. Ie people/getInfo
            :param kwargs: Arguments for the call. Simple arguments can be Arg=Value.
            Arguments like 'Fields' or 'Search' are more complex and need to be formatted as:
                fields=[mobile,family]
                search={'mobile':number}
            :return: Returns a Dict that corresponds to the JSON for the API call.
            """
            global api_url
            posturl = api_url + endpoint + ('' if endpoint[:-1] == '.' else '.') + 'json'

            if self.API_Key:
                self.data = requests.post(posturl, auth=self.API_Key, json=kwargs)
            elif self.OAuth:
                self.data = requests.post(posturl, headers=self.OAuth, json=kwargs)
            info = json.loads(self.data.text)
            if info['status'] != 'ok':
                if int(info['error']['code']) == 121:  # Token Expired
                    if self.refresh_token:  # Can't refresh if no refresh token
                        self._RefreshToken()  # Refresh Tokens
                        info = self._Post(endpoint, **kwargs)  # Make call again
                    else:
                        return {
                            'status': 'Token expired please renew'
                        }
            return info


# endregion

import datetime
import time


class ElvantoAPI(ElvantoAPI):
    class Connection(ElvantoAPI.Connection):
        # def __init__(self, **auth):
        #     super().__init__(**auth)
        #
        def servicesOnDay(self, day: int, *, locationName=None, locationID=None, parseServices=True, fields=None):
            return Helpers.FilterLocation(self.servicesOnDate(Helpers.NextDate(day), parseServices=parseServices),locationName,locationID)

        def servicesOnDate(self, date_service: datetime.datetime, *, locationName=None, locationID=None,
                           parseServices=True, fields=None):
            return Helpers.FilterLocation(Helpers.ServicesOnDate(self, date_service, parseServices=parseServices),locationName,locationID)

        def servicesUpcoming(self, days: int = 7, *, locationName=None, locationID=None, parseServices=True, fields = None):
            return Helpers.FilterLocation(Helpers.ServicesUpcoming(self, days=days, parseServices=parseServices),locationName,locationID)

        def getPeople(self):
            result = {}

            def pull(page=1):
                resp = self._Post("people/getAll", page=page)
                assert resp["status"] == "ok"
                resp = resp["people"]
                for person in resp["person"]:
                    result[person["id"]] = {
                        "first_name": person["preferred_name"] or person["firstname"],
                        "middle_name": person["middle_name"],
                        "last_name": person["lastname"],
                        "email": person["email"]
                    }
                _pageNo = int(resp["page"])
                if (resp["total"] - (_pageNo - 1) * resp["per_page"] - resp["on_this_page"]) > 0:
                    pull(page=_pageNo + 1)

            pull()
            self.people = result
            return result

        def findContact(self, id: str = None, *args, first_name: str = None, middle_name: str = None,
                        last_name: str = None, email: str = None, resolve: bool = True):
            """
            :param first_name: search term
            :param middle_name: search term
            :param last_name: search term
            :param email: search term
            :param id: search term (exact)
            :param resolve: Boolean to resolve matches, or just return IDs
            :return: list - array of people objects
            """
            if id:
                if id in self.people:
                    return [self.people[id]]
                raise Exception("ID not found in contacts")

            if not any([first_name, middle_name, last_name, email]):
                raise Exception("No keyword arguments specified")

            result = []
            for id in self.people:
                person = self.people[id]
                if all([(first_name.lower() in person["first_name"].lower() if first_name else True),
                        (middle_name.lower() in person["middle_name"].lower() if middle_name else True),
                        (last_name.lower() in person["last_name"].lower() if last_name else True),
                        (email.lower() in person["email"].lower() if email else True)]):
                    if resolve:
                        _person = person
                        _person["id"] = id
                    result.append(_person if resolve else id)
            return result


class Helpers:
    @staticmethod
    def FilterLocation(services:list, locationName:str, locationID:str):
        if locationName: return list(filter(lambda serviceObj: serviceObj.location.name.lower() == locationName.lower(), services))
        if locationID: return list(filter(lambda serviceObj: serviceObj.location.id.lower() == locationID.lower(),services))
        return services

    @staticmethod
    def NextDate(day: int):
        # 0 - 6
        date_today = datetime.date.today()
        date_next = date_today + datetime.timedelta((day - date_today.weekday()) % 7)
        return date_next

    @staticmethod
    def ServicesUpcoming(api: ElvantoAPI.Connection, days: int = 7, parseServices=True,
                         fields=None):
        if fields is None: fields = ["plans", "volunteers", "songs"]
        services = api._Post("services/getAll", page_size=20, start=str(datetime.date.today() - datetime.timedelta(1)),
                             end=str(datetime.date.today() + datetime.timedelta(days)), fields=fields)
        if "services" not in services: return []
        return list(map(Service, services["services"]["service"]) if parseServices else services["services"]["service"])

    @staticmethod
    def ServicesOnDate(api: ElvantoAPI.Connection, date_service: datetime.datetime, parseServices=True,
                       fields=None):
        if fields is None: fields = ["plans", "volunteers", "songs"]
        """
        API Request :: services/getAll
        start | YYYY-MM-DD
        end   | YYYY-MM-DD
        page_size | int | minimum page size is 10
        """
        services = api._Post("services/getAll", page_size=10, start=str(date_service - datetime.timedelta(1)),
                             end=str(date_service + datetime.timedelta(1)), fields=fields)
        if "services" not in services: return []
        return list(map(Service, services["services"]["service"]) if parseServices else services["services"]["service"])

    @staticmethod
    def utc_to_local(utc_datetime):
        now_timestamp = time.time()
        offset = datetime.datetime.fromtimestamp(now_timestamp) - datetime.datetime.utcfromtimestamp(now_timestamp)
        return utc_datetime + offset


class Enums:
    class Days:
        MONDAY = 0
        TUESDAY = 1
        WEDNESDAY = 2
        THURSDAY = 3
        FRIDAY = 4
        SATURDAY = 5
        SUNDAY = 6


class Service:
    def __repr__(self):
        return "%s @ %s" % (self.name, self.date.strftime("%#I:%M%p %d/%m/%Y"))

    def __init__(self, serviceDict):

        self._data = serviceDict

        class Type:
            @property
            def id(this):
                return self._data["service_type"]["id"]

            @property
            def name(this):
                return self._data["service_type"]["name"]

        self.type = Type()

        class Location:
            @property
            def id(this):
                return self._data["location"]["id"]

            @property
            def name(this):
                return self._data["location"]["name"]

        self.location = Location()

        class Songs(list):
            def __new__(cls):
                return None
            # raise NotImplementedError
            pass

        self.songs = Songs() if "songs" in self._data else None

        class Volunteers:

            class Person():
                def __init__(self, root):
                    self.root = root

                def __repr__(self):
                    return self.name
                def __str__(self):
                    return self.id

                @property
                def name(self):
                    return "%s %s%s" % (self.root["person"]["preferred_name"] or self.root["person"]["firstname"],
                                        (self.root["person"]["middle_name"] + " ") if self.root["person"]["middle_name"] else "",
                                        self.root["person"]["lastname"])

                @property
                def id(self):
                    return self.root["person"]["id"]

            def __init__(this):
                this.root = self._data["volunteers"]["plan"][0]["positions"]["position"]

                # this.people = dict()
                #
                # for role in this.root:
                #     if "volunteers" in role and role["volunteers"]:
                #         for volunteer in role["volunteers"]["volunteer"]:
                #             volunteer = volunteer["person"]  # ignore the status key
                #             if volunteer["id"] not in this.people:
                #                 this.people[volunteer["id"]] = volunteer
                #                 this.people[volunteer["id"]]["roles"] = []
                #             _role = role.copy()
                #             del _role["volunteers"]
                #             this.people[volunteer["id"]]["roles"].append(_role)

            @staticmethod
            def __map(listObj: list):
                return map(Volunteers.Person, next(listObj)["volunteers"]["volunteer"])

            def byDepartmentId(self, id):
                return list(self.__map(filter(lambda r: r["department_id"].lower() == id.lower(), self.root)))

            def byDepartmentName(self, name):
                return list(self.__map(filter(lambda r: r["department_name"].lower() == name.lower(), self.root)))

            def bySubDepartmentId(self, id):
                return list(self.__map(filter(lambda r: r["sub_department_id"].lower() == id.lower(), self.root)))

            def bySubDepartmentName(self, name):
                return list(self.__map(filter(lambda r: r["sub_department_name"].lower() == name.lower(), self.root)))

            def byPositionId(self, id):
                return list(self.__map(filter(lambda r: r["position_id"].lower() == id.lower(), self.root)))

            def byPositionName(self, name):
                return list(self.__map(filter(lambda r: r["position_name"].lower() == name.lower(), self.root)))

        self.volunteers = Volunteers() if "volunteers" in self._data else None

        class Plan(list):
            class BaseItem:
                def __new__(cls, data):
                    __obj = object.__new__(cls)
                    __obj.id = data["id"]
                    __obj.title = data["title"]
                    return __obj

                def __repr__(self):
                    return '%s("%s")' % (self.__class__.__name__, self.title)

            class Header(BaseItem):
                pass

            class Item(BaseItem):
                def __init__(self, data):
                    self.description = data["description"]
                    self.duration = data["duration"]

            class Song(Item):
                def __init__(self, data):
                    super().__init__(data)
                    self.song = data["song"]
                    """
                    self.song = {
                    'id': '8e113769-4a5a-11e7-ba01-061a3b9c64af',
                    'ccli_number': '6016351',
                    'title': '10,000 Reasons',
                    'artist': 'Redman',
                    'album': '',
                    'arrangement': {
                        'id': '8e123525-4a5a-11e7-ba01-061a3b9c64af',
                        'title': 'Standard Arrangement',
                        'bpm': '0',
                        'duration': '00:00',
                        'sequence': '',
                        'key_id': None,
                        'key_name': '',
                        'key': None}
                    }
                    """

            def __generateObject(self, data):
                if data["song"]:
                    return self.Song(data)
                elif data["heading"] == 1:
                    return self.Header(data)
                else:
                    return self.Item(data)

            def __init__(this):
                if "plan" not in self._data["plans"]:
                    return
                list.__init__(this, map(this.__generateObject, self._data["plans"]["plan"][0]["items"]["item"]))
        self.plan = Plan() if "plans" in self._data else None

    @property
    def id(self):
        return self._data["id"]

    @property
    def name(self):
        return self._data["name"]

    @property
    def date(self):
        return Helpers.utc_to_local(datetime.datetime.strptime(self._data["date"], "%Y-%m-%d %H:%M:%S"))
