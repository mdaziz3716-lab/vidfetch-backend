from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import os

app = Flask(__name__)
CORS(app, origins="*")

@app.route('/')
def home():
    return jsonify({'status': 'VidFetch API Running ✅', 'version': '3.0'})

def get_ydl_opts(format_str):
    return {
        'format': format_str,
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'socket_timeout': 30,
        # ── Anti-bot bypass ──────────────────
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        },
        # ── YouTube cookie workaround ─────────
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
                'player_skip': ['webpage', 'configs'],
            }
        },
        # ── Retry on failure ──────────────────
        'retries': 3,
        'fragment_retries': 3,
    }

@app.route('/api/download', methods=['POST'])
def get_download():
    data = request.get_json()
    url = data.get('url', '').strip()
    quality = data.get('quality', '720')

    if not url or not url.startswith('http'):
        return jsonify({'error': 'Valid URL required'}), 400

    quality_map = {
        '2160': 'bestvideo[height<=2160][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=2160]+bestaudio/best',
        '1080': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best',
        '720':  'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best',
        '480':  'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best',
        '360':  'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=360]+bestaudio/best',
        '240':  'bestvideo[height<=240][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=240]+bestaudio/best',
        '144':  'bestvideo[height<=144][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=144]+bestaudio/best',
    }
    format_str = quality_map.get(quality, quality_map['720'])

    try:
        with yt_dlp.YoutubeDL(get_ydl_opts(format_str)) as ydl:
            info = ydl.extract_info(url, download=False)

            title     = info.get('title', 'Video')
            thumbnail = info.get('thumbnail', '')
            duration  = info.get('duration', 0)
            uploader  = info.get('uploader', '')
            ext       = info.get('ext', 'mp4')

            # Get best download URL
            download_url = None
            if 'url' in info:
                download_url = info['url']
            elif 'formats' in info and info['formats']:
                # Try to get video with audio merged
                fmts = [f for f in info['formats']
                        if f.get('url') and f.get('vcodec') != 'none'
                        and f.get('acodec') != 'none']
                if fmts:
                    download_url = fmts[-1]['url']
                    ext = fmts[-1].get('ext', 'mp4')
                else:
                    # Fallback: any format with URL
                    all_fmts = [f for f in info['formats'] if f.get('url')]
                    if all_fmts:
                        download_url = all_fmts[-1]['url']
                        ext = all_fmts[-1].get('ext', 'mp4')

            if not download_url:
                return jsonify({'error': 'Could not extract download URL. Try a different quality.'}), 500

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
        # Try fallback with different player
        try:
            fallback_opts = get_ydl_opts(format_str)
            fallback_opts['extractor_args'] = {
                'youtube': {'player_client': ['ios']}
            }
            with yt_dlp.YoutubeDL(fallback_opts) as ydl2:
                info = ydl2.extract_info(url, download=False)
                dl_url = info.get('url') or (
                    info.get('formats', [{}])[-1].get('url') if info.get('formats') else None
                )
                if dl_url:
                    duration = info.get('duration', 0)
                    m, s = divmod(int(duration), 60) if duration else (0,0)
                    return jsonify({
                        'success': True,
                        'download_url': dl_url,
                        'title': info.get('title', 'Video'),
                        'thumbnail': info.get('thumbnail', ''),
                        'duration': f'{m}:{s:02d}' if duration else '',
                        'uploader': info.get('uploader', ''),
                        'ext': info.get('ext', 'mp4'),
                        'quality': quality,
                    })
        except:
            pass

        # Return user-friendly error
        if 'Sign in' in msg or 'sign in' in msg:
            return jsonify({'error': 'YouTube is blocking this request. Please try: 1) A different video 2) Lower quality 3) Try again in 1 minute'}), 403
        elif 'Private' in msg:
            return jsonify({'error': 'This video is private and cannot be downloaded.'}), 403
        elif 'not available' in msg or 'unavailable' in msg:
            return jsonify({'error': 'Video not available in this region or has been removed.'}), 403
        elif 'age' in msg.lower():
            return jsonify({'error': 'Age-restricted video cannot be downloaded without login.'}), 403
        else:
            return jsonify({'error': f'Error: {msg[:200]}'}), 500

    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)[:200]}'}), 500


@app.route('/api/info', methods=['POST'])
def get_info():
    data = request.get_json()
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'error': 'URL required'}), 400
    try:
        with yt_dlp.YoutubeDL(get_ydl_opts('best')) as ydl:
            info = ydl.extract_info(url, download=False)
            duration = info.get('duration', 0)
            m, s = divmod(int(duration), 60) if duration else (0,0)
            return jsonify({
                'title': info.get('title','Video'),
                'thumbnail': info.get('thumbnail',''),
                'duration': f'{m}:{s:02d}' if duration else '',
                'uploader': info.get('uploader',''),
            })
    except Exception as e:
        return jsonify({'error': str(e)[:200]}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
