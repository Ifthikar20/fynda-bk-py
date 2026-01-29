<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="isOpen" class="video-modal" @click.self="close">
        <!-- Close button -->
        <button class="close-btn" @click="close">✕</button>
        
        <!-- Navigation buttons -->
        <button v-if="currentIndex > 0" class="nav-btn prev" @click="prevVideo">‹</button>
        <button v-if="currentIndex < videos.length - 1" class="nav-btn next" @click="nextVideo">›</button>
        
        <!-- Contained video card -->
        <div class="video-card" @touchstart="handleTouchStart" @touchend="handleTouchEnd">
          <!-- Author info at TOP -->
          <div class="video-header">
            <img :src="currentVideo?.author_avatar" class="avatar" />
            <div class="author-info">
              <span class="author-name">@{{ currentVideo?.author }}</span>
              <span class="video-type">{{ currentVideo?.video_type?.toUpperCase() || 'REVIEW' }}</span>
            </div>
            <div class="header-actions">
              <button class="action-btn" @click="shareVideo">Share</button>
            </div>
          </div>
          
          <!-- Video frame -->
          <div class="video-frame">
            <iframe
              v-if="embedUrl"
              :key="currentVideo?.id"
              :src="embedUrl"
              class="tiktok-iframe"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowfullscreen
            ></iframe>
            
            <!-- Fallback -->
            <div v-else class="video-fallback">
              <img :src="currentVideo?.thumbnail_url" class="video-thumbnail" />
              <a :href="currentVideo?.video_url" target="_blank" class="play-overlay">
                <div class="play-button">▶</div>
                <span class="play-text">Watch on TikTok</span>
              </a>
            </div>
          </div>
          
          <!-- Video info & stats below video -->
          <div class="video-footer">
            <p class="video-title">{{ currentVideo?.title }}</p>
            <div class="video-stats">
              <span>👁 {{ formatCount(currentVideo?.views) }}</span>
              <span>❤️ {{ formatCount(currentVideo?.likes) }}</span>
              <span>💬 {{ formatCount(currentVideo?.comments) }}</span>
            </div>
            
            <!-- Related product -->
            <div v-if="relatedProduct" class="related-product">
              <img :src="relatedProduct.image_url" class="product-img" />
              <div class="product-info">
                <span class="product-name">{{ relatedProduct.title }}</span>
                <span class="product-price">${{ relatedProduct.price?.toFixed(2) }}</span>
              </div>
              <a :href="relatedProduct.url" target="_blank" class="shop-btn">Shop</a>
            </div>
            
            <a :href="currentVideo?.video_url" target="_blank" class="tiktok-btn">
              Open in TikTok →
            </a>
          </div>
        </div>
        
        <!-- Counter -->
        <div class="counter">{{ currentIndex + 1 }} / {{ videos.length }}</div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  isOpen: Boolean,
  videos: { type: Array, default: () => [] },
  startIndex: { type: Number, default: 0 },
  relatedProduct: { type: Object, default: null },
})

const emit = defineEmits(['close', 'change'])

const currentIndex = ref(0)
let touchStartY = 0

const currentVideo = computed(() => props.videos[currentIndex.value])

const embedUrl = computed(() => {
  const video = currentVideo.value
  if (!video?.video_url) return null
  const match = video.video_url.match(/video\/(\d+)/)
  if (match) return `https://www.tiktok.com/embed/v2/${match[1]}?autoplay=1`
  return null
})

watch(() => props.isOpen, (open) => {
  if (open) {
    currentIndex.value = props.startIndex
    document.body.style.overflow = 'hidden'
  } else {
    document.body.style.overflow = ''
  }
})

const handleKeydown = (e) => {
  if (!props.isOpen) return
  if (e.key === 'Escape') close()
  if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') prevVideo()
  if (e.key === 'ArrowRight' || e.key === 'ArrowDown') nextVideo()
}

onMounted(() => window.addEventListener('keydown', handleKeydown))
onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
  document.body.style.overflow = ''
})

const handleTouchStart = (e) => { touchStartY = e.touches[0].clientY }
const handleTouchEnd = (e) => {
  const diff = touchStartY - e.changedTouches[0].clientY
  if (Math.abs(diff) > 50) diff > 0 ? nextVideo() : prevVideo()
}

const close = () => emit('close')
const prevVideo = () => { if (currentIndex.value > 0) currentIndex.value-- }
const nextVideo = () => { if (currentIndex.value < props.videos.length - 1) currentIndex.value++ }

const formatCount = (count) => {
  if (!count) return '0'
  if (count >= 1000000) return (count / 1000000).toFixed(1) + 'M'
  if (count >= 1000) return (count / 1000).toFixed(1) + 'K'
  return count.toString()
}

const shareVideo = () => {
  if (navigator.share) {
    navigator.share({ title: currentVideo.value?.title, url: currentVideo.value?.video_url })
  } else {
    navigator.clipboard.writeText(currentVideo.value?.video_url)
  }
}
</script>

<style scoped>
.video-modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.85);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.close-btn {
  position: absolute;
  top: 20px;
  right: 20px;
  width: 44px;
  height: 44px;
  background: rgba(255, 255, 255, 0.1);
  border: none;
  border-radius: 50%;
  color: #fff;
  font-size: 18px;
  cursor: pointer;
  z-index: 10;
}

.close-btn:hover {
  background: rgba(255, 255, 255, 0.2);
}

.nav-btn {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 48px;
  height: 48px;
  background: rgba(255, 255, 255, 0.1);
  border: none;
  border-radius: 50%;
  color: #fff;
  font-size: 24px;
  cursor: pointer;
  z-index: 10;
}

.nav-btn:hover {
  background: rgba(255, 255, 255, 0.2);
}

.nav-btn.prev { left: 20px; }
.nav-btn.next { right: 20px; }

/* Contained video card */
.video-card {
  background: #fff;
  border-radius: 20px;
  overflow: hidden;
  width: 100%;
  max-width: 400px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
}

/* Header with author */
.video-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-bottom: 1px solid #f0f0f0;
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: 2px solid #fe2c55;
}

.author-info {
  flex: 1;
}

.author-name {
  display: block;
  font-weight: 600;
  font-size: 14px;
  color: #111;
}

.video-type {
  font-size: 11px;
  color: #fe2c55;
  font-weight: 600;
  letter-spacing: 0.5px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.action-btn {
  padding: 8px 16px;
  background: #f5f5f5;
  border: none;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
}

.action-btn:hover {
  background: #eee;
}

/* Video frame */
.video-frame {
  position: relative;
  width: 100%;
  aspect-ratio: 9/16;
  max-height: 500px;
  background: #000;
}

.tiktok-iframe {
  width: 100%;
  height: 100%;
  border: none;
}

.video-fallback {
  width: 100%;
  height: 100%;
  position: relative;
}

.video-thumbnail {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.play-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  text-decoration: none;
}

.play-button {
  width: 64px;
  height: 64px;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  color: #fe2c55;
}

.play-text {
  color: #fff;
  font-size: 14px;
  font-weight: 600;
}

/* Footer with info */
.video-footer {
  padding: 16px;
  background: #fff;
}

.video-title {
  font-size: 14px;
  line-height: 1.4;
  color: #111;
  margin-bottom: 12px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.video-stats {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: #666;
  margin-bottom: 16px;
}

/* Related product */
.related-product {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: #fafafa;
  border-radius: 12px;
  margin-bottom: 12px;
}

.product-img {
  width: 50px;
  height: 50px;
  border-radius: 8px;
  object-fit: cover;
}

.product-info {
  flex: 1;
  min-width: 0;
}

.product-name {
  display: block;
  font-size: 13px;
  color: #111;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.product-price {
  font-size: 15px;
  font-weight: 700;
  color: #fe2c55;
}

.shop-btn {
  padding: 8px 16px;
  background: #fe2c55;
  color: #fff;
  text-decoration: none;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 600;
}

.tiktok-btn {
  display: block;
  text-align: center;
  padding: 12px;
  background: #111;
  color: #fff;
  text-decoration: none;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 600;
}

.tiktok-btn:hover {
  background: #333;
}

/* Counter */
.counter {
  position: absolute;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(255, 255, 255, 0.1);
  padding: 8px 20px;
  border-radius: 20px;
  color: rgba(255, 255, 255, 0.8);
  font-size: 14px;
}

/* Animation */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

/* Mobile */
@media (max-width: 500px) {
  .video-modal {
    padding: 20px;
  }
  
  .video-card {
    max-height: 85vh;
  }
  
  .nav-btn {
    display: none;
  }
}
</style>
