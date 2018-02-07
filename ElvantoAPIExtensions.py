# region ElvantoAPI | github.com/elvanto/api-py
# import ElvantoAPI
import requests
import json

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
            return oauth_url + '?type=web_server&client_id={id}&redirect_uri={uri}&scope={scope}'.format(**info) + (('&state=' + State) if State else '')
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
        params = 'grant_type=authorization_code&client_id={client_id}&client_secret={client_secret}&code={code}&redirect_uri={redirect_uri}'.format(**info)
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
                raise SyntaxError('Invalid Auth method. Please use APIKey (string) or AccessToken (string), ExpiresIn (float)')

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
#endregion

class ElvantoAPI(ElvantoAPI):
    class Connection(ElvantoAPI.Connection):
        def getPeople(self):
            result = {}
            def pull(page = 1):
                resp = self._Post("people/getAll", page = page)
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
                if (resp["total"] - (_pageNo-1) * resp["per_page"] - resp["on_this_page"]) > 0:
                    pull(page=_pageNo+1)
            pull()
            self.people = result
            return result

        def findContact(self, first_name: str = None, middle_name: str = None, last_name: str = None, email: str = None, id: str = None, resolve: bool = True):
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

            if not any([first_name,middle_name,last_name,email]):
                raise Exception("No keyword arguments specified")

            result = []
            for id in self.people:
                person = self.people[id]
                if all([(first_name.lower() in person["first_name"].lower() if first_name else True), (middle_name.lower() in person["middle_name"].lower() if middle_name else True), (last_name.lower() in person["last_name"].lower() if last_name else True), (email.lower() in person["email"].lower() if email else True)]):
                    if resolve:
                        _person = person
                        _person["id"] = id
                    result.append(_person if resolve else id)
            return result

import datetime

class Helpers:
    @staticmethod
    def NextDate(day: int):
        date_today = datetime.date.today()
        date_next = date_today + datetime.timedelta((day - date_today.weekday()) % 7)
        return date_next

    @staticmethod
    def ServicesOnDate(api: ElvantoAPI.Connection, date_service: datetime.datetime, fields=["plans", "volunteers", "songs"]):
        """
        API Request :: services/getAll
        start | YYYY-MM-DD
        end   | YYYY-MM-DD
        page_size | int | minimum page size is 10
        """
        services = api._Post("services/getAll", page_size=10, start=str(date_service - datetime.timedelta(1)),
                             end=str(date_service + datetime.timedelta(1)), fields=fields)
        return services["services"]["service"]

    @staticmethod
    def ParseServices(services: list):
        return [Helpers.ParseService(service) for service in services]

    @staticmethod
    def ParseService(service: dict):
        newService = {
            "id": service["id"],
            "name": service["name"],
            "date": service["date"],
            "service_type": {
                "id": service["service_type"]["id"],
                "name": service["service_type"]["name"]
            }
        }
        if "plan" in service:
            newService["plan"] = service["plans"]["plan"][0]
        if "songs" in service:
            newService["songs"] = service["songs"]
        if "volunteers" in service:
            volunteers = []
            for role in service["volunteers"]["plan"][0]["positions"]["position"]:
                if role["volunteers"]: # Check if people are assigned to this role
                    roleDict = {
                        "position_name": role["position_name"],
                        "department_name": role["department_name"],
                        "sub_department_name": role["sub_department_name"],
                        "volunteers": {}
                    }
                    for volunteer in role["volunteers"]["volunteer"]:
                        roleDict["volunteers"][volunteer["person"]["id"]] = {
                            "first_name": volunteer["person"]["preferred_name"] or volunteer["person"]["first_name"],
                            "middle_name": volunteer["person"]["middle_name"],
                            "last_name": volunteer["person"]["lastname"],
                            "status": volunteer["status"]
                        }
                    volunteers.append(roleDict)
            newService["volunteers"] = volunteers
        return newService

class Enums:
    class Days:
        MONDAY = 0
        TUESDAY = 1
        WEDNESDAY = 2
        THURSDAY = 3
        FRIDAY = 4
        SATURDAY = 5
        SUNDAY = 6
