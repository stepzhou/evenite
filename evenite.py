import sys
import os.path
import urlparse
import urllib
import urllib2
import webbrowser
import json
import BaseHTTPServer
import facebook
import settings

ACCESS_TOKEN = None

class FBAuth(object):
    """
    Authenticates FB account
    """

    # Enter FB app credentials
    APP_ID = settings.APP_ID
    APP_SECRET = settings.APP_SECRET
    REDIRECT_URI = 'http://127.0.0.1:8080/'
    LOCAL_FILE = '.fb_access_token'
    PERMS = ['create_event', 'user_events', 'read_friendlists']

    def authenticate(self):
        """
        Facebook authentication. Opens a browser window for authentication if
        there isn't a LOCAL_FILE with the access_token, else it uses the
        access_token in LOCAL_FILE.
        """
        global ACCESS_TOKEN
        self.access_token = None
        if not os.path.exists(self.LOCAL_FILE):
            print "Facebook authentication..."
            webbrowser.open(facebook.auth_url(self.APP_ID, self.REDIRECT_URI,
                self.PERMS))
            # Creates a temp HTTPServer
            httpd = BaseHTTPServer.HTTPServer(('127.0.0.1', 8080),
                FBAuth.RequestHandler)
            while ACCESS_TOKEN is None:
                httpd.handle_request()
            self.access_token = ACCESS_TOKEN
        else:
            self.access_token = open(self.LOCAL_FILE).read()

    def init_graph(self):
        """
        Constructs a Facebook GraphAPI object for query uses.
        """
        self.graph = facebook.GraphAPI(access_token=self.access_token)
        me = self.graph.request('/me')
        self.username = me['name']
        self.id = me['id']

    class RequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
        """
        Simple HTTPServer that handles the URL parameters passed back to the
        REDIRECT_URI by the Facebook API.
        """

        def set_token(self, access_token=None):
            self.access_token = access_token

        def do_GET(self):
            global ACCESS_TOKEN
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            code = urlparse.parse_qs(urlparse.urlparse(self.path).query).get('code')
            code = code[0] if code else None
            if code is None:
                self.wfile.write("Sorry, authentication failed.")
                sys.exit(1)
            ACCESS_TOKEN = facebook.get_access_token_from_code(code,
                FBAuth.REDIRECT_URI, FBAuth.APP_ID, FBAuth.APP_SECRET)['access_token']
            open(FBAuth.LOCAL_FILE,'w').write(ACCESS_TOKEN)
            self.wfile.write("You have successfully logged in to facebook. "
                             "You can close this window now.")

def print_title(num, title):
    # unicode() prevents ASCII/uncode conflicts
    print unicode("\t{} - {}").format(num, title)

def print_param(name, key, data):
    event_format = "\t\t{}: {}"
    if key in data:
        print event_format.format(name, data[key])

def is_number(s):
    try:
        int(s)
        return True
    except ValueError:
        return False

def is_char(s):
    try:
        ord(s)
        return True
    except TypeError:
        return False

class FBMenu(object):
    """
    Controls the logic for the terminal usage.
    """

    def __init__(self):
        self.auth = FBAuth()
        self.auth.authenticate()
        self.auth.init_graph()
        self.event_list = []
        self.friendlist_list = []

        self.PROMPT = self.auth.username + "> "

    def show_events(self):
        """
        Displays recent events that includes you as the owner.
        """
        print "Showing your recent events..."

        # Reset event history
        self.event_list = []
        event_num = 0
        events = self.auth.graph.request('/me/events/')['data']
        for event in events:
            print_title(chr(ord('A') + event_num), event['name'])
            print_param("Start time", 'start_time', event)
            print_param("End time", 'end_time', event)
            print_param("Timezone", 'timezone', event)
            print_param("Location", 'location', event)

            # Build event history
            self.event_list.append(event['id'])
            event_num += 1

    def show_lists(self):
        print "Displaying your friend lists and networks..."

        # Reset friendlist history
        self.friendlist_list = []
        friendlist_num = 0
        friendlists = self.auth.graph.request('/me/friendlists/')['data']
        for f in friendlists:
            friend_count = len(self.auth.graph.request('{}/{}'.format(
                    f['id'], 'members'))['data'])
            print_title(friendlist_num, f['name'] + " - " + str(friend_count))

            # Build friendlist history
            self.friendlist_list.append(f['id'])
            friendlist_num += 1

    def show_list_friends(self, list_id):
        """
        Displays all the people within a certain friend list
        """
        friends = self.auth.graph.request('/{}/{}/'.format(
                self.friendlist_list[list_id], 'members'))['data']
        for friend in friends:
            print "\t" + friend['name']

    def invite(self, event_index, list_index):
        """
        Invites all the people in a certain list to a certain event
        """
        # TODO: Currently will throw exception and fail if user doesn't
        # have invite permissions
        friendlist_id = self.friendlist_list[list_index]
        event_id = self.event_list[event_index]

        friends = self.auth.graph.request('/{}/{}/'.format(
            friendlist_id, 'members'))['data']

        friend_ids = []
        for f in friends:
            friend_ids.append(f['id'])
        # Not used -- if already invited, has response error
        friends_query = ",".join(map(str, friend_ids))

        for i in friend_ids:
            post = {}
            post['users'] = str(i)
            try:
                if self.auth.graph.request(
                    '{}/invited'.format(event_id),post_args=post):
                    print "Invitations succeeded"
                else:
                    print "Invitations failed"
            except facebook.GraphAPIError:
                # GraphAPI #200 error thrown when a person who is already
                # invited is invited again.
                print "Duplicate"

    def help(self):
        print """
            show events
            show lists
            show lists <list-num>
            show all
            invite <event-letter> <list-num>
            exit
        """

    def select(self, command, args):
        """
        Controller
        """
        if command == "show" and args[0] == "events":
            self.show_events()
        elif command == "show" and args[0] == "lists" and len(args) == 1:
            self.show_lists()
        elif (command == "show" and args[0] == "lists" and is_number(args[1]) \
                and int(args[1]) < len(self.friendlist_list)):
            self.show_list_friends(int(args[1]))
        elif (command == "invite" and is_char(args[0]) and \
                ord(args[0]) - ord('A') < len(self.event_list) and \
                is_number(args[1]) and int(args[1]) < len(self.friendlist_list)):
            self.invite(ord(args[0]) - ord('A'), int(args[1]))
        elif command == "show" and args[0] == "all":
            self.show_events()
            self.show_lists()
        elif command == "help":
            self.help()
        elif command == "exit":
            sys.exit()
        else:
            print "Invalid command"

if __name__ == "__main__":
    menu = FBMenu()

    print """
    Welcome to Facebook Evenite!
    Type help for instructions
    """
    try:
        while 1:
            params = raw_input(menu.PROMPT).split(' ')
            command = params[0]
            args = params[1:]
            menu.select(command, args)
    except KeyboardInterrupt:
        print