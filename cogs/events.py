import asyncio
import datetime
import json

import discord
import time
from discord.ext import commands
from utils import permissions, BugLog, Util
from utils.Converters import Event


class EventsCog:
    """This cog includes all the features of the modlog"""
    def __init__(self, bot):
        self.bot:commands.Bot = bot
        self.events = dict()
        self.eventChannels = dict()
        bot.DBC.query("SELECT * FROM events WHERE started = 1 AND ended = 0")
        events = bot.DBC.fetch_rows()
        for e in events:
            event = Event().convert2(bot, e['ID'])
            self.events[event['name']] = event
            for name, c in event["channels"].items():
                self.eventChannels[name] = c
        bot.loop.create_task(eventsChecker(self))
        self.active = True

    def __unload(self):
        self.active = False #mark as terminated for the checking loop to terminate cleanly

    async def __local_check(self, ctx:commands.Context):
        return await permissions.hasPermission(ctx, "events")

    @commands.group(name='event')
    async def eventCommand(self, ctx: commands.Context):
        """Allows to manage events"""
        if ctx.invoked_subcommand is None:
            await ctx.send("TODO: add explanations")

    @eventCommand.command()
    async def create(self, ctx: commands.Context, name: str, duration: int, durationtype: str):
        """Creates a new event"""
        duration = Util.convertToSeconds(duration, durationtype)
        dbc = self.bot.DBC
        name = dbc.escape(name)
        dbc.query('INSERT INTO events (name, duration) VALUES ("%s", %d)' % (name, duration))
        id = dbc.connection.insert_id()
        await ctx.send(f"Event `{name}` created with ID `{id}`")

    @eventCommand.command()
    async def info(self, ctx: commands.Context, event:Event):
        info = ""
        for key, item in event.items():
            info = f"{info}\n{key}: {item}"
        await ctx.send(info)

    @eventCommand.command()
    async def setDuration(self, ctx: commands.Context, event: Event, duration: int, durationtype: str, closingtime: int, closingtimetype: str):
        newDuration = Util.convertToSeconds(duration, durationtype)
        newClosing = Util.convertToSeconds(closingtime, closingtimetype)
        dbc = self.bot.DBC
        dbc.query('UPDATE events set duration=%d, closingTime=%d WHERE ID=%d' % (newDuration, newClosing, event["ID"]))
        await ctx.send(f"Event {event['name']} duration is now {duration} {durationtype} and submissions will be closed {closingtime} {closingtimetype} in advance")

    @eventCommand.command()
    async def start(self, ctx: commands.Context, event: Event):
        dbc = self.bot.DBC
        dbc.query('UPDATE events set started=1, endtime=%s WHERE ID=%d' % (time.time() + event["duration"], event["ID"]))
        event = await Event().convert(ctx, event['ID'])
        for name, c in event["channels"].items():
            channel:discord.TextChannel = self.bot.get_channel(c["channel"])
            everyone = None
            for role in channel.guild.roles:
                if role.id == channel.guild.id:
                    everyone = role
                    break
            type = c["type"]
            if type == 0:
                await channel.set_permissions(everyone, read_messages=True)
            elif type == 1 or type == 2:
                await channel.set_permissions(everyone, read_messages=True, send_messages=True)
            self.eventChannels[name] = c
        self.events[event['name']] = event
        await ctx.send(f"{event['name']} has been started!")
        await self.updateScoreboard('testEvent')

    @eventCommand.command()
    async def addChannel(self, ctx: commands.Context, event:Event, channel: discord.TextChannel, codename: str, type: int):
        self.bot.DBC.query("INSERT INTO eventchannels (channel, event, type, name) VALUES (%d, %d, %d, '%s')" % (channel.id, event["ID"], type, codename))
        await ctx.send("Channel assigned")

    positiveID = 418865687365287956
    negativeID = 418865725449437205

    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user:
            return
        if "hugSubmissions" in self.eventChannels and (message.channel.id == self.eventChannels["hugSubmissions"]["channel"] or message.channel.id == self.eventChannels["fightSubmissions"]["channel"]):
            if not '{0}' in message.content or not '{1}' in message.content:
                reply = await message.channel.send(f"{message.author.mention}: Invalid submission, please make sure it contains both ` {0} ` and ` {1} `")
                await asyncio.sleep(10)
                await message.delete()
                await reply.delete()
            else:
                content = self.bot.DBC.escape(message.content)
                positive = None
                negative = None
                for emoji in self.bot.emojis:
                    if emoji.id == self.positiveID:
                        positive = emoji
                    elif emoji.id == self.negativeID:
                        negative = emoji
                await message.add_reaction(positive)
                await message.add_reaction(negative)

                eventID = self.events['testEvent']["ID"]
                self.bot.DBC.query("INSERT INTO submissions (event, user, submission) VALUES (%d, %d, '%s')" % (eventID, message.author.id, content))

    async def on_raw_reaction_add(self, emoji: discord.PartialEmoji, message_id, channel_id, user_id):
        message: discord.Message = await self.bot.get_channel(channel_id).get_message(message_id)
        if "hugSubmissions" in self.eventChannels and (message.channel.id == self.eventChannels["hugSubmissions"]["channel"] or message.channel.id == self.eventChannels["fightSubmissions"]["channel"]):
            positiveCount = 0
            negativeCount = 0
            for reaction in message.reactions:
                async for user in reaction.users():
                    if user == message.author:
                        await message.remove_reaction(reaction.emoji, message.author)
                        reply = await message.channel.send(f"Voting on your own submission is not allowed {message.author.mention}!")
                        await asyncio.sleep(10)
                        await reply.delete()
                if reaction.emoji.id == self.positiveID:
                    positiveCount = reaction.count
                elif reaction.emoji.id == self.negativeID:
                    negativeCount = reaction.count
            if negativeCount > 2:
                try:
                    await message.author.send(f"I'm sorry but the folowing submission has been denied:```\n{message.content}```")
                except Exception as e:
                    #user probably doesn't allow DMs
                    pass
                await message.delete()
            elif positiveCount > 2:
                content = self.bot.DBC.escape(message.content)
                eventID = self.events['testEvent']["ID"]
                self.bot.DBC.query("UPDATE submissions SET points=1 WHERE event=%d AND user=%d AND submission='%s'" % (eventID, message.author.id, content))
                if message.channel.id == self.eventChannels["hugSubmissions"]["channel"]:
                    self.bot.DBC.query('INSERT INTO hugs (hug, author) VALUES ("%s", "%d")' % (content, message.author.id))
                    await BugLog.logToBotlog(message=f"New hug added: ```\n ID: {self.bot.DBC.connection.insert_id()}\nText: {content}\nAuthor: {message.author.name}#{message.author.discriminator}```")
                    try:
                        await message.author.send(f"Congratulation, your hug sugestion ```{content}``` has been added to the list!")
                    except Exception:
                        pass
                elif message.channel.id == self.eventChannels["fightSubmissions"]["channel"]:
                    self.bot.DBC.query('INSERT INTO fights (fight, author) VALUES ("%s", "%d")' % (content, message.author.id))
                    await BugLog.logToBotlog(message=f"New fight added: ```\n ID: {self.bot.DBC.connection.insert_id()}\nText: {content}\nAuthor: {message.author.name}#{message.author.discriminator}```")
                    try:
                        await message.author.send(f"Congratulation, your fight sugestion ```{content}``` has been added to the list!")
                    except Exception:
                        pass
                await self.updateScoreboard('testEvent')
                await message.delete()


    async def updateScoreboard(self, event):
        self.bot.DBC.query('SELECT count(*) as score, user  from submissions WHERE event = %d GROUP BY user ORDER BY score' % (self.events[event]["ID"]))
        top = self.bot.DBC.fetch_rows()[:5]
        desc = ""
        count = 1
        for entry in top:
            desc = f"{desc}\n{count}: <@{entry['user']} ({entry['score']})>"
        if len(desc) == 0:
            desc = "No participants so far :disappointed: "
        embed = discord.Embed(title=f"{event} leaderboard", colour=discord.Colour(0xfe9d3d),
                              description=desc,
                              timestamp=datetime.datetime.utcfromtimestamp(1520015991))
        if self.events[event]["leaderboard"] is None:
            message = await self.bot.get_channel(int(self.bot.config["Events"]["scoreboardChannel"])).send(embed=embed)
            self.bot.DBC.query(
                'UPDATE events SET leaderboard=%d WHERE ID = %d' % (
                message.id, self.events[event]["ID"]))
            self.events[event]["leaderboard"] = message.id
        else:
            message:discord.Message = await self.bot.get_channel(int(self.bot.config["Events"]["scoreboardChannel"])).get_message(self.events[event]["leaderboard"])
            message.edit(embed=embed)






def setup(bot):
    bot.add_cog(EventsCog(bot))


async def eventsChecker(cog: EventsCog):
    await cog.bot.wait_until_ready()
    while not cog.bot.is_closed():
        now = time.time()
        ended = []
        for name, event in cog.events.items():
            if now > event["endtime"]:
                ended.append(event)
            if now > event["closingTime"]:
                for name, c in event["channels"].items():
                    channel:discord.TextChannel = cog.bot.get_channel(c["channel"])
                    everyone = None
                    for role in channel.guild.roles:
                        if role.id == channel.guild.id:
                            everyone = role
                            break
                    if c["type"] == 1:
                        await channel.set_permissions(everyone, send_messages=False)
        for event in ended:
            for name, c in event["channels"].items():
                channel: discord.TextChannel = cog.bot.get_channel(c["channel"])
                everyone = None
                for role in channel.guild.roles:
                    if role.id == channel.guild.id:
                        everyone = role
                        break
                if c["type"] == 2:
                    await channel.set_permissions(everyone, send_messages=False)
                if c["type"] == 0 or c["type"] == 1:
                    await channel.set_permissions(everyone, read_messages=False)
            cog.bot.DBC.query(f"UPDATE events SET ended = 1 WHERE ID = {event['ID']}")
            del cog.events[event["name"]]
            await BugLog.logToBotlog("event ended")
        await asyncio.sleep(5)