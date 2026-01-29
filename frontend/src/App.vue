<template>
  <div id="app">
    <NavBar />
    <main class="main-content">
      <SearchSection @search="handleSearch" :loading="loading" />
      <DealsGrid 
        :deals="deals" 
        :videos="videos" 
        :photos="samplePhotos" 
        :pinterestPins="pinterestPins"
        :pinterestTrend="pinterestTrend"
        :loading="loading" 
      />
    </main>
    <Footer />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import NavBar from './components/NavBar.vue'
import SearchSection from './components/SearchSection.vue'
import DealsGrid from './components/DealsGrid.vue'
import Footer from './components/Footer.vue'
import { eventBus } from './events/eventBus'

const deals = ref([])
const videos = ref([])
const samplePhotos = ref([])
const pinterestPins = ref([])
const pinterestTrend = ref(null)
const loading = ref(false)

// Event-driven search handler
const handleSearch = async (query) => {
  loading.value = true
  eventBus.emit('search:start', query)
  
  try {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
    const response = await fetch(`${apiUrl}/api/search/?q=${encodeURIComponent(query)}`)
    const data = await response.json()
    
    deals.value = data.deals || []
    videos.value = data.videos || []
    samplePhotos.value = data.sample_photos || []
    pinterestPins.value = data.pinterest_pins || []
    pinterestTrend.value = data.pinterest_trend || null
    eventBus.emit('search:complete', { query, deals: deals.value, videos: videos.value })
  } catch (error) {
    console.error('Search failed:', error)
    eventBus.emit('search:error', error)
    deals.value = []
    videos.value = []
    samplePhotos.value = []
    pinterestPins.value = []
    pinterestTrend.value = null
  } finally {
    loading.value = false
  }
}

// Listen for global events
eventBus.on('deal:favorite', (deal) => {
  console.log('Deal favorited:', deal.title)
})
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
  background-color: #ffffff;
  color: #111111;
  min-height: 100vh;
}

#app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.main-content {
  flex: 1;
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 16px;
  width: 100%;
}
</style>
