<template>
  <article class="deal-card" @click="$emit('click')">
    <div class="card-image">
      <img :src="deal.image_url" :alt="deal.title" loading="lazy" />
      <div class="card-overlay">
        <button class="action-btn" @click.stop="handleFavorite">
          <span>❤️</span>
        </button>
        <button class="action-btn" @click.stop="handleShare">
          <span>↗️</span>
        </button>
      </div>
      <span class="source-badge">{{ deal.source }}</span>
      <span v-if="deal.discount_percent >= 15" class="discount-badge">
        -{{ deal.discount_percent }}%
      </span>
    </div>
    
    <div class="card-content">
      <h3 class="card-title">{{ deal.title }}</h3>
      
      <div class="card-pricing">
        <span class="current-price">${{ deal.price.toFixed(2) }}</span>
        <span v-if="deal.original_price > deal.price" class="original-price">
          ${{ deal.original_price.toFixed(2) }}
        </span>
      </div>
      
      <div class="card-meta">
        <span class="card-rating" v-if="deal.rating">
          ⭐ {{ deal.rating }}
        </span>
        <span class="card-reviews" v-if="deal.reviews_count">
          ({{ formatReviews(deal.reviews_count) }})
        </span>
      </div>
      
      <div class="card-shipping" v-if="deal.shipping">
        <span class="shipping-icon">📦</span>
        {{ deal.shipping }}
      </div>
      
      <div class="card-tags" v-if="deal.features?.length">
        <span 
          v-for="tag in deal.features.slice(0, 4)" 
          :key="tag" 
          class="tag"
        >
          {{ tag }}
        </span>
      </div>
    </div>
  </article>
</template>

<script setup>
import { eventBus, Events } from '../events/eventBus'

const props = defineProps({
  deal: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['click'])

const formatReviews = (count) => {
  if (count >= 1000) {
    return (count / 1000).toFixed(1) + 'k'
  }
  return count
}

const handleFavorite = () => {
  eventBus.emit(Events.DEAL_FAVORITE, props.deal)
}

const handleShare = () => {
  eventBus.emit(Events.DEAL_SHARE, props.deal)
  navigator.clipboard?.writeText(props.deal.url)
}
</script>

<style scoped>
.deal-card {
  background: #fff;
  border-radius: 24px;
  overflow: hidden;
  margin-bottom: 20px;
  break-inside: avoid;
  cursor: pointer;
  transition: all 0.3s ease;
  border: 1px solid #f0f0f0;
}

.deal-card:hover {
  transform: translateY(-6px);
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.1);
}

.card-image {
  position: relative;
  overflow: hidden;
  background: #f9f9f9;
}

.card-image img {
  width: 100%;
  height: auto;
  min-height: 200px;
  object-fit: cover;
  display: block;
  transition: transform 0.4s ease;
}

.deal-card:hover .card-image img {
  transform: scale(1.06);
}

.card-overlay {
  position: absolute;
  top: 14px;
  right: 14px;
  display: flex;
  gap: 10px;
  opacity: 0;
  transition: opacity 0.25s ease;
}

.deal-card:hover .card-overlay {
  opacity: 1;
}

.action-btn {
  width: 42px;
  height: 42px;
  background: rgba(255, 255, 255, 0.95);
  border: none;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
  font-size: 18px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.action-btn:hover {
  transform: scale(1.1);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.15);
}

.source-badge {
  position: absolute;
  bottom: 14px;
  left: 14px;
  background: rgba(0, 0, 0, 0.8);
  color: #fff;
  padding: 8px 14px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 500;
}

.discount-badge {
  position: absolute;
  top: 14px;
  left: 14px;
  background: #ef4444;
  color: #fff;
  padding: 8px 12px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 700;
}

.card-content {
  padding: 20px;
}

.card-title {
  font-size: 17px;
  font-weight: 600;
  color: #111;
  line-height: 1.45;
  margin-bottom: 12px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-pricing {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.current-price {
  font-size: 24px;
  font-weight: 700;
  color: #111;
}

.original-price {
  font-size: 16px;
  color: #999;
  text-decoration: line-through;
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #666;
  margin-bottom: 10px;
}

.card-rating {
  display: flex;
  align-items: center;
  gap: 4px;
}

.card-shipping {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #22a861;
  margin-bottom: 14px;
}

.shipping-icon {
  font-size: 14px;
}

.card-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.tag {
  padding: 6px 12px;
  background: #f5f5f5;
  border-radius: 8px;
  font-size: 12px;
  color: #555;
  text-transform: capitalize;
}
</style>
