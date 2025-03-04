import asyncio
import json
import yfinance as yf
import time
import discord
from datetime import datetime
import pytz
from dotenv import load_dotenv
import os

load_dotenv()

intents = discord.Intents.default()
client = discord.Client(intents=intents)

ny_tz = pytz.timezone('America/New_York')

market_was_open = False

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
CHANNEL_ID_ERROR = int(os.getenv("CHANNEL_ID_ERROR"))


def msg_embed_builder(title, description, color=discord.Color.blue()):
    embed = discord.Embed(
        title=title,
        description=description,
        color=color  # Couleur du bord
    )

    embed.set_footer(text=f"Master Panda - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return embed


def msg_embed_error_builder(title, description):
    return msg_embed_builder(title, description, discord.Color.red())


def msg_embed_signal_builder(title, description, fields=[]):
    embed = msg_embed_builder(title, description)

    for field in fields:
        embed.add_field(name=field['name'], value=field['value'], inline=field['inline'])

    return embed


def msg_embed_start_day_builder(title, description):
    embed = msg_embed_builder(title, description, discord.Color.green())

    embed.set_thumbnail(url="https://media.giphy.com/media/3o7TKz5v8Xt3xJ9T3i/giphy.gif")

    return embed


async def is_market_open():
    global market_was_open
    now = datetime.now(ny_tz)

    # Vérifie si c'est un jour de semaine (lundi à vendredi)
    if now.weekday() >= 5:  # 5 = samedi, 6 = dimanche
        if market_was_open:
            await send_msg_discord("The market is now close. Have a good week", CHANNEL_ID)
            print("Le marché est maintenant fermé (week-end).")
            market_was_open = False
        return False

    # Vérifie si l'heure est dans les heures d'ouverture (9h30 à 16h00)
    market_open_time = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close_time = now.replace(hour=16, minute=0, second=0, microsecond=0)

    if market_open_time <= now <= market_close_time:
        if not market_was_open:
            await send_msg_discord(msg_embed_start_day_builder("The market is now open !", "Have a good day."), CHANNEL_ID, is_embed=True)
            print("Le marché vient d'ouvrir.")
            market_was_open = True
        return True
    else:
        if market_was_open:
            await send_msg_discord("The market is now close.", CHANNEL_ID)
            print("Le marché vient de fermer.")
            market_was_open = False
        return False


def load_config(file_path):
    with open(file_path, 'r') as file:
        config = json.load(file)
    return config


async def send_msg_discord(msg, channel_id, is_embed=False):
    channel = client.get_channel(channel_id)

    if channel:
        if is_embed:
            await channel.send(embed=msg)
        else:
            await channel.send(msg)
    else:
        print(f"Impossible de trouver le salon avec l'ID : {channel_id}")


def calculate_macd(data, short_period=12, long_period=26, signal_period=9):
    data['EMA_12'] = data['Close'].ewm(span=short_period, adjust=False).mean()
    data['EMA_26'] = data['Close'].ewm(span=long_period, adjust=False).mean()
    data['MACD'] = data['EMA_12'] - data['EMA_26']
    data['Signal_Line'] = data['MACD'].ewm(span=signal_period, adjust=False).mean()
    data['MACD_Histogram'] = data['MACD'] - data['Signal_Line']
    return data


async def apply_macd_strategy(data, ticker, period, interval, channel_id):
    data = calculate_macd(data)
    last_row = data.iloc[-1]
    second_last_row = data.iloc[-2]

    if second_last_row['MACD'] > second_last_row['Signal_Line'] and last_row['MACD'] < last_row['Signal_Line']:
        await send_msg_discord(
            msg_embed_signal_builder(f"[{ticker}] - SELL Signal", f"Period: {period} - Interval: {interval}", [
                {"name": "MACD", "value": last_row['MACD'], "inline": True},
                {"name": "Signal Line", "value": last_row['Signal_Line'], "inline": True},
                {"name": "MACD Histogram", "value": last_row['MACD_Histogram'], "inline": True},
                {"name": "Close", "value": last_row['Close'], "inline": True}
            ]),
            channel_id, is_embed=True)

        print(f"[{ticker}] - P {period} - I {interval}, SELL Signal")
    elif second_last_row['MACD'] < second_last_row['Signal_Line'] and last_row['MACD'] > last_row['Signal_Line']:
        await send_msg_discord(
            msg_embed_signal_builder(f"[{ticker}] - BUY Signal", f"Period: {period} - Interval: {interval}", [
                {"name": "MACD", "value": last_row['MACD'], "inline": True},
                {"name": "Signal Line", "value": last_row['Signal_Line'], "inline": True},
                {"name": "MACD Histogram", "value": last_row['MACD_Histogram'], "inline": True},
                {"name": "Close", "value": last_row['Close'], "inline": True}
            ]),
            channel_id, is_embed=True)

        print(f"[{ticker}] - P {period} - I {interval}, BUY Signal")
    return data


def format_data(data):
    return data.round(2)


def interval_to_seconds(interval):
    if interval.endswith('m'):
        return int(interval.rstrip('m')) * 60
    elif interval.endswith('h'):
        return int(interval.rstrip('h')) * 3600
    elif interval.endswith('d'):
        return int(interval.rstrip('d')) * 86400
    elif interval.endswith('w'):
        return int(interval.rstrip('w')) * 604800
    return 60


async def fetch_and_apply_strategy(ticker, period, interval, strategy, channel_id):
    try:
        data = yf.download(ticker, period=period, interval=interval)
        if data.empty:
            await send_msg_discord(
                msg_embed_error_builder("No data fetched",
                                        f"[{ticker}] - No data fetched for period {period} and interval {interval}"),
                channel_id, is_embed=True)
            print(f"[{ticker}] - No data fetched for period {period} and interval {interval}")
            return None

        data = format_data(data)

        if strategy == 'macd' and len(data) > 26:
            data = await apply_macd_strategy(data, ticker, period, interval, channel_id)

        latest_data = data.iloc[-1]

        return latest_data

    except Exception as e:
        await send_msg_discord(msg_embed_error_builder("Error", f"Error fetching data for {ticker}: {e}"),
                               CHANNEL_ID_ERROR, is_embed=True)
        print(f"Error fetching data for {ticker}: {e}")
        return None


async def main():
    config_file = 'config.json'
    config = load_config(config_file)

    last_fetched_times = {}
    for item in config:
        key = (item['ticker'], item['period'], item['interval'])
        last_fetched_times[key] = 0

    while True:
        if await is_market_open():
            current_time = time.time()

            for item in config:
                ticker = item['ticker']
                period = item['period']
                interval = item['interval']
                strategy = item['strategy']
                channel_id = item['channel_id']
                disabled = item['disabled']

                if disabled:
                    continue

                interval_seconds = interval_to_seconds(interval)
                key = (ticker, period, interval)

                if current_time - last_fetched_times[key] >= interval_seconds:
                    print(
                        f"Fetching latest data for {ticker} (P: {period}, I: {interval}) using strategy {strategy}...")
                    result = await fetch_and_apply_strategy(ticker, period, interval, strategy, channel_id)

                    if result is not None:
                        last_fetched_times[key] = current_time

        await asyncio.sleep(10)
        # time.sleep(1)


@client.event
async def on_ready():
    print(f'{client.user} est connecté !')

    # for guild in client.guilds:
    #     print(f"Serveur : {guild.name} (ID : {guild.id})")

    # Boucle sur tous les canaux du serveur et imprime leur nom et leur ID
    #    for channel in guild.channels:
    #       print(f" - Canal : {channel.name} (ID : {channel.id}, Type : {channel.type})")

    channel = client.get_channel(CHANNEL_ID)

    if channel:
        # await channel.send(embed=msg_embed_builder("Master Panda is online !", "Hy ! Master Panda ride le graph  !"))
        print("Hy ! Master Panda ride le graph  !")
    else:
        print(f"Impossible de trouver le salon avec l'ID : {CHANNEL_ID}")
        await client.close()
        exit(1)

    await main()
    await client.close()


if __name__ == "__main__":
    client.run(TOKEN)
