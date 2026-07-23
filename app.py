from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import os

app = Flask(__name__)
CORS(app, origins="*")

@app.route('/')
def home():
    return jsonify({'status': 'VidFetch API Running ✅', 'version': '2.0'})

@app.route('/api/download', methods=['POST'])
def get_download():
    data = request.get_json()
    url = data.get('url', '').strip()
    quality = data.get('quality', '720')

    if not url or not url.startswith('http'):
        return jsonify({'error': 'Valid URL required'}), 400

    # Format selection based on quality
    quality_map = {
        '2160': 'bestvideo[height<=2160][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=2160]+bestaudio/best[height<=2160]/best',
        '1080': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
        '720':  'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]/best',
        '480':  'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best[height<=480]/best',
        '360':  'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=360]+bestaudio/best[height<=360]/best',
        '240':  'bestvideo[height<=240][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=240]+bestaudio/best[height<=240]/best',
        '144':  'bestvideo[height<=144][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=144]+bestaudio/best[height<=144]/best',
    }
    format_str = quality_map.get(quality, quality_map['720'])

    ydl_opts = {
        'format': format_str,
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'socket_timeout': 30,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            title     = info.get('title', 'Video')
            thumbnail = info.get('thumbnail', '')
            duration  = info.get('duration', 0)
            uploader  = info.get('uploader', '')
            ext       = info.get('ext', 'mp4')

            # Get download URL
            download_url = None
            if 'url' in info:
                download_url = info['url']
            elif 'formats' in info and info['formats']:
                fmts = [f for f in info['formats'] if f.get('url') and f.get('vcodec') != 'none']
                if fmts:
                    download_url = fmts[-1]['url']
                    ext = fmts[-1].get('ext', 'mp4')
                elif info['formats']:
                    download_url = info['formats'][-1].get('url')

            if not download_url:
                return jsonify({'error': 'Could not extract download URL. Try different quality.'}), 500

            # Format duration
            dur_str = ''
            if duration:
                m, s = divmod(int(duration), 60)
                h, m = divmod(m, 60)
                dur_str = f'{h}:{m:02d}:{s:02d}' if h else f'{m}:{s:02d}'

            return jsonify({
                'success': True,
                'download_url': download_url,
                'title': title,
                'thumbnail': thumbnail,
                'duration': dur_str,
                'uploader': uploader,
                'ext': ext,
                'quality': quality,
            })

    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        if 'Private video' in msg:
            return jsonify({'error': 'This video is private and cannot be downloaded.'}), 403
        elif 'not available' in msg or 'unavailable' in msg:
            return jsonify({'error': 'This video is not available in your region or has been removed.'}), 403
        elif 'Sign in' in msg:
            return jsonify({'error': 'This video requires sign-in and cannot be downloaded.'}), 403
        else:
            return jsonify({'error': f'Download error: {msg[:300]}'}), 500
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)[:200]}'}), 500


@app.route('/api/info', methods=['POST'])
def get_info():
    data = request.get_json()
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'error': 'URL required'}), 400

    ydl_opts = {'quiet': True, 'no_warnings': True, 'socket_timeout': 20}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            duration = info.get('duration', 0)
            m, s = divmod(int(duration), 60) if duration else (0, 0)
            return jsonify({
                'title': info.get('title', 'Video'),
                'thumbnail': info.get('thumbnail', ''),
                'duration': f'{m}:{s:02d}' if duration else '',
                'uploader': info.get('uploader', ''),
            })
    except Exception as e:
        return jsonify({'error': str(e)[:200]}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
