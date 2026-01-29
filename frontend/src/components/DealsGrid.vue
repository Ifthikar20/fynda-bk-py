<template>
  <section class="content-section">
    <!-- Trend Score Bar (compact) -->
    <div v-if="pinterestTrend && !loading" class="trend-bar">
      <span class="trend-score" :class="trendClass">
        📌 {{ pinterestTrend.trending_score }}/100
      </span>
      <span class="trend-level">{{ pinterestTrend.engagement_level?.toUpperCase() }}</span>
      <span class="trend-pins">{{ formatLargeNumber(pinterestTrend.pin_count) }} pins</span>
      <div class="trend-tags">
        <span v-for="term in pinterestTrend.related_terms?.slice(0, 2)" :key="term">{{ term }}</span>
      </div>
    </div>
    
    <!-- Loading skeleton -->
    <div v-if="loading" class="masonry-grid">
      <div v-for="n in 12" :key="n" class="grid-item skeleton">
        <div class="skeleton-image" :style="{ height: getRandomHeight() + 'px' }"></div>
      </div>
    </div>
    
    <!-- Unified Masonry Grid -->
    <div v-else-if="allContent.length > 0" class="masonry-grid">
      <div 
        v-for="(item, index) in allContent" 
        :key="item.id + '-' + item.type"
        class="grid-item"
        @click="handleItemClick(item, index)"
      >
        <!-- Image -->
        <img :src="getItemImage(item)" :alt="getItemTitle(item)" loading="lazy" />
        
        <!-- Video play indicator -->
        <div v-if="item.type === 'video'" class="play-indicator">▶</div>
        
        <!-- Source badge -->
        <span class="source-badge" :class="getSourceClass(item)">
          {{ getSourceLabel(item) }}
        </span>
        
        <!-- Overlay info at bottom -->
        <div class="item-overlay">
          <p class="item-title">{{ getItemTitle(item) }}</p>
          
          <!-- Price for deals -->
          <div v-if="item.type === 'deal' && item.price" class="price-row">
            <span class="price">${{ item.price?.toFixed(2) }}</span>
            <span v-if="item.original_price > item.price" class="original-price">
              ${{ item.original_price?.toFixed(2) }}
            </span>
          </div>
          
          <!-- Pinterest with source link -->
          <div v-else-if="item.type === 'pinterest'" class="stats-row">
            <span v-if="item.saves">📌 {{ formatCount(item.saves) }}</span>
            <a 
              v-if="item.source_domain" 
              :href="item.source_url" 
              target="_blank" 
              class="source-link"
              @click.stop
            >
              🔗 {{ item.source_domain }}
            </a>
          </div>
          
          <!-- Stats for other social content -->
          <div v-else class="stats-row">
            <span v-if="item.likes">❤️ {{ formatCount(item.likes) }}</span>
            <span v-if="item.saves">📌 {{ formatCount(item.saves) }}</span>
            <span v-if="item.views">👁 {{ formatCount(item.views) }}</span>
          </div>
        </div>
        
        <!-- Discount badge -->
        <span v-if="item.type === 'deal' && item.discount_percent > 0" class="discount-badge">
          -{{ item.discount_percent }}%
        </span>
      </div>
    </div>
    
    <!-- Empty state -->
    <div v-else class="empty-state">
      <p>Search for products to discover deals</p>
    </div>
    
    <!-- Video Player Modal -->
    <VideoPlayerModal 
      :isOpen="videoModalOpen"
      :videos="videoItems"
      :startIndex="selectedVideoIndex"
      :relatedProduct="deals[0]"
      @close="videoModalOpen = false"
    />
  </section>
</template>

<script setup>
import { ref, computed } from 'vue'
import VideoPlayerModal from './VideoPlayerModal.vue'

const props = defineProps({
  deals: { type: Array, default: () => [] },
  videos: { type: Array, default: () => [] },
  photos: { type: Array, default: () => [] },
  pinterestPins: { type: Array, default: () => [] },
  pinterestTrend: { type: Object, default: null },
  loading: Boolean
})

const videoModalOpen = ref(false)
const selectedVideoIndex = ref(0)

// All video items for modal
const videoItems = computed(() => props.videos)

// Trend class for styling
const trendClass = computed(() => {
  if (!props.pinterestTrend) return 'low'
  return props.pinterestTrend.engagement_level || 'low'
})

// Merge ALL content into single unified array
const allContent = computed(() => {
  const items = []
  
  // Add deals
  props.deals.forEach(d => items.push({ ...d, type: 'deal' }))
  
  // Add TikTok videos
  props.videos.forEach(v => items.push({ ...v, type: 'video' }))
  
  // Add Instagram photos
  props.photos.forEach(p => items.push({ ...p, type: 'instagram' }))
  
  // Add Pinterest pins
  props.pinterestPins.forEach(p => items.push({ ...p, type: 'pinterest' }))
  
  // Shuffle to create mixed feed
  return shuffleArray(items)
})

// Shuffle array for mixed content
const shuffleArray = (array) => {
  const arr = [...array]
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]]
  }
  return arr
}

// Get image based on content type
const getItemImage = (item) => {
  switch (item.type) {
    case 'deal': return item.image_url
    case 'video': return item.thumbnail_url
    case 'instagram': return item.image_url
    case 'pinterest': return item.image_url
    default: return item.image_url || item.thumbnail_url
  }
}

// Get title based on content type
const getItemTitle = (item) => {
  return item.title || item.caption || ''
}

// Get source class for badge styling
const getSourceClass = (item) => {
  if (item.type === 'video') return 'tiktok'
  if (item.type === 'instagram') return 'instagram'
  if (item.type === 'pinterest') return 'pinterest'
  if (item.source?.toLowerCase().includes('shopify')) return 'shopify'
  if (item.source?.toLowerCase().includes('ebay')) return 'ebay'
  if (item.source?.toLowerCase().includes('best buy')) return 'bestbuy'
  if (item.source?.toLowerCase().includes('facebook')) return 'facebook'
  return 'default'
}

// Get source label
const getSourceLabel = (item) => {
  if (item.type === 'video') return 'TikTok'
  if (item.type === 'instagram') return 'IG'
  if (item.type === 'pinterest') return 'Pin'
  if (item.source?.includes('Shopify')) {
    const match = item.source.match(/\((.+?)\)/)
    return match ? match[1] : 'Shop'
  }
  return item.source?.split(' ')[0] || 'Shop'
}

// Handle click on item
const handleItemClick = (item, index) => {
  if (item.type === 'video') {
    const videoIdx = props.videos.findIndex(v => v.id === item.id)
    selectedVideoIndex.value = videoIdx >= 0 ? videoIdx : 0
    videoModalOpen.value = true
  } else if (item.type === 'instagram') {
    window.open(item.post_url, '_blank')
  } else if (item.type === 'pinterest') {
    window.open(item.pin_url, '_blank')
  } else if (item.url) {
    window.open(item.url, '_blank')
  }
}

const getRandomHeight = () => 200 + Math.floor(Math.random() * 150)

const formatCount = (count) => {
  if (!count) return ''
  if (count >= 1000000) return (count / 1000000).toFixed(1) + 'M'
  if (count >= 1000) return (count / 1000).toFixed(1) + 'K'
  return count.toString()
}

const formatLargeNumber = (num) => {
  if (!num) return '0'
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(0) + 'K'
  return num.toString()
}
</script>

<style scoped>
.content-section {
  padding: 16px 0;
}

/* Compact Trend Bar */
.trend-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: #fafafa;
  border-radius: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.trend-score {
  font-weight: 700;
  font-size: 14px;
  padding: 4px 10px;
  border-radius: 8px;
}

.trend-score.viral { background: #ff4757; color: #fff; }
.trend-score.high { background: #e60023; color: #fff; }
.trend-score.medium { background: #ffa502; color: #fff; }
.trend-score.low { background: #ddd; color: #666; }

.trend-level {
  font-size: 12px;
  font-weight: 600;
  color: #666;
}

.trend-pins {
  font-size: 12px;
  color: #999;
}

.trend-tags {
  display: flex;
  gap: 6px;
  margin-left: auto;
}

.trend-tags span {
  font-size: 11px;
  padding: 4px 10px;
  background: rgba(0,0,0,0.05);
  border-radius: 12px;
  color: #666;
}

/* Pinterest-Style Masonry Grid */
.masonry-grid {
  column-count: 4;
  column-gap: 12px;
}

.grid-item {
  break-inside: avoid;
  margin-bottom: 12px;
  border-radius: 16px;
  overflow: hidden;
  position: relative;
  cursor: pointer;
  transition: transform 0.2s ease;
}

.grid-item:hover {
  transform: scale(1.02);
}

.grid-item img {
  width: 100%;
  display: block;
  min-height: 180px;
  object-fit: cover;
  background: #f0f0f0;
}

/* Play indicator for videos */
.play-indicator {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 48px;
  height: 48px;
  background: rgba(0,0,0,0.6);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 18px;
  opacity: 0;
  transition: opacity 0.2s;
}

.grid-item:hover .play-indicator {
  opacity: 1;
}

/* Source badge */
.source-badge {
  position: absolute;
  top: 10px;
  left: 10px;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.source-badge.tiktok { background: #000; color: #fff; }
.source-badge.instagram { background: linear-gradient(45deg, #f09433, #dc2743); color: #fff; }
.source-badge.pinterest { background: #e60023; color: #fff; }
.source-badge.shopify { background: #95bf47; color: #fff; }
.source-badge.ebay { background: #e53238; color: #fff; }
.source-badge.bestbuy { background: #003da6; color: #fff; }
.source-badge.facebook { background: #1877f2; color: #fff; }
.source-badge.default { background: rgba(0,0,0,0.6); color: #fff; }

/* Discount badge */
.discount-badge {
  position: absolute;
  top: 10px;
  right: 10px;
  background: #ff4757;
  color: #fff;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 700;
}

/* Bottom overlay */
.item-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 40px 12px 12px;
  background: linear-gradient(transparent, rgba(0,0,0,0.7));
  color: #fff;
}

.item-title {
  font-size: 13px;
  font-weight: 500;
  line-height: 1.3;
  margin-bottom: 6px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.price-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.price {
  font-size: 16px;
  font-weight: 700;
}

.original-price {
  font-size: 12px;
  text-decoration: line-through;
  opacity: 0.7;
}

.stats-row {
  display: flex;
  gap: 10px;
  font-size: 11px;
  opacity: 0.9;
}

.source-link {
  color: #fff;
  text-decoration: none;
  background: rgba(255,255,255,0.2);
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 10px;
  transition: background 0.2s;
}

.source-link:hover {
  background: rgba(255,255,255,0.35);
}

/* Skeleton */
.grid-item.skeleton {
  background: #f0f0f0;
}

.skeleton-image {
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* Empty state */
.empty-state {
  text-align: center;
  padding: 80px 20px;
  color: #999;
}

/* Responsive */
@media (max-width: 1200px) {
  .masonry-grid { column-count: 3; }
}

@media (max-width: 768px) {
  .masonry-grid { column-count: 2; column-gap: 8px; }
  .grid-item { margin-bottom: 8px; border-radius: 12px; }
}

@media (max-width: 480px) {
  .trend-bar { flex-direction: column; align-items: flex-start; }
  .trend-tags { margin-left: 0; margin-top: 8px; }
}
</style>
