import discord
from discord.ext import commands
import yt_dlp
import asyncio

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voice_clients = {}
        self.music_queue = []  # Queue to store the songs
        self.current_song = None  # Store currently playing song
        self.auto_disconnect_task = None  # Task for auto-disconnect

    async def check_auto_disconnect(self, ctx):
        """Automatically disconnect if no members are in the voice channel after a timeout."""
        await asyncio.sleep(300)  # 5-minute timeout
        if ctx.voice_client and len(ctx.voice_client.channel.members) == 1:  # Only the bot is left
            await ctx.voice_client.disconnect()
            await ctx.send("Disconnected from the voice channel due to inactivity.")

    @commands.command(name="join")
    async def join(self, ctx):
        """Joins the voice channel of the user."""
        if ctx.author.voice:
            channel = ctx.author.voice.channel
            if ctx.voice_client is None:
                await channel.connect()
                await ctx.send(f"Joined {channel}")
            else:
                await ctx.voice_client.move_to(channel)
                await ctx.send(f"Moved to {channel}")
        else:
            await ctx.send("You need to be in a voice channel first!")

    @commands.command(name="leave")
    async def leave(self, ctx):
        """Leaves the voice channel."""
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await ctx.send("Disconnected from the voice channel.")
        else:
            await ctx.send("I'm not in a voice channel!")

    @commands.command(name="play")
    async def play(self, ctx, *, query: str):
        """
        Plays a song from the given YouTube URL or search term.
        If a song is already playing, adds it to the queue.
        """
        if ctx.voice_client is None:
            await self.join(ctx)

        # Function to handle playback after the current song
        def after_playing(error):
            if len(self.music_queue) > 0:
                next_song = self.music_queue.pop(0)
                self.current_song = next_song["url"]
                source = discord.FFmpegPCMAudio(next_song["url"], **self.ffmpeg_options)
                ctx.voice_client.play(source, after=lambda e: after_playing(e))
                asyncio.run_coroutine_threadsafe(
                    ctx.send(f"Now playing: {next_song['title']}"), self.bot.loop
                )
            else:
                self.current_song = None
                self.auto_disconnect_task = self.bot.loop.create_task(self.check_auto_disconnect(ctx))

        # Determine if the query is a URL or a search term
        ydl_opts = {"format": "bestaudio", "noplaylist": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                if "youtube.com" in query or "youtu.be" in query:
                    # Process as a URL
                    info = ydl.extract_info(query, download=False)
                else:
                    # Process as a search term
                    info = ydl.extract_info(f"ytsearch:{query}", download=False)["entries"][0]
            except Exception as e:
                await ctx.send(f"An error occurred while processing the query: {str(e)}")
                return

        audio_url = info["url"]
        song_title = info["title"]

        if ctx.voice_client.is_playing() or self.current_song:
            # Add to queue
            self.music_queue.append({"url": audio_url, "title": song_title})
            await ctx.send(f"Added to queue: {song_title}")
        else:
            # Play immediately
            self.current_song = audio_url
            source = discord.FFmpegPCMAudio(audio_url, **self.ffmpeg_options)
            ctx.voice_client.play(source, after=lambda e: after_playing(e))
            await ctx.send(f"Now playing: {song_title}")

    @commands.command(name="stop")
    async def stop(self, ctx):
        """Stops playback and clears the queue."""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            self.music_queue.clear()
            await ctx.send("Music stopped and queue cleared!")

    @commands.command(name="pause")
    async def pause(self, ctx):
        """Pauses the currently playing song."""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("Music paused!")

    @commands.command(name="resume")
    async def resume(self, ctx):
        """Resumes the currently paused song."""
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("Music resumed!")

    @commands.command(name="skip")
    async def skip(self, ctx):
        """Skips the currently playing song."""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send("Skipped the current song!")

    @commands.command(name="queue")
    async def queue(self, ctx):
        """Displays the current queue."""
        if len(self.music_queue) == 0:
            await ctx.send("The queue is empty!")
        else:
            queue_list = "\n".join([f"{i+1}. {item['title']}" for i, item in enumerate(self.music_queue)])
            await ctx.send(f"Current queue:\n{queue_list}")

    @commands.command(name="current")
    async def current(self, ctx):
        """Displays the currently playing song."""
        if self.current_song:
            await ctx.send(f"Currently playing: {self.current_song}")
        else:
            await ctx.send("No song is currently playing!")

    ffmpeg_options = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -loglevel error",
    "options": "-vn -buffer_size 512k",  # Add a larger buffer
    }



async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
