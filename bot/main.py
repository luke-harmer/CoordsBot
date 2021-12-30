import os
import re

uri = os.getenv("DATABASE_URL")
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
import discord
from discord import Color
from discord.ext import commands
from sqlalchemy import create_engine
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base


# Database configuration
DATABASE_URL = os.environ['DATABASE_URL']
engine = create_engine(DATABASE_URL)
Base = declarative_base()
Session = sessionmaker(bind=engine)
session = Session()


# Database models
class Alliance(Base):
    __tablename__ = 'alliances'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    members = relationship("Player", back_populates="alliance", order_by="Player.name")

    def __str__(self):
        text = "Alliance: '{}'".format(self.name)
        text += "\n  Members:"
        if not self.members or self.members == []:
            text += "\n    None"
        for member in self.members:
            text += "\n    {}".format(member.name)
        return text

    def as_embed(self):
        embed = discord.Embed(title="**{}**".format(self.name), description="\u200b", color=Color.dark_green())
        text = ""
        if not self.members or self.members == []:
            text += "\n**None**"
        for member in self.members:
            text += "\n{}".format(member.name)
        embed.add_field(name="Members", value=text, inline=False)
        return embed


class Player(Base):
    __tablename__ = 'players'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    alliance_id = Column(Integer, ForeignKey('alliances.id'), nullable=True)
    alliance = relationship("Alliance", back_populates="members")
    wsa = Column(String(11), nullable=True)
    planets = relationship("Planet", back_populates="player", order_by="Planet.order_key")

    def __str__(self):
        text = "Player: '{}'".format(self.name)
        text += "\n  Alliance: '{}'".format(self.alliance.name) if self.alliance else ""
        text += "\n  WSA: {}".format(self.wsa) if self.wsa else ""
        text += "\n  Planets:"
        if not self.planets or self.planets == []:
            text += "\n    None"
        for planet in self.planets:
            text += "\n    {}".format(planet)
        return text

    def as_embed(self):
        embed = discord.Embed(title="**{}**".format(self.name), description="\u200b", color=Color.dark_red())
        if self.alliance:
            embed.add_field(name="Alliance", value=self.alliance.name, inline=True)
        if self.wsa:
            embed.add_field(name="WSA:", value=self.wsa, inline=True)
        text = ""
        if not self.planets or self.planets == []:
            text += "\n**None**"
        for planet in self.planets:
            text += "\n{}".format(planet)
        embed.add_field(name="Planets", value=text, inline=False)
        return embed


class Planet(Base):
    __tablename__ = 'planets'

    id = Column(Integer, primary_key=True)
    order_key = Column(String)
    nice_coords = Column(String)
    moon = Column(Integer, nullable=True)
    player_id = Column(Integer, ForeignKey('players.id'))
    player = relationship("Player", back_populates="planets")

    def __str__(self):
        text = self.nice_coords
        if self.moon:
            text += " - Moon: {}".format(self.moon)
        return text


# Creates database tables if they don't exists
Base.metadata.create_all(engine)


# Helper functions
def niceKey(galaxy: int, system: int, planet: int):
    return str(galaxy) + ":" + str(system) + ":" + str(planet)


def orderKey(galaxy: int, system: int, planet: int):
    return str(galaxy).rjust(3, '0') + str(system).rjust(3, '0') + str(planet).rjust(3, '0')


def getAlliance(name: str):
    alliance_ = session.query(Alliance).filter(Alliance.name == name).all()
    if not alliance_:
        return Alliance(name=name)
    else:
        return alliance_[0]


def getPlayer(playername: str):
    player = session.query(Player).filter(Player.name == playername).all()
    if not player:
        return Player(name=playername)
    else:
        return player[0]


def getPlanet(galaxy: int, system: int, planet: int, moon: int = None):
    key = orderKey(galaxy, system, planet)
    nicekey = niceKey(galaxy, system, planet)
    planet = session.query(Planet).filter(Planet.order_key == key).all()
    if not planet:
        return Planet(order_key=key, nice_coords=nicekey, moon=moon)
    else:
        if moon:
            planet[0].moon = moon
        return planet[0]


# Bot config
token = os.getenv('DISCORD_TOKEN')
bot = commands.Bot(command_prefix='!', case_insensitive=True)
bot.load_extension("cogs.error_handler")


# Bot commands
@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------')


@bot.command(name='info', brief='Info about the bot')
async def info(ctx):
    player_count = session.query(Player).count()
    planet_count = session.query(Planet).count()
    embed = discord.Embed(title="CoordsBot",
                          description="A bot for storing and retrieving game data",
                          color=Color.dark_gold())
    embed.add_field(name="Author", value="Caerisse")
    embed.add_field(name="Saved players count", value=str(player_count))
    embed.add_field(name="Saved planets count", value=str(planet_count))
    await ctx.send(embed=embed)


@bot.command(name='test',
             brief='Test brief',
             help='Test help message',
             description='Test command description',
             aliases=['test1', 'test2'])
async def test(ctx):
    response = '```Test response, stop bothering```'
    await ctx.send(response)


@bot.command(name='link',
             brief='https://coordsbot.herokuapp.com/',
             help='follow the link to start the bot again',
             description='link to heroku app')
async def link(ctx):
    response = '```https://coordsbot.herokuapp.com/```'
    await ctx.send(response)


@bot.command(name='add',
             brief='Add planets to database',
             help='PlayerName Galaxy System Planet and MoonSize must have a space between them'
                  '\nMoonSize can be omitted'
                  '\nCan be used to add MoonSize to an already saved planet without that information',
             description='Add or update planets to database under a player name',
             aliases=['post', 'save', 'update'],
             usage='playername 2 123 5 9400')
async def add(ctx, playername: str, galaxy: int, system: int, planet: int, moon: int = None):
    playername = playername.lower()
    player = getPlayer(playername)
    planet_ = getPlanet(galaxy, system, planet, moon)
    planet_.player = player
    session.add(player)
    session.add(planet_)
    session.commit()
    response = '```Added planet {} to {} planets```'.format(planet_, playername)
    await ctx.send(response) 


@bot.command(name='delete',
             brief='Delete planets from database',
             help='PlayerName Galaxy System and Planet must have a space between them',
             description='Delete a planet of a given player',
             usage='playername 2 123 5')
async def delete(ctx, playername: str, galaxy: int, system: int, planet: int):
    playername = playername.lower()
    player = getPlayer(playername)
    planet_ = getPlanet(galaxy, system, planet)
    if planet_ in player.planets:
        response = '```Deleted planet {} in {} planets```'.format(planet_, playername)
        session.delete(planet_)
        session.commit()
    else:
        response = "```{} didn't have planet {}```".format(playername, planet_)
    await ctx.send(response) 


@bot.command(name='get',
             brief='Display all data of a player',
             help='Retrieves all the saved information of the given player name',
             description='Display all data of a player',
             aliases=['coords', 'view'],
             usage='playername')
async def get(ctx, playername):
    playername = playername.lower()
    playername = playername.lower()
    player = getPlayer(playername)
    await ctx.send(embed=player.as_embed())


@bot.command(name='alliance',
             brief='Associates a player to an alliance',
             help='Be careful of typing the alliance name correctly for better results in the members command',
             description='Associates a player to an alliance',
             aliases=['ally', 'alli'],
             usage='playername alliance_name')
async def alliance(ctx, playername: str, alliance_name: str):
    playername = playername.lower()
    alliance_name = alliance_name.lower()
    player = getPlayer(playername)
    alliance_ = getAlliance(alliance_name)
    player.alliance = alliance_
    session.add(player)
    session.add(alliance_)
    session.commit()
    response = "```Updated alliance of {}```".format(playername)
    await ctx.send(response)


@bot.command(name='members',
             brief='Displays all members of an alliance',
             help='',
             description='Displays all members of an alliance',
             aliases=['who', 'list'],
             usage='alliance_name')
async def members(ctx, alliance_name: str):
    alliance_name = alliance_name.lower()
    alliance_ = getAlliance(alliance_name)
    await ctx.send(embed=alliance_.as_embed())


@bot.command(name='wsa',
             brief='Saves player techs',
             help='playername w s a must have a space between them',
             description='Saves player techs in order weapons, shields, armor',
             aliases=['techs', 'tech'],
             usage='playername 1 2 3')
async def wsa(ctx, playername: str, w: str, s: str, a: str):
    playername = playername.lower()
    player = getPlayer(playername)
    wsa_text = "{}/{}/{}".format(w, s, a)
    player.wsa = wsa_text
    session.add(player)
    session.commit()
    response = "```Updated wsa of {}```".format(playername)
    await ctx.send(response)
    

# Run
bot.run(token)
