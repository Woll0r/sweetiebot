from utils import botcmd, logerrors
from sleekxmpp import JID
from datetime import datetime
import logging

log = logging.getLogger(__name__)

class SweetieSeen:
    def __init__(self, bot, store):
        self.bot = bot
        self.store = store
        self.bot.add_presence_handler(self.on_presence)
        self.bot.add_message_handler(self.on_message)
        self.bot.load_commands_from(self)
        self.date_format = '%Y-%m-%d %H:%M'

    def timestamp(self):
        return datetime.now().strftime(self.date_format)

    def set(self, prefix, name, response):
        if name is None or response is None:
            # TODO: find out why we hit this branch
            log.warning('skipping setting {} to {}'.format(name, response))
            return
        log.debug('setting {} {} to {}'.format(prefix, name, response))
        self.store.set(prefix+':'+name, response)

    def on_presence(self, presence):
        log.debug('recieved presence: {} from {}'.format(presence.presence_type,
                                                         presence.user_jid))
        user = presence.user_jid.bare
        nickname = presence.muc_jid.resource
        if presence.presence_type == 'unavailable':
            response = self.timestamp()
            self.set('seen', user, response)
            self.set('seen', nickname, response)

    def on_message(self, message):
        if message.is_pm: return

        response = self.timestamp()
        nickname = message.sender_nick
        user = message.user_jid.bare
        self.set('spoke', nickname, response)
        self.set('spoke', user, response)

    @botcmd
    @logerrors
    def seen(self, message):
        '''[nick/jid] Report when a user was last seen'''

        # TODO: I'm not totally convinced about the logic around jidtarget/
        # other if statements below.
        if not message.nick_reason:
            return "A nickname or jid must be provided"
        nick,reason = message.nick_reason
        if reason:
            log.warning("Wasn't expecting to get a reason in !seen: %r", message.nick_reason)

        jidtarget = JID(self.bot.get_jid_from_nick(nick)).bare
        target = jidtarget or nick

        seen = self.store.get('seen:'+target)
        spoke = self.store.get('spoke:'+target)

        now = datetime.now()

        if jidtarget and self.bot.jid_is_in_room(jidtarget) and spoke:
            spoke = spoke.decode('utf-8').strip()
            spokedate = datetime.strptime(spoke, self.date_format)
            ago = self.get_time_ago(now, spokedate)
            return '{} last seen speaking at {} ({})'.format(nick, spoke, ago)
        elif seen:
            seen = seen.decode('utf-8').strip()
            seendate = datetime.strptime(seen, self.date_format)
            ago = self.get_time_ago(now, seendate)
            return '{} last seen in room at {} ({})'.format(nick, seen, ago)
        else:
            return "No records found for user '{}'".format(nick)

    def get_time_ago(self, now, past):
        td = now - past
        if td.total_seconds() < 0: return 'in the future'
        days = td.days
        hours, remainder = divmod(td.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return '{}d {}h {}m {}s ago'.format(days, hours, minutes, seconds)



