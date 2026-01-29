<template>
  <section class="videos-section" v-if="videos.length > 0">
    <div class="videos-header">
      <h3 class="videos-title">
        <span class="tiktok-icon">📱</span>
        Related TikTok Videos
      </h3>
      <span class="videos-badge">{{ videos.length }} videos</span>
    </div>
    
    <div class="videos-grid">
      <a 
        v-for="video in videos" 
        :key="video.id"
        :href="video.video_url"
        target="_blank"
        class="video-card"
      >
        <div class="video-thumbnail">
          <img :src="video.thumbnail_url" :alt="video.title" loading="lazy" />
          <div class="video-overlay">
            <span class="play-btn">▶</span>
          </div>
          <span class="video-duration">{{ formatDuration(video.duration) }}</span>
        </div>
        
        <div class="video-content">
          <div class="video-author">
            <img :src="video.author_avatar" :alt="video.author" class="author-avatar" />
            <span class="author-name">@{{ video.author }}</span>
          </div>
          <p class="video-title">{{ video.title }}</p>
          <div class="video-stats">
            <span class="stat">👁 {{ formatCount(video.views) }}</span>
            <span class="stat">❤️ {{ formatCount(video.likes) }}</span>
          </div>
        </div>
      </a>
    </div>
  </section>
</template>

<script setup>
const props = defineProps({
  videos: {
    type: Array,
    default: () => []
  }
})

const formatDuration = (seconds) => {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

const formatCount = (count) => {
  if (count >= 1000000) {
    return (count / 1000000).toFixed(1) + 'M'
  }
  if (count >= 1000) {
    return (count / 1000).toFixed(1) + 'K'
  }
  return count.toString()
}
</script>

<style scoped>
.videos-section {
  margin-top: 40px;
  padding: 0 8px;
}

.videos-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.videos-title {
  font-size: 20px;
  font-weight: 600;
  color: #111;
  display: flex;
  align-items: center;
  gap: 10px;
}

.tiktok-icon {
  font-size: 24px;
}

.videos-badge {
  font-size: 13px;
  color: #888;
  background: #f5f5f5;
  padding: 6px 14px;
  border-radius: 12px;
}

.videos-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
}

.video-card {
  background: #fff;
  border-radius: 16px;
  overflow: hidden;
  text-decoration: none;
  transition: all 0.3s ease;
  border: 1px solid #f0f0f0;
}

.video-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.1);
}

.video-thumbnail {
  position: relative;
  aspect-ratio: 9/16;
  background: #111;
  overflow: hidden;
}

.video-thumbnail img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s ease;
}

.video-card:hover .video-thumbnail img {
  transform: scale(1.05);
}

.video-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.2s ease;
}

.video-card:hover .video-overlay {
  opacity: 1;
}

.play-btn {
  width: 48px;
  height: 48px;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  color: #111;
}

.video-duration {
  position: absolute;
  bottom: 8px;
  right: 8px;
  background: rgba(0, 0, 0, 0.75);
  color: #fff;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
}

.video-content {
  padding: 14px;
}

.video-author {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.author-avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  object-fit: cover;
}

.author-name {
  font-size: 13px;
  color: #666;
  font-weight: 500;
}

.video-title {
  font-size: 14px;
  color: #111;
  line-height: 1.4;
  margin-bottom: 10px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.video-stats {
  display: flex;
  gap: 12px;
}

.stat {
  font-size: 12px;
  color: #888;
}

@media (max-width: 600px) {
  .videos-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
