import requests
import logging
from urllib.parse import quote

class AdditionalStreamServices:
    def __init__(self):
        self.timeout = 15
    
    def get_ytsr_stream(self, video_id):
        """YTSRサービスからストリームを取得"""
        try:
            # YTSRサービスのエンドポイント（一般的なパターン）
            urls_to_try = [
                f"https://ytsr-api.vercel.app/api/video/{video_id}",
                f"https://ytsr.vercel.app/api/video/{video_id}",
                f"https://api.ytsr.org/video/{video_id}"
            ]
            
            for url in urls_to_try:
                try:
                    response = requests.get(url, timeout=self.timeout)
                    if response.status_code == 200:
                        data = response.json()
                        return self._parse_ytsr_response(data, video_id)
                except Exception as e:
                    logging.debug(f"YTSR URL {url} failed: {e}")
                    continue
            
            return None
            
        except Exception as e:
            logging.error(f"YTSRサービスエラー: {e}")
            return None
    
    def get_ytpl_stream(self, video_id):
        """YTPLサービスからストリームを取得"""
        try:
            # YTPLサービスのエンドポイント（一般的なパターン）
            urls_to_try = [
                f"https://ytpl-api.vercel.app/api/video/{video_id}",
                f"https://ytpl.vercel.app/api/video/{video_id}",
                f"https://api.ytpl.org/video/{video_id}"
            ]
            
            for url in urls_to_try:
                try:
                    response = requests.get(url, timeout=self.timeout)
                    if response.status_code == 200:
                        data = response.json()
                        return self._parse_ytpl_response(data, video_id)
                except Exception as e:
                    logging.debug(f"YTPL URL {url} failed: {e}")
                    continue
            
            return None
            
        except Exception as e:
            logging.error(f"YTPLサービスエラー: {e}")
            return None
    
    def get_wakame_high_quality_stream(self, video_id):
        """高画質ストリーム取得（wakame API）"""
        try:
            url = f"https://watawatawata.glitch.me/api/{video_id}?token=wakameoishi"
            response = requests.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                return self._parse_wakame_response(data, video_id)
            
            return None
            
        except Exception as e:
            logging.error(f"Wakame高画質サービスエラー: {e}")
            return None
    
    def _parse_ytsr_response(self, data, video_id):
        """YTSR APIレスポンスを解析"""
        try:
            formats = []
            
            if 'formats' in data:
                for fmt in data['formats']:
                    if fmt.get('url') and fmt.get('qualityLabel'):
                        formats.append({
                            'url': fmt['url'],
                            'quality': fmt['qualityLabel'],
                            'resolution': fmt.get('resolution', ''),
                            'has_audio': fmt.get('hasAudio', True),
                            'audio_url': fmt.get('audioUrl'),
                            'bitrate': fmt.get('bitrate', 0),
                            'fps': fmt.get('fps', 30),
                            'ext': fmt.get('ext', 'mp4')
                        })
            
            if formats:
                return {
                    'title': data.get('title', ''),
                    'duration': data.get('duration', 0),
                    'thumbnail': data.get('thumbnail', ''),
                    'uploader': data.get('uploader', ''),
                    'best_url': formats[0]['url'],
                    'formats': formats,
                    'source': 'YTSR'
                }
            
            return None
            
        except Exception as e:
            logging.error(f"YTSR解析エラー: {e}")
            return None
    
    def _parse_ytpl_response(self, data, video_id):
        """YTPL APIレスポンスを解析"""
        try:
            formats = []
            
            if 'videoDetails' in data and 'formats' in data['videoDetails']:
                for fmt in data['videoDetails']['formats']:
                    if fmt.get('url') and fmt.get('qualityLabel'):
                        formats.append({
                            'url': fmt['url'],
                            'quality': fmt['qualityLabel'],
                            'resolution': fmt.get('resolution', ''),
                            'has_audio': fmt.get('hasAudio', True),
                            'audio_url': fmt.get('audioUrl'),
                            'bitrate': fmt.get('bitrate', 0),
                            'fps': fmt.get('fps', 30),
                            'ext': fmt.get('ext', 'mp4')
                        })
            
            if formats:
                video_details = data.get('videoDetails', {})
                return {
                    'title': video_details.get('title', ''),
                    'duration': video_details.get('lengthSeconds', 0),
                    'thumbnail': video_details.get('thumbnail', {}).get('thumbnails', [{}])[-1].get('url', ''),
                    'uploader': video_details.get('author', ''),
                    'best_url': formats[0]['url'],
                    'formats': formats,
                    'source': 'YTPL'
                }
            
            return None
            
        except Exception as e:
            logging.error(f"YTPL解析エラー: {e}")
            return None
    
    def _parse_wakame_response(self, data, video_id):
        """Wakame高画質APIレスポンスを解析"""
        try:
            formats = []
            
            # Wakame APIの構造に応じて調整
            if 'videoUrl' in data:
                formats.append({
                    'url': data['videoUrl'],
                    'quality': data.get('quality', '1080p'),
                    'resolution': data.get('resolution', '1920x1080'),
                    'has_audio': True,
                    'audio_url': data.get('audioUrl'),
                    'bitrate': data.get('bitrate', 0),
                    'fps': data.get('fps', 60),
                    'ext': 'mp4'
                })
            elif 'formats' in data:
                for fmt in data['formats']:
                    if fmt.get('url'):
                        formats.append({
                            'url': fmt['url'],
                            'quality': fmt.get('quality', 'high'),
                            'resolution': fmt.get('resolution', ''),
                            'has_audio': fmt.get('hasAudio', True),
                            'audio_url': fmt.get('audioUrl'),
                            'bitrate': fmt.get('bitrate', 0),
                            'fps': fmt.get('fps', 60),
                            'ext': fmt.get('ext', 'mp4')
                        })
            
            if formats:
                return {
                    'title': data.get('title', ''),
                    'duration': data.get('duration', 0),
                    'thumbnail': data.get('thumbnail', ''),
                    'uploader': data.get('uploader', ''),
                    'best_url': formats[0]['url'],
                    'formats': formats,
                    'source': 'Wakame High Quality'
                }
            
            return None
            
        except Exception as e:
            logging.error(f"Wakame解析エラー: {e}")
            return None