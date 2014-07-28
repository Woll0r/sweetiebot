from modules.Message import Message
import logging
from utils import logerrors
from sleekxmpp import ClientXMPP
from sleekxmpp.xmlstream.jid import JID

log = logging.getLogger(__name__)

class RestartException(Exception):
    pass

class MessageProcessor(object):

    def __init__(self, unknown_command_callback):
        self.commands = {}
        self.unknown_command_callback = unknown_command_callback

    def add_command(self, command_name, command_callback):
        self.commands[command_name] = command_callback

    @logerrors
    def process_message(self, message):
        if message.command is not None:
            if message.command in self.commands:
                log.debug('running command '+message.command)
                return self.commands[message.command](message)

        if self.unknown_command_callback is not None:
            return self.unknown_command_callback(message)

class MUCJabberBot():

    def __init__(self, jid, password, room, nick):
        print('creating bot with {} {} {} {} '.format(jid, password, room, nick))
        self.nick = nick
        self.room = room
        self.jid = JID(jid)

        bot = ClientXMPP(jid, password)

        bot.add_event_handler('session_start', self.on_start)
        bot.add_event_handler('message', self.on_message)

        bot.register_plugin('xep_0045')
        self._muc = bot.plugin['xep_0045']
        bot.register_plugin('xep_0199')
        bot.plugin['xep_0199'].enable_keepalive(30, 30)

        self.unknown_command_callback = None

        def on_unknown_callback(message):
            if self.unknown_command_callback is not None:
                return self.unknown_command_callback(message)
        self.message_processor = MessageProcessor(on_unknown_callback)

        print('sb connect')
        if bot.connect():
            print('sb process')
            bot.process()
        else:
            raise 'could not connect'

        self._bot = bot

    def disconnect(self):
        self._bot.disconnect()

    def on_start(self, event):
        print('sb on_start')
        self._bot.get_roster()
        self._bot.send_presence()
        print('sb join {} as {}'.format(self.room, self.nick))
        self._muc.joinMUC(self.room, self.nick, wait=True)

    def send_groupchat_message(self, message, room=None):
        room = room or self.room
        self._bot.send_message(mto=self.room, mbody=message, mhtml=message, mtype='groupchat')

    @logerrors
    def on_message(self, message_stanza):

        if message_stanza['type'] == 'error':
            print('\n\nerror!\n\n')
            log.error(message_stanza)

        body = message_stanza['body']
        if not body:
            log.warn('apparently empty message [no body] %s', message_stanza)
            return

        #print('##')
        #print('keys: {}'.format(message_stanza.keys()))
        #print('xml: {}'.format(message_stanza.xml))
        #print('type: {}'.format(message_stanza['type']))

        #props = mess.getProperties()
        jid = message_stanza['from']

#        if xmpp.NS_DELAY in props:
#            # delayed messages are history from before we joined the chat
#            return

        log.debug('comparing jid {} against message from {}'.format(
            self.jid, jid))
        if self.jid.bare == jid.bare:
            log.debug('ignoring from jid')
            return

        #print('checking for subject {}'.format(message_stanza['subject']))
        if message_stanza['subject']:
            log.debug('ignoring subject..')
            return

        if message_stanza['mucnick']:
            sender_nick = message_stanza['mucnick']
            user_jid = self.get_jid_from_nick(sender_nick)
        else:
            user_jid = jid
            sender_nick = self.get_nick_from_jid(user_jid)
        user_jid = JID(user_jid).bare

        if sender_nick == self.nick:
            log.debug('ignoring from nickname')
            return

        is_pm = message_stanza['type'] == 'chat'
        message_html = str(message_stanza['html']['body'])
        message = message_stanza['body']
        print(str(type(Message)))
        parsed_message = Message(self.nick, sender_nick, jid, user_jid, message,
                                 message_html, is_pm)

        reply = self.message_processor.process_message(parsed_message)
        if reply:
            if is_pm: self.send_pm_to_jid(jid, reply)
            else: self.send_groupchat_message(reply)

    def send_pm_to_jid(self, jid, pm):
        print('sending {} to {}'.format(pm, jid))
        self._bot.send_message(mto=jid, mbody=pm)

    def get_jid_from_nick(self, nick):
        return self._muc.getJidProperty(self.room, nick, 'jid').bare

    def get_nick_from_jid(self, jid):
        room_details = self._muc.rooms[self.room]
        log.debug('room details '+str(room_details))
        for nick, props in room_details.items():
            if JID(props['jid']).bare == JID(jid).bare:
                return nick

    def load_commands_from(self, target):
        import inspect
        for name, value in inspect.getmembers(target, inspect.ismethod):
            if getattr(value, '_bot_command', False):
                name = getattr(value, '_bot_command_name')
                log.info('Registered command: %s' % name)
                self.message_processor.add_command(name, value)

    def on_ping_timeout(self):
        log.error('ping timeout.')
        raise RestartException()

    def create_iq(self, id, type, xml):
        iq = self._bot.make_iq(id=id, ifrom=self.jid, ito=self.room, itype=type)
        iq.set_payload(xml)
        return iq



