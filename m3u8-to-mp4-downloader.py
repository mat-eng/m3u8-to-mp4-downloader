"""
Created on 08.09.2024
@author: mat-eng
@description: Takes web url as input. The web page is scrapped to find master m3u8 file(s).
All playlists found are displayed, user need to choose 1 video playlist and 1 audio playlist.
Video and audio segments (ts files) are downloaded, then put together.
Finally, the video and audio files are combined and exported as a mp4 file.
ffmpeg is required and need to be on the system path.
"""
########################################################################################################################
# Imports
import os
import sys
import m3u8
import requests
import subprocess
import json
import re
import datetime
from tqdm import tqdm
from bs4 import BeautifulSoup


########################################################################################################################
# Scrap the input webpage to find master m3u8 file(s)
def find_master_m3u8(webpage_url):
    print(f"Searching for master m3u8 in: {webpage_url}")

    # Fetch the webpage content
    response = requests.get(webpage_url)
    if response.status_code != 200:
        print(f"Failed to access {webpage_url}")
        return None

    webpage_content = response.text

    # Attempt to locate JSON-like data in the page
    soup = BeautifulSoup(webpage_content, 'html.parser')

    # Look for script tags that may contain JSON data
    for script in soup.find_all('script'):
        if script.string:
            try:
                # Use regex to extract JSON-like content from script tag
                json_data = re.search(r'{.*}', script.string.strip())
                if json_data:
                    data = json.loads(json_data.group())
                    # Assuming the M3U8 URL is under 'streams' -> 'url' key
                    m3u8_url = data.get('streams', [{}])[0].get('url')
                    if m3u8_url:
                        print(f"Found M3U8 URL: {m3u8_url}")
                        return m3u8_url
            except (json.JSONDecodeError, IndexError, KeyError):
                continue  # If parsing fails, move to the next script tag

    # Fallback: Extract M3U8 links directly from the HTML content
    m3u8_links = []

    # Search for links with '.m3u8' in the href
    for link in soup.find_all('a', href=True):
        if '.m3u8' in link['href']:
            m3u8_links.append(link['href'])

    # Search for M3U8 URLs inside inline script tags
    for script in soup.find_all('script'):
        if script.string and '.m3u8' in script.string:
            m3u8_links.extend(re.findall(r'(https?://[^\s\'"]+\.m3u8)', script.string))

    if not m3u8_links:
        print("No M3U8 links found on the page.")
        return None

    # Clean up and deduplicate the links
    m3u8_links = list(set(m3u8_links))

    # Return the first M3U8 link found as the master playlist
    master_m3u8_url = m3u8_links[0]
    if not master_m3u8_url.startswith('http'):
        # Handle relative URLs
        from urllib.parse import urljoin
        master_m3u8_url = urljoin(webpage_url, master_m3u8_url)

    print(f"Found M3U8 URL: {master_m3u8_url}")
    return master_m3u8_url


########################################################################################################################
# Function to download each segment and save to a file
def download_segment(url, output_dir, segment_filename):
    segment_path = os.path.join(output_dir, segment_filename)

    # Download the segment only if it doesn't already exist
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(segment_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
        return segment_path
    else:
        print(f"Failed to download segment: {url}")
        return None


########################################################################################################################
# Function to download all unique segments from a playlist
def download_stream(m3u8_url, output_dir, stream_type):
    playlist = m3u8.load(m3u8_url)
    seen_urls = set()
    segment_files = []
    base_uri = playlist.base_uri or m3u8_url.rsplit('/', 1)[0] + '/'

    print(f"\nDownloading {stream_type} segments...")
    for i, segment in enumerate(tqdm(playlist.segments)):
        segment_url = segment.uri if segment.uri.startswith('http') else base_uri + segment.uri
        if segment_url in seen_urls:
            #print(f"Skipping duplicate segment: {segment_url}")
            continue
        seen_urls.add(segment_url)
        segment_filename = f'{stream_type}_segment_{i}.ts'
        segment_path = download_segment(segment_url, output_dir, segment_filename)
        if segment_path:
            segment_files.append(segment_path)
    return segment_files


########################################################################################################################
# Function to combine video and audio into a single MP4 file using ffmpeg
def combine_audio_video(video_file, audio_file, output_filename, ffmpeg_path):
    print(f"Combining video and audio into {output_filename}...")
    command = [
        ffmpeg_path,
        '-i', video_file,
        '-i', audio_file,
        '-c:v', 'copy',  # Copy video codec to avoid re-encoding
        '-c:a', 'aac',  # Encode audio with AAC codec
        '-strict', 'experimental',
        output_filename
    ]
    subprocess.run(command, check=True)
    print(f"Output file created: {output_filename}")


########################################################################################################################
# Function to list playlists from master m3u8 file and get user's selection
def select_playlist_from_master(master_m3u8_url):
    response = requests.get(master_m3u8_url)
    master_playlist = m3u8.loads(response.text)

    # Parse video playlists
    video_playlists = []
    audio_playlists = []

    for playlist in master_playlist.data['playlists']:
        video_playlists.append(playlist)

    # Parse audio playlists
    for media in master_playlist.data['media']:
        if media['type'] == 'AUDIO':
            audio_playlists.append(media)

    # Let the user select a video playlist
    print("\nAvailable video playlists:")
    for idx, video_playlist in enumerate(video_playlists):
        print(f"{idx+1}: {video_playlist}\n")
    video_choice = int(input("Select the video playlist number: ")) - 1
    video_playlist_url = video_playlists[video_choice]['uri']

    # Let the user select an audio playlist
    print("\nAvailable audio playlists:")
    for idx, audio_playlist in enumerate(audio_playlists):
        print(f"{idx + 1}: {audio_playlist}\n")
    audio_choice = int(input("Select the audio playlist number: ")) - 1
    audio_playlist_url = audio_playlists[audio_choice]['uri']

    return video_playlist_url, audio_playlist_url


########################################################################################################################
# Main function to download both video and audio streams and combine them
def download_video_and_audio(output_filename, ffmpeg_path):
    # Ask user for web url
    print("")
    webpage_url = input("Paste the url link: ")
    print("")
    # Search for the master m3u8 file from the webpage
    master_m3u8_url = find_master_m3u8(webpage_url)
    if not master_m3u8_url:
        print("Failed to find the master M3U8 file.")
        return

    # Let user select video and audio playlists from master file
    video_m3u8_url, audio_m3u8_url = select_playlist_from_master(master_m3u8_url)

    # Create output directory for video and audio segments
    output_dir = 'video_audio_segments'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Download video segments
    video_segment_files = download_stream(video_m3u8_url, output_dir, 'video')

    # Download audio segments
    audio_segment_files = download_stream(audio_m3u8_url, output_dir, 'audio')

    # Combine video segments into a single video file
    video_file = os.path.join(output_dir, 'video_combined.ts')
    with open(video_file, 'wb') as v_out:
        for segment_file in video_segment_files:
            with open(segment_file, 'rb') as v_in:
                v_out.write(v_in.read())

    # Combine audio segments into a single audio file
    audio_file = os.path.join(output_dir, 'audio_combined.ts')
    with open(audio_file, 'wb') as a_out:
        for segment_file in audio_segment_files:
            with open(segment_file, 'rb') as a_in:
                a_out.write(a_in.read())

    # Combine audio and video using ffmpeg
    combine_audio_video(video_file, audio_file, output_filename, ffmpeg_path)

    # Optionally clean up the segment files
    for segment_file in video_segment_files + audio_segment_files:
        os.remove(segment_file)
    os.remove(video_file)
    os.remove(audio_file)
    os.rmdir(output_dir)

    print(f"Video and audio download and merge complete: {output_filename}")


########################################################################################################################
# Check if ffmpeg is installed and available on the system path
def check_ffmpeg():
    try:
        # Run 'ffmpeg -version' to check if ffmpeg is in the system path
        result = subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            return True
        else:
            print("FFmpeg is not available or not working properly.")
            return False
    except FileNotFoundError:
        # If the command is not found, raise an error
        print("FFmpeg is not installed or not in the system path.")
        return False


########################################################################################################################
# Check if ffmpeg is on the system path or in the bundled executable
def get_ffmpeg_path():
    if hasattr(sys, '_MEIPASS'):
        # If running in a PyInstaller bundle, find ffmpeg in the bundled directory
        return os.path.join(sys._MEIPASS, 'ffmpeg', 'ffmpeg')
    else:
        # Otherwise, check if ffmpeg is on the system PATH
        if not check_ffmpeg():
            print("Please install FFmpeg and make sure it's available on the system path. Visit https://www.ffmpeg.org/download.html")
            exit(1)  # Exit the script if ffmpeg is not available
        else:
            return 'ffmpeg'


########################################################################################################################
# Main
if __name__ == '__main__':
    # Check availability of ffmpeg
    ffmpeg_path = get_ffmpeg_path()

    output_filename = 'final-output-' + datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S') + '.mp4'

    download_video_and_audio(output_filename, ffmpeg_path)
