import requests
import logging
import time
from functools import lru_cache
from config import INVIDIOUS_INSTANCES, REQUEST_TIMEOUT
import random

class InvidiousService:
    def __init__(self):
        self.instances = INVIDIOUS_INSTANCES.copy()
        # 優先インスタンスを使用するため、シャッフルしない
        self._cache = {}
        self._cache_timeout = 300  # 5分間キャッシュ
        self._failed_instances = {}  # 失敗したインスタンスを一時的に記録
        self._failure_timeout = 180  # 3分間は失敗したインスタンスを避ける
    
    def _make_request(self, endpoint, params=None):
        """複数のインスタンスでリクエストを試行（キャッシュ付き）"""
        # キャッシュキーを作成
        cache_key = f"{endpoint}:{str(params) if params else ''}"
        current_time = time.time()
        
        # キャッシュチェック
        if cache_key in self._cache:
            cached_data, timestamp = self._cache[cache_key]
            if current_time - timestamp < self._cache_timeout:
                return cached_data
        
        # キャッシュがない場合はAPIリクエスト
        for instance in self.instances:
            # 失敗したインスタンスを一時的に避ける
            if instance in self._failed_instances:
                failure_time = self._failed_instances[instance]
                if current_time - failure_time < self._failure_timeout:
                    continue
                else:
                    # タイムアウト経過後は再試行
                    del self._failed_instances[instance]
            
            try:
                url = f"{instance.rstrip('/')}/api/v1/{endpoint}"
                response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
                if response.status_code == 200:
                    data = response.json()
                    # キャッシュに保存
                    self._cache[cache_key] = (data, current_time)
                    return data
                else:
                    # HTTPエラーも記録
                    self._failed_instances[instance] = current_time
            except Exception as e:
                logging.warning(f"インスタンス {instance} でエラー: {e}")
                self._failed_instances[instance] = current_time
                continue
        
        raise Exception("すべてのInvidiousインスタンスで失敗しました")
    
    def search_videos(self, query, page=1, sort_by='relevance'):
        """動画検索"""
        params = {
            'q': query,
            'page': page,
            'sort_by': sort_by,
            'type': 'video'
        }
        
        try:
            results = self._make_request('search', params)
            return results if results else []
        except Exception as e:
            logging.error(f"検索エラー: {e}")
            return []

    def search_all(self, query, page=1, sort_by='relevance'):
        """動画とチャンネルを両方検索"""
        params = {
            'q': query,
            'page': page,
            'sort_by': sort_by,
            'type': 'all'
        }
        
        try:
            results = self._make_request('search', params)
            if results:
                # 結果をタイプ別に分離
                videos = [item for item in results if item.get('type') == 'video']
                channels = [item for item in results if item.get('type') == 'channel']
                return {
                    'videos': videos,
                    'channels': channels
                }
            return {'videos': [], 'channels': []}
        except Exception as e:
            logging.error(f"統合検索エラー: {e}")
            return {'videos': [], 'channels': []}
    
    def get_video_info(self, video_id):
        """動画情報取得"""
        try:
            return self._make_request(f'videos/{video_id}')
        except Exception as e:
            logging.error(f"動画情報取得エラー: {e}")
            return None
    
    def get_video_formats(self, video_id):
        """動画フォーマット取得"""
        try:
            video_info = self.get_video_info(video_id)
            if video_info and 'formatStreams' in video_info:
                return video_info['formatStreams']
            return []
        except Exception as e:
            logging.error(f"フォーマット取得エラー: {e}")
            return []
    
    def get_stream_urls(self, video_id):
        """Invidiousから直接ストリームURLを取得"""
        try:
            video_info = self.get_video_info(video_id)
            if not video_info:
                return None
            
            # フォーマットストリームを取得
            format_streams = video_info.get('formatStreams', [])
            adaptive_formats = video_info.get('adaptiveFormats', [])
            
            formats = []
            
            # 通常のフォーマット（音声付き）- 360p以外は分離音声に変更
            for fmt in format_streams:
                if fmt.get('url') and fmt.get('qualityLabel'):
                    quality = fmt['qualityLabel']
                    # 360p以外は音声を分離
                    if quality != '360p':
                        formats.append({
                            'url': fmt['url'],
                            'quality': quality,
                            'resolution': fmt.get('resolution', f"{fmt.get('width', '?')}x{fmt.get('height', '?')}"),
                            'has_audio': False,  # 360p以外は分離音声使用
                            'audio_url': None,  # 後で最高品質音声を設定
                            'bitrate': fmt.get('bitrate', 0),
                            'fps': fmt.get('fps', 30),
                            'ext': fmt.get('container', 'mp4')
                        })
                    else:
                        # 360pのみ音声付きのまま
                        formats.append({
                            'url': fmt['url'],
                            'quality': quality,
                            'resolution': fmt.get('resolution', f"{fmt.get('width', '?')}x{fmt.get('height', '?')}"),
                            'has_audio': True,
                            'audio_url': None,
                            'bitrate': fmt.get('bitrate', 0),
                            'fps': fmt.get('fps', 30),
                            'ext': fmt.get('container', 'mp4')
                        })
            
            # アダプティブフォーマット（高品質、音声分離）
            video_formats = [f for f in adaptive_formats if f.get('type', '').startswith('video/')]
            audio_formats = [f for f in adaptive_formats if f.get('type', '').startswith('audio/')]
            
            # 最高品質の音声を取得
            best_audio = None
            if audio_formats:
                best_audio = max(audio_formats, key=lambda x: x.get('bitrate', 0))
            
            # 動画フォーマットを追加
            for fmt in video_formats:
                if fmt.get('url') and fmt.get('qualityLabel'):
                    formats.append({
                        'url': fmt['url'],
                        'quality': fmt['qualityLabel'],
                        'resolution': fmt.get('resolution', f"{fmt.get('width', '?')}x{fmt.get('height', '?')}"),
                        'has_audio': False,
                        'audio_url': best_audio['url'] if best_audio else None,
                        'bitrate': fmt.get('bitrate', 0),
                        'fps': fmt.get('fps', 30),
                        'ext': fmt.get('container', 'mp4')
                    })
            
            # 360p以外のフォーマットに音声URLを設定
            if best_audio:
                for fmt in formats:
                    if fmt['quality'] != '360p' and not fmt['has_audio']:
                        fmt['audio_url'] = best_audio['url']
            
            # 重複を除去し、品質でソート
            unique_formats = []
            seen_qualities = set()
            
            for fmt in formats:
                if fmt['quality'] not in seen_qualities:
                    seen_qualities.add(fmt['quality'])
                    unique_formats.append(fmt)
            
            # 音声付きフォーマットを優先してソート
            def extract_quality_number(quality):
                import re
                match = re.search(r'(\d+)', quality)
                return int(match.group(1)) if match else 0
            
            # 音声付きフォーマットを最初に配置
            audio_enabled_formats = [f for f in unique_formats if f['has_audio']]
            video_only_formats = [f for f in unique_formats if not f['has_audio']]
            
            # それぞれを品質でソート
            audio_enabled_formats.sort(key=lambda x: extract_quality_number(x['quality']), reverse=True)
            video_only_formats.sort(key=lambda x: extract_quality_number(x['quality']), reverse=True)
            
            # 音声付きを優先して結合
            final_formats = audio_enabled_formats + video_only_formats
            
            if not final_formats:
                return None
            
            # 最良のストリーム（音声付き優先）を選択
            best_stream = final_formats[0]
            
            return {
                'title': video_info.get('title', ''),
                'duration': video_info.get('lengthSeconds', 0),
                'thumbnail': video_info.get('videoThumbnails', [{}])[0].get('url', ''),
                'uploader': video_info.get('author', ''),
                'best_url': best_stream['url'],
                'has_audio': best_stream['has_audio'],
                'audio_url': best_stream['audio_url'],
                'formats': final_formats
            }
            
        except Exception as e:
            logging.error(f"Invidiousストリーム取得エラー: {e}")
            return None
    
    def get_channel_info(self, channel_id):
        """チャンネル情報を取得"""
        try:
            endpoint = f"api/v1/channels/{channel_id}"
            
            # 各インスタンスで試行
            for instance in self.instances:
                try:
                    url = f"{instance}{endpoint}"
                    response = requests.get(url, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        return {
                            'author': data.get('author', ''),
                            'authorId': data.get('authorId', channel_id),
                            'description': data.get('description', ''),
                            'subCount': data.get('subCount', 0),
                            'totalViews': data.get('totalViews', 0),
                            'videoCount': data.get('videoCount', 0),
                            'joined': data.get('joined', 0),
                            'authorThumbnails': data.get('authorThumbnails', []),
                            'authorBanners': data.get('authorBanners', []),
                            'autoGenerated': data.get('autoGenerated', False)
                        }
                except requests.RequestException as e:
                    logging.warning(f"チャンネル情報取得失敗 {instance}: {e}")
                    continue
                    
            logging.error(f"全てのインスタンスでチャンネル情報取得に失敗: {channel_id}")
            return None
            
        except Exception as e:
            logging.error(f"チャンネル情報取得エラー: {str(e)}")
            return None
    
    def get_channel_videos(self, channel_id, page=1, sort='newest'):
        """チャンネルの動画一覧を取得"""
        try:
            endpoint = f"/api/v1/channels/{channel_id}/videos"
            params = {
                'page': page,
                'sort_by': sort
            }
            data = self._make_request(endpoint, params)
            
            if data:
                videos = []
                for video in data:
                    videos.append({
                        'videoId': video.get('videoId', ''),
                        'title': video.get('title', ''),
                        'description': video.get('description', ''),
                        'videoThumbnails': video.get('videoThumbnails', []),
                        'lengthSeconds': video.get('lengthSeconds', 0),
                        'viewCount': video.get('viewCount', 0),
                        'author': video.get('author', ''),
                        'authorId': video.get('authorId', ''),
                        'publishedText': video.get('publishedText', ''),
                        'published': video.get('published', 0)
                    })
                return videos
        except Exception as e:
            logging.error(f"チャンネル動画取得エラー: {str(e)}")
            return []

    def get_trending_videos(self, region='JP'):
        """トレンド動画を取得（件数を増加）"""
        try:
            # 通常のトレンド動画を取得
            endpoint = "trending"
            params = {'region': region}
            data = self._make_request(endpoint, params)
            
            all_videos = []
            if data:
                for video in data[:30]:  # 30件に増加
                    all_videos.append({
                        'videoId': video.get('videoId', ''),
                        'title': video.get('title', ''),
                        'description': video.get('description', ''),
                        'videoThumbnails': video.get('videoThumbnails', []),
                        'lengthSeconds': video.get('lengthSeconds', 0),
                        'viewCount': video.get('viewCount', 0),
                        'author': video.get('author', ''),
                        'authorId': video.get('authorId', ''),
                        'publishedText': video.get('publishedText', ''),
                        'published': video.get('published', 0)
                    })
            
            # 追加のカテゴリからも取得
            try:
                for category in ['Music', 'Gaming']:
                    cat_params = {'region': region, 'type': category}
                    cat_data = self._make_request(endpoint, cat_params)
                    if cat_data:
                        for video in cat_data[:10]:
                            all_videos.append({
                                'videoId': video.get('videoId', ''),
                                'title': video.get('title', ''),
                                'description': video.get('description', ''),
                                'videoThumbnails': video.get('videoThumbnails', []),
                                'lengthSeconds': video.get('lengthSeconds', 0),
                                'viewCount': video.get('viewCount', 0),
                                'author': video.get('author', ''),
                                'authorId': video.get('authorId', ''),
                                'publishedText': video.get('publishedText', ''),
                                'published': video.get('published', 0)
                            })
            except:
                pass
                
            return all_videos
        except Exception as e:
            logging.error(f"トレンド動画取得エラー: {str(e)}")
            return []

    def get_video_comments(self, video_id, continuation=None):
        """動画のコメントを取得"""
        try:
            endpoint = f"comments/{video_id}"
            params = {}
            if continuation:
                params['continuation'] = continuation
                
            data = self._make_request(endpoint, params)
            
            if data:
                comments = []
                for comment in data.get('comments', []):
                    comments.append({
                        'author': comment.get('author', ''),
                        'authorId': comment.get('authorId', ''),
                        'authorThumbnails': comment.get('authorThumbnails', []),
                        'content': comment.get('content', ''),
                        'published': comment.get('published', 0),
                        'publishedText': comment.get('publishedText', ''),
                        'likeCount': comment.get('likeCount', 0),
                        'replies': comment.get('replies', {}).get('replyCount', 0),
                        'isOwner': comment.get('authorIsChannelOwner', False),
                        'isPinned': comment.get('isPinned', False)
                    })
                
                return {
                    'comments': comments,
                    'continuation': data.get('continuation'),
                    'commentCount': data.get('commentCount', 0)
                }
            return {'comments': [], 'continuation': None, 'commentCount': 0}
        except Exception as e:
            logging.error(f"コメント取得エラー: {str(e)}")
            return {'comments': [], 'continuation': None, 'commentCount': 0}
