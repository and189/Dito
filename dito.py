import discord
from discord.ext import commands, tasks
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

load_dotenv()

bot_token = os.getenv('BOT_TOKEN')
allowed_users = [int(user_id) for user_id in os.getenv('ALLOWED_USERS').split(',')]

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

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

@bot.command(name='addrole')
async def add_role(ctx, member: discord.Member, role: discord.Role, days: int):
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
