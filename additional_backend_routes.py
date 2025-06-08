from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app import db
from models import Comment, Notification, SearchHistory, Download, WatchHistory, Favorite, Playlist, Rating
from datetime import datetime, timedelta
from sqlalchemy import desc, or_, func
import logging

additional = Blueprint('additional', __name__)

# =============================================================================
# コメント機能
# =============================================================================

@additional.route('/api/comments/<string:video_id>', methods=['GET'])
def api_get_comments(video_id):
    """動画のコメントを取得（ログイン不要）"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        
        comments = Comment.query.filter_by(video_id=video_id, is_deleted=False)\
            .order_by(desc(Comment.created_at))\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'success': True,
            'comments': [comment.to_dict() for comment in comments.items],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': comments.total,
                'pages': comments.pages,
                'has_next': comments.has_next,
                'has_prev': comments.has_prev
            }
        })
        
    except Exception as e:
        logging.error(f"コメント取得エラー: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@additional.route('/api/comments', methods=['POST'])
@login_required
def api_post_comment():
    """コメントを投稿"""
    try:
        data = request.get_json()
        video_id = data.get('video_id', '').strip()
        content = data.get('content', '').strip()
        
        if not video_id:
            return jsonify({'success': False, 'error': '動画IDは必須です。'}), 400
        
        if not content:
            return jsonify({'success': False, 'error': 'コメント内容を入力してください。'}), 400
        
        if len(content) > 1000:
            return jsonify({'success': False, 'error': 'コメントは1000文字以内で入力してください。'}), 400
        
        comment = Comment(
            user_id=current_user.id,
            video_id=video_id,
            content=content
        )
        
        db.session.add(comment)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'コメントを投稿しました。',
            'comment': comment.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"コメント投稿エラー: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@additional.route('/api/comments/<int:comment_id>', methods=['PUT'])
@login_required
def api_update_comment(comment_id):
    """コメントを編集"""
    try:
        comment = Comment.query.filter_by(id=comment_id, user_id=current_user.id).first()
        if not comment:
            return jsonify({'success': False, 'error': 'コメントが見つかりません。'}), 404
        
        if comment.is_deleted:
            return jsonify({'success': False, 'error': '削除されたコメントは編集できません。'}), 400
        
        data = request.get_json()
        content = data.get('content', '').strip()
        
        if not content:
            return jsonify({'success': False, 'error': 'コメント内容を入力してください。'}), 400
        
        if len(content) > 1000:
            return jsonify({'success': False, 'error': 'コメントは1000文字以内で入力してください。'}), 400
        
        comment.content = content
        comment.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'コメントを更新しました。',
            'comment': comment.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"コメント編集エラー: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@additional.route('/api/comments/<int:comment_id>', methods=['DELETE'])
@login_required
def api_delete_comment(comment_id):
    """コメントを削除"""
    try:
        comment = Comment.query.filter_by(id=comment_id, user_id=current_user.id).first()
        if not comment:
            return jsonify({'success': False, 'error': 'コメントが見つかりません。'}), 404
        
        comment.is_deleted = True
        comment.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'コメントを削除しました。'
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"コメント削除エラー: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@additional.route('/api/comments/<int:comment_id>/like', methods=['POST'])
@login_required
def api_like_comment(comment_id):
    """コメントにいいねを追加/削除"""
    try:
        comment = Comment.query.get_or_404(comment_id)
        
        if comment.is_deleted:
            return jsonify({'success': False, 'error': '削除されたコメントにはいいねできません。'}), 400
        
        # 簡易的ないいね機能（実際にはユーザーごとのいいね状態を管理する必要があります）
        comment.likes += 1
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'いいねしました。',
            'likes': comment.likes
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"コメントいいねエラー: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# =============================================================================
# 通知システム
# =============================================================================

@additional.route('/api/notifications', methods=['GET'])
@login_required
def api_get_notifications():
    """通知一覧を取得"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        unread_only = request.args.get('unread_only', 'false').lower() == 'true'
        
        query = Notification.query.filter_by(user_id=current_user.id)
        
        if unread_only:
            query = query.filter_by(is_read=False)
        
        notifications = query.order_by(desc(Notification.created_at))\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'success': True,
            'notifications': [notification.to_dict() for notification in notifications.items],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': notifications.total,
                'pages': notifications.pages,
                'has_next': notifications.has_next,
                'has_prev': notifications.has_prev
            },
            'unread_count': Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        })
        
    except Exception as e:
        logging.error(f"通知取得エラー: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@additional.route('/api/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def api_mark_notification_read(notification_id):
    """通知を既読にする"""
    try:
        notification = Notification.query.filter_by(id=notification_id, user_id=current_user.id).first()
        if not notification:
            return jsonify({'success': False, 'error': '通知が見つかりません。'}), 404
        
        notification.is_read = True
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '通知を既読にしました。'
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"通知既読エラー: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@additional.route('/api/notifications/read-all', methods=['POST'])
@login_required
def api_mark_all_notifications_read():
    """全ての通知を既読にする"""
    try:
        Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '全ての通知を既読にしました。'
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"全通知既読エラー: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@additional.route('/api/notifications/<int:notification_id>', methods=['DELETE'])
@login_required
def api_delete_notification(notification_id):
    """通知を削除"""
    try:
        notification = Notification.query.filter_by(id=notification_id, user_id=current_user.id).first()
        if not notification:
            return jsonify({'success': False, 'error': '通知が見つかりません。'}), 404
        
        db.session.delete(notification)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '通知を削除しました。'
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"通知削除エラー: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# =============================================================================
# 検索履歴
# =============================================================================

@additional.route('/api/search-history', methods=['GET'])
@login_required
def api_get_search_history():
    """検索履歴を取得"""
    try:
        limit = min(request.args.get('limit', 20, type=int), 100)
        
        history = SearchHistory.query.filter_by(user_id=current_user.id)\
            .order_by(desc(SearchHistory.searched_at))\
            .limit(limit).all()
        
        return jsonify({
            'success': True,
            'history': [item.to_dict() for item in history]
        })
        
    except Exception as e:
        logging.error(f"検索履歴取得エラー: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@additional.route('/api/search-history', methods=['POST'])
@login_required
def api_add_search_history():
    """検索履歴を追加"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        results_count = data.get('results_count', 0)
        
        if not query:
            return jsonify({'success': False, 'error': '検索クエリは必須です。'}), 400
        
        if len(query) > 200:
            return jsonify({'success': False, 'error': '検索クエリは200文字以内で入力してください。'}), 400
        
        # 既存の同じクエリがあれば削除（重複を避ける）
        SearchHistory.query.filter_by(user_id=current_user.id, query=query).delete()
        
        # 新しい検索履歴を追加
        search_history = SearchHistory(
            user_id=current_user.id,
            query=query,
            results_count=results_count
        )
        
        db.session.add(search_history)
        
        # 古い検索履歴を削除（最新100件のみ保持）
        old_searches = SearchHistory.query.filter_by(user_id=current_user.id)\
            .order_by(desc(SearchHistory.searched_at))\
            .offset(100).all()
        
        for old_search in old_searches:
            db.session.delete(old_search)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '検索履歴を記録しました。',
            'history': search_history.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"検索履歴追加エラー: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@additional.route('/api/search-history/<int:history_id>', methods=['DELETE'])
@login_required
def api_delete_search_history(history_id):
    """検索履歴を削除"""
    try:
        history = SearchHistory.query.filter_by(id=history_id, user_id=current_user.id).first()
        if not history:
            return jsonify({'success': False, 'error': '検索履歴が見つかりません。'}), 404
        
        db.session.delete(history)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '検索履歴を削除しました。'
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"検索履歴削除エラー: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@additional.route('/api/search-history/clear', methods=['DELETE'])
@login_required
def api_clear_search_history():
    """検索履歴を全削除"""
    try:
        SearchHistory.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '検索履歴を全て削除しました。'
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"検索履歴全削除エラー: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# =============================================================================
# ダウンロード機能
# =============================================================================

@additional.route('/api/downloads', methods=['GET'])
@login_required
def api_get_downloads():
    """ダウンロード履歴を取得"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        status = request.args.get('status')  # pending, processing, completed, failed
        
        query = Download.query.filter_by(user_id=current_user.id)
        
        if status:
            query = query.filter_by(status=status)
        
        downloads = query.order_by(desc(Download.created_at))\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'success': True,
            'downloads': [download.to_dict() for download in downloads.items],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': downloads.total,
                'pages': downloads.pages,
                'has_next': downloads.has_next,
                'has_prev': downloads.has_prev
            }
        })
        
    except Exception as e:
        logging.error(f"ダウンロード履歴取得エラー: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@additional.route('/api/downloads', methods=['POST'])
@login_required
def api_request_download():
    """ダウンロードをリクエスト"""
    try:
        data = request.get_json()
        video_id = data.get('video_id', '').strip()
        title = data.get('title', '').strip()
        quality = data.get('quality', '720p')
        format_type = data.get('format', 'mp4')  # mp4, webm, mp3
        
        if not video_id or not title:
            return jsonify({'success': False, 'error': '動画IDとタイトルは必須です。'}), 400
        
        if quality not in ['360p', '480p', '720p', '1080p', 'best']:
            return jsonify({'success': False, 'error': '無効な品質設定です。'}), 400
        
        if format_type not in ['mp4', 'webm', 'mp3']:
            return jsonify({'success': False, 'error': '無効なフォーマットです。'}), 400
        
        # 既存の同じダウンロードリクエストがあるかチェック
        existing_download = Download.query.filter_by(
            user_id=current_user.id,
            video_id=video_id,
            quality=quality,
            format=format_type,
            status='pending'
        ).first()
        
        if existing_download:
            return jsonify({
                'success': True,
                'message': '同じダウンロードリクエストが既に存在します。',
                'download': existing_download.to_dict()
            })
        
        download = Download(
            user_id=current_user.id,
            video_id=video_id,
            title=title,
            quality=quality,
            format=format_type,
            status='pending'
        )
        
        db.session.add(download)
        db.session.commit()
        
        # 実際のダウンロード処理はバックグラウンドタスクで実行
        # （この例では処理をスキップし、ステータスのみ管理）
        
        return jsonify({
            'success': True,
            'message': 'ダウンロードリクエストを受け付けました。',
            'download': download.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"ダウンロードリクエストエラー: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@additional.route('/api/downloads/<int:download_id>', methods=['DELETE'])
@login_required
def api_delete_download(download_id):
    """ダウンロード履歴を削除"""
    try:
        download = Download.query.filter_by(id=download_id, user_id=current_user.id).first()
        if not download:
            return jsonify({'success': False, 'error': 'ダウンロード履歴が見つかりません。'}), 404
        
        db.session.delete(download)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'ダウンロード履歴を削除しました。'
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"ダウンロード履歴削除エラー: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@additional.route('/api/downloads/clear', methods=['DELETE'])
@login_required
def api_clear_downloads():
    """ダウンロード履歴を全削除"""
    try:
        Download.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'ダウンロード履歴を全て削除しました。'
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"ダウンロード履歴全削除エラー: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# =============================================================================
# 統計・分析
# =============================================================================

@additional.route('/api/stats', methods=['GET'])
@login_required
def api_get_user_stats():
    """ユーザーの利用統計を取得"""
    try:
        from models import WatchHistory, Favorite, Playlist, Rating
        
        # 各種統計を取得
        stats = {
            'total_watch_time': db.session.query(func.sum(WatchHistory.watch_duration))\
                .filter_by(user_id=current_user.id).scalar() or 0,
            'videos_watched': WatchHistory.query.filter_by(user_id=current_user.id).count(),
            'favorites_count': Favorite.query.filter_by(user_id=current_user.id).count(),
            'playlists_count': Playlist.query.filter_by(user_id=current_user.id).count(),
            'comments_count': Comment.query.filter_by(user_id=current_user.id, is_deleted=False).count(),
            'likes_given': Rating.query.filter_by(user_id=current_user.id, rating='like').count(),
            'dislikes_given': Rating.query.filter_by(user_id=current_user.id, rating='dislike').count(),
        }
        
        # 今週の視聴時間
        week_ago = datetime.utcnow() - timedelta(days=7)
        stats['this_week_watch_time'] = db.session.query(func.sum(WatchHistory.watch_duration))\
            .filter(WatchHistory.user_id == current_user.id, WatchHistory.watched_at >= week_ago)\
            .scalar() or 0
        
        # 今月の視聴時間
        month_ago = datetime.utcnow() - timedelta(days=30)
        stats['this_month_watch_time'] = db.session.query(func.sum(WatchHistory.watch_duration))\
            .filter(WatchHistory.user_id == current_user.id, WatchHistory.watched_at >= month_ago)\
            .scalar() or 0
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        logging.error(f"統計取得エラー: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500