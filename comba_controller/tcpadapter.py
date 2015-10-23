
import SocketServer
from combacontroller import CombaController

"""
    CombaTCPHandler Class
"""
class CombaTCPAdapter(SocketServer.BaseRequestHandler):
    
    # Constructor
    def __init__(self, request, client_address, server):
        self.lqs_socket = server.lqs_socket
        self.lqs_recorder_socket = server.lqs_recorder_socket
        SocketServer.BaseRequestHandler.__init__(self, request, client_address, server)

    #------------------------------------------------------------------------------------------#
    # Request Handler
    def handle(self):        

        self.data = ''
        self.controller = CombaController(self, self.lqs_socket, self.lqs_recorder_socket)
        while str(self.data).upper() != 'QUIT':
            
            self.data = self.request.recv(1024).strip()
            if self.data == '':
                self.events.run() 
                time.sleep(1)
            elif self.data.upper() == 'QUIT':
                continue    
            else:                
                data = self.data.split(' ')
                command = str(data.pop(0)) 
                params = "()" if len(data) < 1 else  "('" + "','".join(data) + "')" 
                
                try: 
                    exec"a=self.controller." + command + params  
                except SyntaxError:
                    self.data = 'quit'
                    continue
                except AttributeError:                    
                    print "Warning: Method " + command + " does not exist"
                    self.controller.message('Warning: Method ' + command + ' does not exist')
                except TypeError:
                   print "Warning: Wrong number of params"
                   self.controller.message('Warning: Wrong number of params')
        del self.controller                   

    #------------------------------------------------------------------------------------------#
    def send(self,message):
        self.request.sendall(message + "\nEND\n")                   
