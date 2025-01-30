import discord
from discord.ext import commands
import yt_dlp
import asyncio
import csv
import random
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.music_queue = []  # Queue to store songs
        self.current_song = None  # Currently playing song
        self.vote_counts = {}  # Dynamic vote counts for songs
        self.voted_users = set()  # Track users who have voted
        self.predefined_channel_id = 1330578292767592651  # Text channel ID
        self.predefined_voice_channel_id = 1330579866851999827  # Voice channel ID
        self.poll_in_progress = False  # Prevent multiple polls
        self.lock = asyncio.Lock()  # Concurrency lock
        self.ffmpeg_options = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin",
            "options": "-vn -bufsize 1024k",  # Optimize buffer size
        }

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def set_channel(self, ctx, text_channel: discord.TextChannel, voice_channel: discord.VoiceChannel):
        """Command to set predefined text and voice channels."""
        self.predefined_channel_id = text_channel.id
        self.predefined_voice_channel_id = voice_channel.id
        await ctx.send(f"Text channel set to {text_channel.mention} and voice channel set to {voice_channel.name}.")
        logging.info(f"Text channel: {text_channel.id}, Voice channel: {voice_channel.id} set successfully.")

    @commands.Cog.listener()
    async def on_ready(self):
        """Triggered when the bot is ready."""
        logging.info("Music bot is ready!")
        if self.predefined_voice_channel_id:
            channel = self.bot.get_channel(self.predefined_voice_channel_id)
            if channel:
                try:
                    if not channel.guild.voice_client:
                        await channel.connect()
                        logging.info(f"Bot connected to {channel.name}")
                except discord.ClientException:
                    logging.warning(f"Bot is already connected to {channel.name}")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Detects users joining or leaving the voice channel."""
        if after.channel and after.channel.id == self.predefined_voice_channel_id:
            voice_client = after.channel.guild.voice_client
            if not voice_client:
                return

            if not self.poll_in_progress and len([m for m in after.channel.members if not m.bot]) > 0:
                text_channel = self.bot.get_channel(self.predefined_channel_id)
                if text_channel:
                    asyncio.create_task(self.start_voting(text_channel))

    async def start_voting(self, ctx):
        """Starts a voting session."""
        if self.poll_in_progress:
            return
        self.poll_in_progress = True
        self.voted_users.clear()

        while True:
            voice_client = ctx.guild.voice_client
            if not voice_client or len([m for m in voice_client.channel.members if not m.bot]) == 0:
                await ctx.send("No active users in the voice channel. Stopping voting session.")
                self.poll_in_progress = False
                return

            try:
                songs = await self.load_songs_async()
                if len(songs) < 5:
                    await ctx.send("Not enough songs in the CSV file to create a poll.")
                    self.poll_in_progress = False
                    return

                selected_songs = random.sample(songs, 5)
                self.vote_counts = {song[0]: 0 for song in selected_songs}

                view = discord.ui.View(timeout=None)  # Disable automatic timeout
                for song in selected_songs:
                    view.add_item(SongVoteButton(song[0], self.vote_counts, ctx, self.voted_users))

                vote_message = await ctx.send("**Vote for your favorite song!**", view=view)

                await asyncio.sleep(60)  # Voting duration

                # Disable buttons after voting
                for child in view.children:
                    if isinstance(child, discord.ui.Button):
                        child.disabled = True

                await vote_message.edit(content="**Voting has ended! Here are the results:**", view=view)

                # Sort and add top-voted songs to the queue
                sorted_songs = sorted(self.vote_counts.items(), key=lambda item: item[1], reverse=True)
                for song_title, _ in sorted_songs:
                    song_url = next(song[1] for song in selected_songs if song[0] == song_title)
                    self.music_queue.append({"url": song_url, "title": song_title})

                if not self.current_song:
                    asyncio.create_task(self.play_next_song(ctx))

                self.poll_in_progress = False
                return
            except FileNotFoundError:
                await ctx.send("CSV file not found. Ensure 'songs.csv' exists in the bot's directory.")
                self.poll_in_progress = False
                return
        
    async def load_songs_async(self):
        """Asynchronously loads songs from the CSV file."""
        return await asyncio.to_thread(self.load_songs)

    def load_songs(self):
        """Loads songs from the CSV file."""
        script_dir = os.path.dirname(__file__)  # Path to this cog's directory
        file_path = os.path.join(script_dir, "songs.csv")

        if not os.path.exists(file_path):
            logging.error(f"CSV file not found: {file_path}")
            return []

        with open(file_path, "r") as file:
            reader = csv.DictReader(file)
            if "songs" not in reader.fieldnames or "URL" not in reader.fieldnames:
                logging.error("CSV file is improperly formatted. Ensure it contains 'songs' and 'URL' columns.")
                return []
            return [(row["songs"], row["URL"]) for row in reader if row["songs"] and row["URL"]]

    async def play_next_song(self, ctx):
        """Plays the next song in the queue."""
        async with self.lock:
            if self.music_queue:
                next_song = self.music_queue.pop(0)
                self.current_song = next_song["url"]
                voice_client = ctx.guild.voice_client

                if voice_client and not voice_client.is_playing():
                    source = await self.stream_song(next_song["url"])
                    if source:
                        def after_playing(_):
                            # Callback after the current song finishes
                            asyncio.run_coroutine_threadsafe(self.on_song_end(ctx), self.bot.loop)

                        voice_client.play(source, after=after_playing)
                        # Log the currently playing song
                        logging.info(f"Now playing: {next_song['title']}")
                        # Log the updated queue
                        logging.info(f"Updated queue: {[song['title'] for song in self.music_queue]}")
                        await ctx.send(f"Now playing: {next_song['title']}")
                    else:
                        await ctx.send(f"Failed to stream: {next_song['title']}")
                        logging.error(f"Failed to stream: {next_song['title']}")
                        asyncio.create_task(self.play_next_song(ctx))  # Skip to the next song if this fails
            else:
                # No songs in the queue
                self.current_song = None
                logging.info("Queue is empty. No more songs to play.")
                await ctx.send("Queue is empty. Add more songs!")
                
    async def on_song_end(self, ctx):
        """Handles events when a song finishes."""
        voice_client = ctx.guild.voice_client

        # Check if there are active users in the channel
        if not voice_client or len([m for m in voice_client.channel.members if not m.bot]) == 0:
            await ctx.send("No active users in the voice channel. Stopping playback.")
            return

        # Check if the queue is empty
        if len(self.music_queue) == 0:
            await ctx.send("🎶 Queue is empty! Starting a new voting session...")
            asyncio.create_task(self.start_voting(ctx))
        else:
            asyncio.create_task(self.play_next_song(ctx))  # Continue to the next song

    async def stream_song(self, url):
        """Streams a song directly without downloading."""
        ydl_opts = {
            "format": "bestaudio/best",
            "noplaylist": True,
            "quiet": True,
            "noprogress": True,
            "socket_timeout": 15,
            "extractor_args": {"youtube": {"skip": ["dash", "hls"]}},  # Skip DASH/HLS formats
            "default_search": "ytsearch",
            "geo_bypass": True,
        }
        try:
            info = await asyncio.to_thread(self.extract_song_info, url, ydl_opts)
            if "url" in info:
                return discord.FFmpegPCMAudio(info["url"], **self.ffmpeg_options)
            else:
                logging.error("Failed to extract song info.")
                return None
        except Exception as e:
            logging.error(f"Error streaming song: {e}")
            return None

    def extract_song_info(self, url, ydl_opts):
        """Runs yt_dlp in a blocking thread to extract song information."""
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)

class SongVoteButton(discord.ui.Button):
    def __init__(self, song_title, vote_counts, ctx, voted_users):
        super().__init__(style=discord.ButtonStyle.primary, label=song_title)
        self.song_title = song_title
        self.vote_counts = vote_counts
        self.ctx = ctx
        self.voted_users = voted_users

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id in self.voted_users:
            await interaction.response.send_message("You have already voted! :)", ephemeral=True)
            return

        self.vote_counts[self.song_title] += 1
        self.voted_users.add(interaction.user.id)
        vote_summary = "\n".join([f"{count} votes: {title}" for title, count in self.vote_counts.items()])
        await interaction.response.edit_message(content=f"**Vote for your favorite song**\n{vote_summary}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))