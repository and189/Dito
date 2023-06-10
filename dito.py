import discord
from discord.ext import commands, tasks
from discord_slash import SlashCommand, SlashContext
from discord_slash.utils.manage_commands import create_option
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

load_dotenv()

bot_token = os.getenv('BOT_TOKEN')
allowed_users = [int(user_id) for user_id in os.getenv('ALLOWED_USERS').split(',')]

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)
slash = SlashCommand(bot, sync_commands=True)

# Verbindung zur SQLite-Datenbank herstellen
conn = sqlite3.connect('members.db')
c = conn.cursor()

# Tabelle erstellen, falls sie noch nicht existiert
c.execute('''CREATE TABLE IF NOT EXISTS members (id INTEGER PRIMARY KEY, user_id INTEGER, role_id INTEGER, end_date TEXT)''')
conn.commit()

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    # Task starten, um regelmäßig die Rollen zu überprüfen
    check_roles.start()

@slash.slash(name="addrole",
             description="Fügt einem Mitglied eine Rolle hinzu",
             options=[
               create_option(
                 name="member",
                 description="Das Mitglied, dem die Rolle hinzugefügt werden soll",
                 option_type=6,
                 required=True
               ),
               create_option(
                 name="role",
                 description="Die Rolle, die hinzugefügt werden soll",
                 option_type=8,
                 required=True
               ),
               create_option(
                 name="days",
                 description="Die Anzahl der Tage, für die die Rolle gegeben wird",
                 option_type=4,
                 required=True
               )
             ])
async def _add_role(ctx: SlashContext, member: discord.Member, role: discord.Role, days: int):
    if ctx.author.id not in allowed_users:
        await ctx.send('Du bist nicht berechtigt, diesen Befehl zu verwenden.')
        return

    # Überprüfen, ob der Nutzer bereits eine Rolle hat
    c.execute('SELECT * FROM members WHERE user_id=?', (member.id,))
    result = c.fetchone()
    if result:
        await ctx.send(f'{member.mention} hat bereits eine Rolle.')
        return

    # Rolle hinzufügen
    await member.add_roles(role)
    # Enddatum berechnen
    end_date = datetime.now() + timedelta(days=days)
    # Eintrag in die Datenbank hinzufügen
    c.execute('INSERT INTO members (user_id, role_id, end_date) VALUES (?, ?, ?)', (member.id, role.id, end_date.strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    await ctx.send(f'{member.mention} wurde die Rolle {role.name} für {days} Tage gegeben.')
    await member.send(f'Du wurdest der Rolle {role.name} hinzugefügt und wirst in {days} Tagen entfernt.')

@slash.slash(name="extendrole",
             description="Verlängert die Laufzeit einer vorhandenen Rolle",
             options=[
               create_option(
                 name="member",
                 description="Das Mitglied, dessen Rolle verlängert werden soll",
                 option_type=6,
                 required=True
               ),
               create_option(
                 name="role",
                 description="Die Rolle, die verlängert werden soll",
                 option_type=8,
                 required=True
               ),
               create_option(
                 name="days",
                 description="Die Anzahl der Tage, um die die Laufzeit verlängert wird",
                 option_type=4,
                 required=True
               )
             ])
async def _extend_role(ctx: SlashContext, member: discord.Member, role: discord.Role, days: int):
    if ctx.author.id not in allowed_users:
        await ctx.send('Du bist nicht berechtigt, diesen Befehl zu verwenden.')
        return

    # Überprüfen, ob der Nutzer bereits eine Rolle hat
    c.execute('SELECT * FROM members WHERE user_id=? AND role_id=?', (member.id, role.id))
    result = c.fetchone()
    if not result:
        await ctx.send(f'{member.mention} hat diese Rolle nicht.')
        return

    # Enddatum auslesen und aktualisieren
    end_date = datetime.strptime(result[3], '%Y-%m-%d %H:%M:%S')
    end_date += timedelta(days=days)
    # Eintrag in der Datenbank aktualisieren
    c.execute('UPDATE members SET end_date=? WHERE id=?', (end_date.strftime('%Y-%m-%d %H:%M:%S'), result[0]))
    conn.commit()
    await ctx.send(f'Die Rolle {role.name} von {member.mention} wurde um {days} Tage verlängert.')

@tasks.loop(minutes=1)
async def check_roles():
    # Alle Einträge aus der Datenbank holen
    c.execute('SELECT * FROM members')
    results = c.fetchall()
    for result in results:
        # Enddatum auslesen und mit dem aktuellen Datum vergleichen
        end_date = datetime.strptime(result[3], '%Y-%m-%d %H:%M:%S')
        if datetime.now() > end_date:
            # Rolle entfernen
            guild = bot.get_guild(result[1])
            member = guild.get_member(result[1])
            role = guild.get_role(result[2])
            await member.remove_roles(role)
            # Eintrag aus der Datenbank entfernen
            c.execute('DELETE FROM members WHERE id=?', (result[0],))
            conn.commit()
            await member.send(f'Deine Rolle {role.name} wurde entfernt.')
        elif datetime.now() > end_date - timedelta(days=5):
            await member.send(f'Deine Rolle {role.name} wird in 5 Tagen entfernt.')

bot.run(bot_token)
