from modules.controller import *
from comba_lib.base.combabase import CombaBase
import threading
import zmq
import sys
import time
import zmq.auth
import redis
import random
import string
from zmq.auth.thread import ThreadAuthenticator
from threading import Event

class CombaZMQAdapter(threading.Thread, CombaBase):
    
    def __init__(self, port):

        self.port = str(port)
        threading.Thread.__init__ (self)
        self.shutdown_event = Event()
        self.context = zmq.Context().instance()
        self.authserver = ThreadAuthenticator(self.context)
        self.loadConfig()
        self.start()

    #------------------------------------------------------------------------------------------#
    def run(self):
        """
        run runs on function start
        """

        self.startAuthserver()
        self.data = ''
        self.socket = self.context.socket(zmq.REP)
        self.socket.plain_server = True
        self.socket.bind("tcp://*:"+self.port)
        self.shutdown_event.clear()
        self.controller = CombaController(self, self.lqs_socket, self.lqs_recorder_socket)
        self.controller.messenger.setMailAddresses(self.get('frommail'), self.get('adminmail'))
        self.can_send = False
        # Process tasks forever
        while not self.shutdown_event.is_set():
            self.data = self.socket.recv()
            self.can_send = True
            data = self.data.split(' ')
            command = str(data.pop(0)) 
            params = "()" if len(data) < 1 else  "('" + "','".join(data) + "')" 
                     
            try: 
                exec"a=self.controller." + command + params  
            
            except SyntaxError:                
                self.controller.message('Warning: Syntax Error')

            except AttributeError:
                print "Warning: Method " + command + " does not exist"
                self.controller.message('Warning: Method ' + command + ' does not exist')
            except TypeError:
                print "Warning: Wrong number of params"
                self.controller.message('Warning: Wrong number of params')
            except:
                print "Warning: Unknown Error"
                self.controller.message('Warning: Unknown Error')

        return

    #------------------------------------------------------------------------------------------#
    def halt(self):
        """
        Stop the server
        """
        if self.shutdown_event.is_set():
            return
        try:
            del self.controller
        except:
            pass
        self.shutdown_event.set()
        result = 'failed'
        try:
            result = self.socket.unbind("tcp://*:"+self.port)
        except:
            pass
        #self.socket.close()

    #------------------------------------------------------------------------------------------#
    def reload(self):
        """
        stop, reload config and startagaing
        """
        if self.shutdown_event.is_set():
            return
        self.loadConfig()
        self.halt()
        time.sleep(3)
        self.run()

    #------------------------------------------------------------------------------------------#
    def send(self,message):
        """
        Send a message to the client
        :param message: string
        """
        if self.can_send:
            self.socket.send(message)
            self.can_send = False

    #------------------------------------------------------------------------------------------#
    def startAuthserver(self):
        """
        Start zmq authentification server
        """
        # stop auth server if running
        if self.authserver.is_alive():
            self.authserver.stop()
        if self.securitylevel > 0:
            # Authentifizierungsserver starten.

            self.authserver.start()

            # Bei security level 2 auch passwort und usernamen verlangen
            if self.securitylevel > 1:
                try:

                    addresses = CombaWhitelist().getList()
                    for address in addresses:
                        self.authserver.allow(address)

                except:
                    pass

            # Instruct authenticator to handle PLAIN requests
            self.authserver.configure_plain(domain='*', passwords=self.getAccounts())

    #------------------------------------------------------------------------------------------#
    def getAccounts(self):
        """
        Get accounts from redis db
        :return: llist - a list of accounts
        """
        accounts = CombaUser().getLogins()
        db = redis.Redis()

        internaccount = db.get('internAccess')
        if not internaccount:
            user = ''.join(random.sample(string.lowercase,10))
            password = ''.join(random.sample(string.lowercase+string.uppercase+string.digits,22))
            db.set('internAccess', user + ':' + password)
            intern = [user, password]
        else:
            intern =  internaccount.split(':')

        accounts[intern[0]] = intern[1]

        return accounts
