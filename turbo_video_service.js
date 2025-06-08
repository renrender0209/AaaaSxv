const ytdl = require('ytdl-core');
const YouTubeSearchAPI = require('youtube-search-api');

class TurboVideoService {
    constructor() {
        this.cache = new Map();
        this.maxCacheSize = 1000;
        this.requestQueue = [];
        this.processing = false;
    }

    async getVideoStream(videoId, quality = '720p') {
        try {
            // キャッシュチェック
            const cacheKey = `${videoId}_${quality}`;
            if (this.cache.has(cacheKey)) {
                const cached = this.cache.get(cacheKey);
                if (Date.now() - cached.timestamp < 300000) { // 5分間キャッシュ
                    return cached.data;
                }
            }

            // 高速取得開始
            const videoUrl = `https://www.youtube.com/watch?v=${videoId}`;
            
            // 並列でフォーマット情報を取得
            const [info, formats] = await Promise.all([
                ytdl.getBasicInfo(videoUrl),
                ytdl.getInfo(videoUrl).then(info => info.formats)
            ]);

            // 720p音声付きフォーマットを優先選択
            const videoFormats = formats.filter(f => f.hasVideo && f.hasAudio);
            const audioOnlyFormats = formats.filter(f => !f.hasVideo && f.hasAudio);
            const videoOnlyFormats = formats.filter(f => f.hasVideo && !f.hasAudio);

            // 720p音声付きを探す
            let bestFormat = videoFormats.find(f => 
                f.qualityLabel === '720p' || 
                (f.height === 720 && f.hasAudio)
            );

            // フォールバック: 最高品質の音声付き動画
            if (!bestFormat) {
                bestFormat = videoFormats
                    .filter(f => f.hasAudio && f.height >= 480)
                    .sort((a, b) => b.height - a.height)[0];
            }

            // 分離音声・動画対応
            let audioFormat = null;
            let videoFormat = null;

            if (!bestFormat && videoOnlyFormats.length > 0) {
                videoFormat = videoOnlyFormats
                    .filter(f => f.height === 720 || f.qualityLabel === '720p')
                    .sort((a, b) => b.height - a.height)[0];
                
                audioFormat = audioOnlyFormats
                    .sort((a, b) => b.audioBitrate - a.audioBitrate)[0];
            }

            const result = {
                success: true,
                videoId: videoId,
                title: info.videoDetails.title,
                duration: parseInt(info.videoDetails.lengthSeconds),
                author: info.videoDetails.author.name,
                thumbnail: info.videoDetails.thumbnails?.[0]?.url,
                formats: {
                    combined: bestFormat ? {
                        url: bestFormat.url,
                        quality: bestFormat.qualityLabel || `${bestFormat.height}p`,
                        hasAudio: true,
                        hasVideo: true,
                        container: bestFormat.container,
                        bitrate: bestFormat.bitrate
                    } : null,
                    video: videoFormat ? {
                        url: videoFormat.url,
                        quality: videoFormat.qualityLabel || `${videoFormat.height}p`,
                        hasAudio: false,
                        hasVideo: true,
                        container: videoFormat.container,
                        bitrate: videoFormat.bitrate
                    } : null,
                    audio: audioFormat ? {
                        url: audioFormat.url,
                        quality: 'audio',
                        hasAudio: true,
                        hasVideo: false,
                        container: audioFormat.container,
                        bitrate: audioFormat.audioBitrate
                    } : null
                },
                allFormats: formats.map(f => ({
                    quality: f.qualityLabel || `${f.height}p`,
                    url: f.url,
                    hasAudio: f.hasAudio,
                    hasVideo: f.hasVideo,
                    container: f.container,
                    bitrate: f.bitrate || f.audioBitrate
                }))
            };

            // キャッシュに保存
            this.cache.set(cacheKey, {
                data: result,
                timestamp: Date.now()
            });

            // キャッシュサイズ制限
            if (this.cache.size > this.maxCacheSize) {
                const firstKey = this.cache.keys().next().value;
                this.cache.delete(firstKey);
            }

            return result;

        } catch (error) {
            console.error('Video stream error:', error);
            return {
                success: false,
                error: error.message,
                videoId: videoId
            };
        }
    }

    async batchGetVideos(videoIds, quality = '720p') {
        try {
            // 並列処理で複数動画を高速取得
            const promises = videoIds.map(id => this.getVideoStream(id, quality));
            const results = await Promise.all(promises);
            
            return {
                success: true,
                videos: results.filter(r => r.success),
                errors: results.filter(r => !r.success)
            };

        } catch (error) {
            console.error('Batch video error:', error);
            return {
                success: false,
                error: error.message
            };
        }
    }

    async searchVideos(query, maxResults = 20) {
        try {
            const searchResults = await YouTubeSearchAPI.GetListByKeyword(
                query, 
                false, 
                maxResults,
                [{ type: 'video' }]
            );

            const videos = searchResults.items.map(item => ({
                id: item.id,
                title: item.title,
                author: item.channelTitle,
                duration: this.parseDuration(item.length?.simpleText),
                thumbnail: item.thumbnail?.thumbnails?.[0]?.url,
                views: item.viewCount?.simpleText,
                publishedTime: item.publishedTime
            }));

            return {
                success: true,
                videos: videos
            };

        } catch (error) {
            console.error('Search error:', error);
            return {
                success: false,
                error: error.message
            };
        }
    }

    parseDuration(durationText) {
        if (!durationText) return 0;
        
        const parts = durationText.split(':').reverse();
        let seconds = 0;
        
        for (let i = 0; i < parts.length; i++) {
            seconds += parseInt(parts[i]) * Math.pow(60, i);
        }
        
        return seconds;
    }

    clearCache() {
        this.cache.clear();
    }

    getCacheStats() {
        return {
            size: this.cache.size,
            maxSize: this.maxCacheSize
        };
    }
}

// CLI インターフェース
if (require.main === module) {
    const service = new TurboVideoService();
    const [,, command, ...args] = process.argv;

    switch (command) {
        case 'stream':
            service.getVideoStream(args[0], args[1])
                .then(result => console.log(JSON.stringify(result)))
                .catch(error => {
                    console.error(JSON.stringify({ success: false, error: error.message }));
                    process.exit(1);
                });
            break;

        case 'batch':
            const videoIds = args[0].split(',');
            service.batchGetVideos(videoIds, args[1])
                .then(result => console.log(JSON.stringify(result)))
                .catch(error => {
                    console.error(JSON.stringify({ success: false, error: error.message }));
                    process.exit(1);
                });
            break;

        case 'search':
            service.searchVideos(args[0], parseInt(args[1]) || 20)
                .then(result => console.log(JSON.stringify(result)))
                .catch(error => {
                    console.error(JSON.stringify({ success: false, error: error.message }));
                    process.exit(1);
                });
            break;

        default:
            console.error('Usage: node turbo_video_service.js [stream|batch|search] [args...]');
            process.exit(1);
    }
}

module.exports = TurboVideoService;