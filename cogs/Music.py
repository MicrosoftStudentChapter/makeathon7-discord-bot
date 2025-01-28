import discord
import yt_dlp
from discord.ext import commands
import asyncio
import csv
import random
import logging
from asyncio import Lock  # Use asyncio's Lock instead of threading.Lock

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.music_queue = []  # Queue to store the songs
        self.current_song = None  # Store currently playing song
        self.vote_counts = {}  # Dynamic vote counts for songs
        self.voted_users = set()  # Set to track users who have voted
        self.vote_lock = Lock()  # Lock for thread-safe vote updates
        self.predefined_channel_id = 1330578292767592651  # Replace with your predefined text channel ID
        self.predefined_voice_channel_id = 1330579866851999827  # Replace with your predefined voice channel ID
        self.auto_disconnect_task = None  # Task for auto-pause after 60 seconds of no one in the voice channel

    @commands.Cog.listener()
    async def on_ready(self):
        """Automatically joins the predefined voice channel."""
        channel = self.bot.get_channel(self.predefined_voice_channel_id)
        if channel:
            if not channel.guild.voice_client:
                await channel.connect()
                logging.info(f"Bot connected to {channel.name}")
            else:
                logging.info(f"Bot is already connected to {channel.name}")
        else:
            logging.error("Predefined voice channel not found!")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Detects when members join or leave the voice channel."""
        if after.channel and after.channel.id == self.predefined_voice_channel_id:
            voice_client = after.channel.guild.voice_client
            if not voice_client:
                return

            if len(after.channel.members) == 1 and after.channel.members[0] == voice_client.user:
                # Bot is alone in the channel, start auto-pause task
                if not self.auto_disconnect_task or self.auto_disconnect_task.done():
                    self.auto_disconnect_task = self.bot.loop.create_task(self.check_auto_pause(after.channel))
            elif len(after.channel.members) > 1:
                # Start voting session when a user joins
                text_channel = self.bot.get_channel(self.predefined_channel_id)
                if text_channel:
                    await self.start_voting(text_channel)
                else:
                    logging.error("Predefined text channel not found!")

    async def check_auto_pause(self, channel):
        """Checks if the bot is alone in the voice channel for over 60 seconds."""
        await asyncio.sleep(60)
        if channel.guild.voice_client and len(channel.members) == 1 and channel.id == self.predefined_voice_channel_id:
            voice_client = channel.guild.voice_client
            if voice_client.is_playing():
                voice_client.pause()
                await channel.send("Music has been paused because no one is left in the channel.")
                logging.info("Music paused due to inactivity.")

    async def start_voting(self, ctx):
        """Starts a voting session for songs picked from a CSV file."""
        try:
            with open("cogs\\songs.csv", "r") as file:  # Use relative path
                reader = csv.reader(file)
                next(reader)  # Skip header row
                songs = [row for row in reader if len(row) == 2]  # Ensure each row has a title and URL

            if len(songs) < 5:
                await ctx.send("Not enough songs in the CSV file to create a poll.")
                return

            selected_songs = random.sample(songs, 5)
            self.vote_counts = {song[0]: 0 for song in selected_songs}
            self.voted_users.clear()

            view = discord.ui.View()
            for song in selected_songs:
                view.add_item(SongVoteButton(song[0], self.vote_counts, ctx, self.voted_users, self.vote_lock))

            vote_summary = "\n".join([f"{title}: {count} votes" for title, count in self.vote_counts.items()])
            await ctx.send("**Vote for your favorite song!**\n" + vote_summary, view=view)

            await asyncio.sleep(30)  # Wait for 30 seconds

            sorted_songs = sorted(self.vote_counts.items(), key=lambda item: item[1], reverse=True)
            top_song = sorted_songs[0][0]
            song_url = next(song[1] for song in selected_songs if song[0] == top_song)

            # Fetch audio URL using yt-dlp
            try:
                ydl_opts = {"format": "bestaudio", "noplaylist": True}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(song_url, download=False)
                    audio_url = info['url']
            except yt_dlp.utils.DownloadError as e:
                logging.error(f"Error extracting audio URL: {e}")
                await ctx.send("There was an error fetching the song. Please try again later.")
                return

            self.music_queue.append({"url": audio_url, "title": top_song})
            await self.play_next_song(ctx)

            await ctx.send(f"Voting has ended! The most voted song is: **{top_song}**\nNow playing...")

        except FileNotFoundError:
            await ctx.send("CSV file not found. Please ensure 'songs.csv' exists in the bot's directory.")

    async def play_next_song(self, ctx):
        """Plays the next song in the queue."""
        if len(self.music_queue) > 0:
            next_song = self.music_queue.pop(0)
            self.current_song = next_song["url"]
            voice_client = ctx.guild.voice_client
            if voice_client:
                if voice_client.is_playing():  # Check if audio is already playing
                    await ctx.send("Audio is still playing. Please wait until the current song finishes.")
                    return

                source = discord.FFmpegPCMAudio(next_song["url"], **self.ffmpeg_options)
                voice_client.play(source, after=lambda e: self.bot.loop.create_task(self.play_next_song(ctx)))
                await ctx.send(f"Now playing: {next_song['title']}")
        else:
            await ctx.send("The queue is empty. No more songs to play.")

    ffmpeg_options = {
        "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        "options": "-vn",
    }

class SongVoteButton(discord.ui.Button):
    def __init__(self,  button_number, vote_counts, ctx, voted_users, lock):
        super().__init__(style=discord.ButtonStyle.primary, label=song_title)
        self.button_number = button_number
        self.vote_counts = vote_counts
        self.ctx = ctx
        self.voted_users = voted_users
        self.lock = lock

    async def callback(self, interaction: discord.Interaction):
        with self.lock:  # Ensure thread-safe updates
            if interaction.user.id in self.voted_users:
                await interaction.response.send_message("You have already voted!", ephemeral=True)
                return

            self.vote_counts[f"Option {self.button_number}"] += 1
            self.voted_users.add(interaction.user.id)

        vote_summary = "\n".join([f"{count} -> {title} votes" for title, count in self.vote_counts.items()])
        await interaction.response.edit_message(content=f"**Vote for your favorite song!**\n{vote_summary}")

async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
