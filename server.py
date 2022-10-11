import asyncio
import sys
import logging
import json
import aiohttp
import time

MAPS_API_KEY = '' #enter your google maps API key here
MAPS_API_URL = 'https://maps.googleapis.com/maps/api/place/nearbysearch/json'
ADDRESS = '127.0.0.1' #standard address for IPv4 loopback traffic

#Ports assigned to 5-161: 12331 to 12335
SERVER_PORTS = {
    "Bernard": 12331,
    "Clark": 12332,
    "Jaquez": 12333,
    "Johnson": 12334,
    "Juzang": 12335
}

RELATIONS = {
    "Bernard": ["Jaquez", "Johnson", "Juzang"],
    "Clark": ["Jaquez", "Juzang"],
    "Jaquez": ["Bernard", "Clark"],
    "Johnson": ["Bernard", "Juzang"],
    "Juzang": ["Bernard", "Clark", "Johnson"]
}

def log(txt):
    logging.info(txt)

class Server:
    def __init__(self, name):
        self.name = name
        self.adjacent = RELATIONS[name]
        self.port = SERVER_PORTS[name]
        self.clients = {}

    async def flood(self, response):
        for server in self.adjacent:
            try: 
                reader, writer = await asyncio.open_connection(ADDRESS, SERVER_PORTS[server])
                log("Connected to " + server + "\nSending: " + response + "\n")
                writer.write(response.encode())
                await writer.drain()
                writer.close()
                await writer.wait_closed()
            except: 
                #print("Unable to connect to: "+ server)
                log("Unable to connect to: "+ server + "\n")

    async def client_callback(self, reader, writer):
        data = await reader.read(1000000)
        command = data.decode()

        log("Recieved: " + command)
        #print(command)
        write = True
        query = command.split()
        if(query):
            if query[0] == "WHATSAT" and self.valid_WHATSAT(command):
                usr = query[1]
                radius = float(query[2]) * 1000 #km to m for google API
                limit = int(query[3])
                location = self.extract_coords(self.clients[usr].split()[4])
                formated_location = str(location[0]) + "," + str(location[1])
                payload = await self.google_query(formated_location, str(radius))
                tmp = json.loads(payload)
                if len(tmp["results"]) > limit:
                    tmp["results"] = tmp["results"][:limit]
                    final = json.dumps(tmp, indent=4).rstrip()
                else:
                    final = payload
                split_arr = (self.clients[usr] + final).split("\n")
                while "" in split_arr:
                    split_arr.remove("")
                log("Queried Google API\n")
                ret = '\n'.join(split_arr) + "\n\n"
            elif query[0] == "IAMAT" and self.valid_IAMAT(command):
                usr = query[1]
                coords = query[2]
                dt = time.time() - float(query[3])
                delta_t = ""
                if dt > 0:
                    delta_t = '+' + str(dt)
                else: 
                    delta_t = '-' + str(dt)
                ret = "AT " + self.name + " " + delta_t + " " + usr + " " + coords + " " + query[3] + "\n"
                self.clients[usr] = ret
                await self.flood(ret)
            elif query[0] == "AT": #to handle flooding
                usr = query[3]
                if usr in self.clients:
                    if command != self.clients[usr]:
                        self.clients[usr] = command
                else:
                    self.clients[usr] = command
                    await self.flood(command)
                write = False
            else: 
                ret = '? ' + command
        if write:
            writer.write(ret.encode())
            await writer.drain()
            log("Closed the connection with client")
            writer.close()
        else:
            log("Closed the connection with client")
            writer.close()

    #general idea: https://www.programcreek.com/python/example/81575/asyncio.start_server & https://docs.python.org/3/library/asyncio-stream.html
    async def run(self): 
        log('Server ' + sys.argv[1] + " has started running ")
        server = await asyncio.start_server(self.client_callback, ADDRESS, self.port)
        async with server:
            await server.serve_forever()

    def extract_coords(self, coords):
        if coords[0] == '+':
            if coords.find('-') != -1:
                lat = coords[0:coords.find('-')]
                lng = coords[coords.find('-'):]
            else:
                lat = coords[0:coords[1:].find('+')]
                lng = coords[coords[1:].find('+')+1:]
        else:
            if coords[1:].find('-') != -1:
                lat = coords[0:coords[1:].find('-')]
                lng = coords[coords[1:].find('-')+1:]
            else:
                lat = coords[0:coords[1:].find('+')]
                lng = coords[coords[1:].find('+')+1:]
        return [float(lat), float(lng)]


    def valid_IAMAT(self, command):
        query = command.split()
        if len(query) != 4:
            return False
        coords = query[2]
        if (coords.count('+') + coords.count('-')) != 2:
            return False
        try:
            combo = self.extract_coords(coords)
            float(query[3])
        except:
            return False
        lat = combo[0]
        lng = combo[1]
        if lat > 90 or lat < -90 or lng > 180 or lng < -180:
            return False
        return True


    def valid_WHATSAT(self, command):
        query = command.split()
        if len(query) != 4 or not query[1] in self.clients:
            return False
        try:
            rad = float(query[2])
            limit = int(query[3])
        except:
            return False
        if rad > 50 or rad < 0:
            return False
        if limit > 20 or limit < 1:
            return False
        return True


    async def google_query(self, location, radius): 
        request = MAPS_API_URL + "?&location=" + location + "&radius=" + radius + "&key=" + MAPS_API_KEY
        async with aiohttp.ClientSession() as session:
            async with session.get(request) as response:
                html = await response.text()
                return html


def verify_args(arg):
	if len(arg) != 2:
		print("Must have one argument:\n\tJaquez / Juzang / Bernard / Clark / Johnson\n", file=sys.stderr)
		sys.exit(1)

	if arg[1] not in RELATIONS:
		print("Argument must be:\n\tJaquez / Juzang / Bernard / Clark / Johnson\n", file=sys.stderr) 
		sys.exit(1)


def main():
    verify_args(sys.argv) #checks input
    logging.basicConfig(filename=sys.argv[1] + "-log.txt", encoding='utf-8', format='%(asctime)s %(message)s', filemode='w', level=logging.INFO)
    server = Server(sys.argv[1])
    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        log("Server closed via KeyboardInterrupt")


if __name__ == '__main__':
    main()
