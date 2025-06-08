from flask import render_template, request, jsonify, redirect, url_for
from app import app
from invidious_service import InvidiousService
from piped_service import PipedService
from ytdl_service import YtdlService
from additional_services import AdditionalStreamServices
from turbo_video_service import TurboVideoService
from user_preferences import user_prefs
import logging

invidious = InvidiousService()
piped = PipedService()
ytdl = YtdlService()
additional_services = AdditionalStreamServices()
turbo_service = TurboVideoService()

@app.route('/')
def index():
    try:
        # 複数のAPIから急上昇動画を取得して統合
        trending_videos = []
        
        # Invidiousから取得
        try:
            invidious_trending = invidious.get_trending_videos('JP')
            trending_videos.extend(invidious_trending[:30])
        except Exception as e:
            logging.warning(f"Invidious trending error: {e}")
        
        # TODO: Piped APIは現在不安定なため無効化
        # try:
        #     piped_trending = piped.get_trending_videos('JP')
        #     trending_videos.extend(piped_trending[:30])
        # except Exception as e:
        #     logging.warning(f"Piped trending error: {e}")
        
        # 重複を除去（動画IDベース）
        seen_ids = set()
        unique_videos = []
        for video in trending_videos:
            video_id = video.get('videoId')
            if video_id and video_id not in seen_ids:
                seen_ids.add(video_id)
                unique_videos.append(video)
        
        # 最大50件まで表示
        return render_template('index.html', trending_videos=unique_videos[:50])
    except Exception as e:
        logging.error(f"トレンド動画取得エラー: {e}")
        return render_template('index.html', trending_videos=[])

@app.route('/search')
def search():
    query = request.args.get('q', '')
    page = int(request.args.get('page', 1))
    
    if not query:
        return redirect(url_for('index'))
    
    try:
        # 並行して複数のAPIから動画を検索
        all_videos = []
        channels = []
        
        # Invidiousで検索
        try:
            invidious_videos = invidious.search_videos(query, page=page)
            all_videos.extend(invidious_videos)
            
            # チャンネル検索（1ページ目のみ）
            if page == 1:
                try:
                    all_results = invidious.search_all(query, page=1)
                    channels = all_results.get('channels', [])[:3]
                except:
                    channels = []
                    
        except Exception as e:
            logging.warning(f"Invidious search error: {e}")
        
        # TODO: Piped APIは現在不安定なため無効化
        # try:
        #     piped_videos = piped.search_videos(query, page=page)
        #     all_videos.extend(piped_videos)
        # except Exception as e:
        #     logging.warning(f"Piped search error: {e}")
        
        # 重複を除去（動画IDベース）
        seen_ids = set()
        unique_videos = []
        for video in all_videos:
            video_id = video.get('videoId')
            if video_id and video_id not in seen_ids:
                seen_ids.add(video_id)
                unique_videos.append(video)
        
        # ページネーション用に適切な数で切り出し
        start_idx = (page - 1) * 20
        end_idx = start_idx + 20
        paginated_videos = unique_videos[start_idx:end_idx]
        
        return render_template('search.html', 
                             results=paginated_videos,
                             channels=channels if page == 1 else [],
                             query=query, 
                             page=page)
    except Exception as e:
        logging.error(f"検索エラー: {e}")
        return render_template('search.html', 
                             results=[], 
                             channels=[],
                             query=query, 
                             page=page)

@app.route('/watch')
def watch():
    video_id = request.args.get('v')
    if not video_id:
        return redirect(url_for('index'))
    try:
        # 動画情報を1回だけ取得
        video_info = invidious.get_video_info(video_id)
        if not video_info:
            return render_template('watch.html', error="動画が見つかりません。")
        
        # ストリーム取得を高速化 - 最も確実なソースから順番に
        stream_data = None
        
        # 1. Invidiousから直接取得（最速）
        try:
            stream_data = invidious.get_stream_urls(video_id)
        except Exception as e:
            logging.warning(f"Invidious stream error: {e}")
        
        # 2. yt-dlpを試行
        if not stream_data:
            try:
                stream_data = ytdl.get_stream_urls(video_id)
            except Exception as e:
                logging.warning(f"ytdl stream error: {e}")
        
        # 3. 追加サービスを試行
        if not stream_data:
            try:
                stream_data = additional_services.get_wakame_high_quality_stream(video_id)
            except Exception as e:
                logging.warning(f"Additional services error: {e}")
        
        if not stream_data:
            return render_template('watch.html', 
                                 video_info=video_info,
                                 error="動画のストリームURLを取得できませんでした。")
        
        # コメントを非同期で取得（最小限）
        comments_data = {'comments': [], 'continuation': None}
        try:
            comments_data = invidious.get_video_comments(video_id)
        except Exception as e:
            logging.warning(f"Comments error: {e}")
        
        # 視聴履歴を記録
        user_prefs.record_watch(video_info)
        
        return render_template('watch.html', 
                             video_info=video_info,
                             stream_data=stream_data,
                             comments_data=comments_data)
    except Exception as e:
        logging.error(f"動画取得エラー: {e}")
        return render_template('watch.html', 
                             error="動画の読み込み中にエラーが発生しました。")

@app.route('/channel/<channel_id>')
def channel(channel_id):
    """チャンネルページ - 速度改善版"""
    try:
        # ページ番号、チャンネル名、ソート順を取得
        page = int(request.args.get('page', 1))
        channel_name = request.args.get('name', '')
        sort = request.args.get('sort', 'newest')
        
        # 直接チャンネル情報を取得（高速化）
        channel_info = invidious.get_channel_info(channel_id)
        if not channel_info and channel_name:
            # フォールバック: チャンネル名で基本情報作成
            channel_info = {
                'author': channel_name,
                'authorId': channel_id,
                'description': f'{channel_name}のチャンネル',
                'subCount': 0,
                'totalViews': 0,
                'videoCount': 0,
                'joined': 0,
                'authorThumbnails': [],
                'authorBanners': [],
                'autoGenerated': False
            }
        
        # チャンネル動画を直接取得（高速化）
        videos = invidious.get_channel_videos(channel_id, page=page, sort=sort)
        
        # フォールバック: 検索による動画取得
        if not videos and channel_name:
            search_results = invidious.search_videos(f"channel:{channel_name}", page=page)
            videos = [video for video in search_results 
                     if video.get('authorId') == channel_id or 
                        (channel_name and video.get('author', '').lower() == channel_name.lower())]
        
        # ページネーション設定（簡易版）
        videos = videos or []
        total_pages = max(1, page + (1 if len(videos) >= 20 else 0))
        
        # チャンネル情報が無い場合の最終フォールバック
        if not channel_info:
            channel_info = {
                'author': videos[0].get('author', channel_name) if videos else (channel_name or f'チャンネル ({channel_id})'),
                'authorId': channel_id,
                'description': 'チャンネル動画一覧',
                'subCount': 0,
                'totalViews': 0,
                'videoCount': len(videos) if videos else 0,
                'joined': 0,
                'authorThumbnails': videos[0].get('authorThumbnails', []) if videos else [],
                'authorBanners': [],
                'autoGenerated': False
            }
        
        return render_template('channel.html',
                             channel_info=channel_info,
                             videos=videos,
                             current_page=page,
                             total_pages=total_pages,
                             sort=sort)
        
    except Exception as e:
        logging.error(f"Channel page error: {e}")
        channel_name = request.args.get('name', '')
        
        # エラー時も基本的なページを表示
        channel_info = {
            'author': channel_name if channel_name else f'チャンネル ({channel_id})',
            'authorId': channel_id,
            'description': 'チャンネル情報の読み込み中にエラーが発生しました。',
            'subCount': 0,
            'totalViews': 0,
            'videoCount': 0,
            'joined': 0,
            'authorThumbnails': [],
            'authorBanners': [],
            'autoGenerated': False
        }
        
        return render_template('channel.html',
                             channel_info=channel_info,
                             videos=[],
                             current_page=1,
                             total_pages=1,
                             sort='newest',
                             error="チャンネル情報の読み込み中にエラーが発生しました")

@app.route('/shorts')
def shorts():
    """ショート動画メインページ（最初の動画にリダイレクト）"""
    try:
        # 最初のショート動画を取得
        response = api_shorts_list()
        if response.get('success') and response.get('videos'):
            first_video_id = response['videos'][0]['videoId']
            return redirect(url_for('shorts_video', video_id=first_video_id))
        else:
            return render_template('shorts.html', error="ショート動画が見つかりません")
    except Exception as e:
        logging.error(f"ショート動画リダイレクトエラー: {e}")
        return render_template('shorts.html', error="エラーが発生しました")

@app.route('/shorts/<video_id>')
def shorts_video(video_id):
    """個別ショート動画ページ"""
    try:
        # 動画情報を取得
        video_info = invidious.get_video_info(video_id)
        if not video_info:
            return redirect(url_for('shorts'))
        
        # 視聴履歴を記録
        user_prefs.record_watch(video_info)
        
        # コメントを取得
        comments_data = {'comments': [], 'continuation': None}
        try:
            comments_data = invidious.get_video_comments(video_id)
        except Exception as e:
            logging.warning(f"Comments error: {e}")
        
        return render_template('shorts.html', 
                             current_video=video_info,
                             current_video_id=video_id,
                             comments_data=comments_data)
    except Exception as e:
        logging.error(f"ショート動画取得エラー: {e}")
        return redirect(url_for('shorts'))

@app.route('/api/shorts-list')
def api_shorts_list():
    """個人化された日本のショート動画リストAPI - 大幅改善版"""
    try:
        shorts_videos = []
        
        # ユーザーの好みに基づいた推奨キーワードを取得
        recommended_keywords = user_prefs.get_recommendation_keywords()
        logging.info(f"推奨キーワード: {recommended_keywords[:5]}")
        
        # より多くのソースから動画を収集
        search_queries = []
        
        # 好みのチャンネルからの動画を優先検索
        preferred_channels = user_prefs.get_preferred_channels()
        for channel_name, count in preferred_channels[:5]:  # 上位5チャンネル
            search_queries.append(f"channel:{channel_name}")
        
        # 推奨キーワード追加
        search_queries.extend(recommended_keywords[:15])
        
        # 日本の人気ジャンル追加
        popular_genres = [
            "面白い", "おもしろ", "爆笑", "ネタ", "コメディ",
            "料理", "レシピ", "簡単", "DIY", "手作り",
            "ダンス", "踊り", "TikTok", "バズった",
            "猫", "犬", "ペット", "動物", "可愛い",
            "ゲーム", "実況", "攻略", "プレイ",
            "メイク", "ファッション", "コーデ", "美容",
            "スポーツ", "サッカー", "野球", "バスケ",
            "歌ってみた", "弾いてみた", "演奏", "カバー",
            "vlog", "日常", "ルーティン", "モーニング"
        ]
        search_queries.extend(popular_genres)
        
        # 検索実行
        for query in search_queries[:25]:  # 最大25クエリ
            try:
                search_results = invidious.search_videos(query, page=1)
                if search_results and isinstance(search_results, list):
                    videos_list = search_results[:6]  # 各クエリから6件
                elif search_results and search_results.get('success'):
                    videos_list = search_results.get('videos', [])[:6]
                else:
                    videos_list = []
                
                for video in videos_list:
                        duration = video.get('lengthSeconds', 0)
                        if 10 <= duration <= 300:  # 10秒～5分に拡大
                            video_id = video.get('videoId')
                            if video_id not in [v.get('videoId') for v in shorts_videos]:
                                if user_prefs.should_recommend_video(video):
                                    shorts_videos.append(video)
                                    if len(shorts_videos) >= 80:  # 80件まで収集
                                        break
                
                if len(shorts_videos) >= 80:
                    break
                    
            except Exception as e:
                logging.warning(f"検索エラー ({query}): {e}")
                continue
        
        # トレンド動画からも大量追加
        trending_types = ['', 'Music', 'Gaming']
        for trend_type in trending_types:
            if len(shorts_videos) >= 80:
                break
                
            try:
                if trend_type:
                    trending_videos = invidious.get_trending_videos(region='JP')
                else:
                    trending_videos = invidious.get_trending_videos(region='JP')
                
                if trending_videos:
                    videos_list = trending_videos if isinstance(trending_videos, list) else trending_videos.get('videos', [])
                    for video in videos_list[:15]:  # トレンドから15件
                        duration = video.get('lengthSeconds', 0)
                        if 10 <= duration <= 300:  # 範囲拡大
                            video_id = video.get('videoId')
                            if video_id not in [v.get('videoId') for v in shorts_videos]:
                                if user_prefs.should_recommend_video(video):
                                    shorts_videos.append(video)
                                    if len(shorts_videos) >= 80:
                                        break
            except Exception as e:
                logging.warning(f"トレンド動画取得エラー: {e}")
        
        # 多様性を保つため、ランダムに並び替え
        import random
        random.shuffle(shorts_videos)
        
        # 短い動画を優先しつつ、多様性も保つ
        shorts_videos.sort(key=lambda x: (x.get('lengthSeconds', 0), random.random()))
        
        logging.info(f"ショート動画 {len(shorts_videos)} 件を取得")
        
        return jsonify({
            'success': True,
            'videos': shorts_videos,  # 全件返す
            'has_more': True,  # 常に追加読み込み可能
            'total': len(shorts_videos)
        })
    except Exception as e:
        logging.error(f"ショート動画リスト取得エラー: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'videos': []
        })

@app.route('/api/shorts-next/<current_video_id>')
def api_shorts_next(current_video_id):
    """次のショート動画を取得"""
    try:
        # 現在の動画リストを取得
        response = api_shorts_list()
        if hasattr(response, 'get_json'):
            response_data = response.get_json()
        else:
            response_data = response
            
        if not response_data.get('success'):
            return jsonify({'success': False, 'error': 'No videos available'})
        
        videos = response_data['videos']
        current_index = -1
        
        # 現在の動画のインデックスを探す
        for i, video in enumerate(videos):
            if video.get('videoId') == current_video_id:
                current_index = i
                break
        
        # 次の動画を取得
        next_index = current_index + 1
        if next_index < len(videos):
            return jsonify({
                'success': True,
                'video': videos[next_index],
                'has_next': next_index + 1 < len(videos)
            })
        else:
            # 新しい動画を生成して追加
            import random
            additional_keywords = ["エンタメ", "動物", "グルメ", "スポーツ", "技術"]
            for keyword in additional_keywords:
                try:
                    search_results = invidious.search_videos(keyword, page=random.randint(1, 3))
                    for video in search_results[:2]:
                        duration = video.get('lengthSeconds', 0)
                        if 15 <= duration <= 180:
                            if user_prefs.should_recommend_video(video):
                                return jsonify({
                                    'success': True,
                                    'video': video,
                                    'has_next': True
                                })
                except:
                    continue
            
            return jsonify({'success': False, 'error': 'No more videos'})
            
    except Exception as e:
        logging.error(f"次の動画取得エラー: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/shorts-prev/<current_video_id>')
def api_shorts_prev(current_video_id):
    """前のショート動画を取得"""
    try:
        response = api_shorts_list()
        if not response.get('success'):
            return jsonify({'success': False, 'error': 'No videos available'})
        
        videos = response['videos']
        current_index = -1
        
        for i, video in enumerate(videos):
            if video.get('videoId') == current_video_id:
                current_index = i
                break
        
        prev_index = current_index - 1
        if prev_index >= 0:
            return jsonify({
                'success': True,
                'video': videos[prev_index],
                'has_prev': prev_index > 0
            })
        else:
            return jsonify({'success': False, 'error': 'No previous videos'})
            
    except Exception as e:
        logging.error(f"前の動画取得エラー: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/comments/<video_id>')
def api_comments(video_id):
    """ショート動画コメント取得API"""
    try:
        comments_data = invidious.get_video_comments(video_id)
        return jsonify({
            'success': True,
            'comments': comments_data.get('comments', []),
            'commentCount': comments_data.get('commentCount', 0)
        })
    except Exception as e:
        logging.error(f"コメント取得エラー: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'comments': []
        })

@app.route('/api/stream/<video_id>')
def api_stream(video_id):
    """APIエンドポイント：動画ストリーム取得 - 音声付き優先"""
    try:
        # Invidiousサービスを最優先（安定性重視）
        invidious_result = invidious.get_stream_urls(video_id)
        if invidious_result:
            # 720p以上の品質を探す
            best_url = None
            audio_url = None
            has_audio = True
            
            # 適切なフォーマットを選択
            if isinstance(invidious_result, dict):
                if invidious_result.get('formats'):
                    # 720p音声付きを優先
                    for fmt in invidious_result.get('formats', []):
                        if fmt.get('quality') and '720' in str(fmt.get('quality')):
                            best_url = fmt.get('url')
                            break
                    
                    # フォールバック：最高品質
                    if not best_url and invidious_result.get('formats'):
                        best_url = invidious_result['formats'][0].get('url')
                
                elif invidious_result.get('video_url'):
                    best_url = invidious_result.get('video_url')
                    audio_url = invidious_result.get('audio_url')
                    has_audio = invidious_result.get('has_audio', True)
            
            if best_url:
                response_data = {
                    "success": True,
                    "stream_url": best_url,
                    "audio_url": audio_url,
                    "has_audio": has_audio,
                    "title": invidious_result.get('title', ''),
                    "duration": invidious_result.get('duration', 0),
                    "quality": "720p",
                    "source": "invidious"
                }
                return jsonify(response_data)
        
        # フォールバック：yt-dlp（簡単なフォーマット指定）
        try:
            ytdl_result = ytdl.get_stream_urls(video_id)
            if ytdl_result and ytdl_result.get('success'):
                response_data = {
                    "success": True,
                    "stream_url": ytdl_result.get('best_url') or ytdl_result.get('video_url'),
                    "has_audio": True,
                    "title": ytdl_result.get('title', ''),
                    "duration": ytdl_result.get('duration', 0),
                    "quality": "auto",
                    "source": "ytdl"
                }
                return jsonify(response_data)
        except Exception as e:
            logging.warning(f"yt-dlp失敗: {e}")
        
        return jsonify({
            "success": False,
            "error": "動画の取得に失敗しました。著作権制限により再生できない可能性があります。",
            "copyright_restricted": True
        }), 404
            
    except Exception as e:
        logging.error(f"ストリームAPI エラー: {e}")
        return jsonify({"success": False, "error": str(e)}), 500



@app.errorhandler(404)
def not_found(error):
    return render_template('base.html', error="ページが見つかりません。"), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('base.html', error="内部サーバーエラーが発生しました。"), 500
