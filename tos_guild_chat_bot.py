# -*- coding:utf-8 -*-
import logging
import discord
import asyncio
import os
import glob
import datetime
import dateutil.parser
import codecs
import re
import signal
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument("--access_token", required=True, help="Discord Access Token")
parser.add_argument("--server_id", required=True, help="Discord Server Id")
parser.add_argument("--tos_ss_dir", default='C:/Nexon/TreeofSaviorJP/release/screenshot/', help="ToS screenshot directory")

args = parser.parse_args()

### Settings
GUILD_SERVER_ID = args.server_id
TOS_SS_DIR = args.tos_ss_dir
ACCESS_TOKEN = args.access_token
CHAT_RECORDS_FILE_FORMAT = 'recchat_{0:%Y%m%d}*.txt'
GUILD_CHAT_LOG_PATTERN = r"(.+)\[ギルド\s+\] ([^\:]+)\:(.+)"
INITIAL_REPORT_TIME = 1 #minutes
MESSAGE_SEND_BULK_SIZE = 10
FETCH_WAIT_TIME = 5 #seconds

### Initialize
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
client = discord.Client()

### Global Variables
last_read_line_numbers = {} # key is file_name, value is line_number

### Extract messages from target file. only newer than last sent or last N minutes.
def extract_new_messages(file_name):
    now = datetime.datetime.now()
    messages = []
    with codecs.open(file_name, 'r', 'utf-8') as f:
        line_number = 0
        for line in f:
            line_number = line_number + 1

            matcher = re.match(GUILD_CHAT_LOG_PATTERN , line)
            if matcher:
                sender = matcher.group(2)
                message = matcher.group(3)

                # should send message?
                should_send_message = False
                if file_name in last_read_line_numbers:
                    should_send_message = last_read_line_numbers[file_name] < line_number
                else:
                    chat_recorded_time_string = matcher.group(1)
                    am_or_pm = chat_recorded_time_string[0:2]
                    time_12h = chat_recorded_time_string[2:-1].strip()
                    chat_recorded_time = datetime.datetime.strptime(time_12h, "%H:%M")
                    if am_or_pm == "PM":
                        chat_recorded_time = chat_recorded_time + datetime.timedelta(hours=12)
                    should_send_message = (now - datetime.timedelta(minutes=INITIAL_REPORT_TIME)).time() < chat_recorded_time.time()

                if should_send_message:
                    messages.append("[" + sender + "] " + message)
        # save
        last_read_line_numbers[file_name] = line_number
        return messages

async def send_guild_messages(destination):
    now = datetime.datetime.now()
    file_pattern = TOS_SS_DIR + CHAT_RECORDS_FILE_FORMAT.format(now)
    file_names = glob.glob(file_pattern)
    for file_name in file_names:
        messages = extract_new_messages(file_name)
        messages_bulk = [messages[i:i + MESSAGE_SEND_BULK_SIZE] for i in range(0, len(messages), MESSAGE_SEND_BULK_SIZE)]
        for bulk in messages_bulk:
            await client.send_message(destination, ''.join(bulk))

@client.event
async def on_ready():
    logger.info('Logged in as %s, id: %s', client.user.name, client.user.id)
    destination = client.get_server(GUILD_SERVER_ID)
    logger.info(destination)
    await client.send_message(destination, "GuildChatBot started. Reporting Messages in Last " + str(INITIAL_REPORT_TIME) + " Minutes...")
    while True:
        await send_guild_messages(destination)
        await asyncio.sleep(FETCH_WAIT_TIME)

# TODO
#@client.event
#async def on_message(message):
#    logger.info(message.content)

def main():
    logger.info('start')

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(client.start(ACCESS_TOKEN))
        loop.run_until_complete(client.connect())
    except KeyboardInterrupt:
        logger.info("shut down")
        destination = client.get_server(GUILD_SERVER_ID)
        loop.run_until_complete(client.send_message(destination, "GuildChatBot is now shutting down. Bye :)"))
        loop.run_until_complete(client.logout())
    # cancel all tasks lingering
    finally:
        loop.close()

    logger.info("finished")

if __name__ == '__main__':
    main()
