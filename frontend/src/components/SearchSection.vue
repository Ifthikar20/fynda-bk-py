<template>
  <section class="prompt-section">
    <div class="prompt-module">
      <div class="prompt-input-area">
        <textarea
          v-model="query"
          class="prompt-input"
          placeholder="Ask FetchBot to find the best deals for you..."
          rows="4"
          @keydown.enter.prevent="handleSearch"
          :disabled="loading"
        ></textarea>
      </div>
      
      <div class="prompt-toolbar">
        <div class="toolbar-left">
          <button class="toolbar-btn">
            <span class="btn-icon">+</span>
          </button>
          <button class="toolbar-btn">
            <span class="icon">📎</span>
            <span class="btn-text">Attach</span>
          </button>
          <button class="toolbar-btn dropdown">
            <span class="icon">🎨</span>
            <span class="btn-text">Theme</span>
            <span class="chevron">▾</span>
          </button>
        </div>
        
        <div class="toolbar-right">
          <button class="toolbar-btn">
            <span class="btn-text">Plan</span>
          </button>
          <button class="toolbar-btn">
            <span class="icon">📊</span>
          </button>
          <button 
            class="submit-btn" 
            @click="handleSearch"
            :disabled="loading || !query.trim()"
          >
            <span v-if="loading" class="spinner"></span>
            <span v-else class="arrow">↑</span>
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref } from 'vue'

const emit = defineEmits(['search'])
const props = defineProps({
  loading: Boolean
})

const query = ref('')

const handleSearch = () => {
  if (query.value.trim()) {
    emit('search', query.value.trim())
  }
}
</script>

<style scoped>
.prompt-section {
  padding: 56px 16px 48px;
  display: flex;
  justify-content: center;
}

.prompt-module {
  width: 100%;
  max-width: 900px;
  background: #f8f8f8;
  border: 1px solid #e5e5e5;
  border-radius: 24px;
  padding: 24px 28px 20px;
  box-shadow: 
    0 4px 24px rgba(0, 0, 0, 0.03),
    0 1px 3px rgba(0, 0, 0, 0.02);
}

.prompt-input-area {
  margin-bottom: 16px;
}

.prompt-input {
  width: 100%;
  border: none;
  outline: none;
  font-size: 18px;
  line-height: 1.6;
  color: #111;
  resize: none;
  font-family: inherit;
  background: transparent;
}

.prompt-input::placeholder {
  color: #999;
}

.prompt-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 12px;
  border-top: 1px solid #e8e8e8;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 6px;
}

.toolbar-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 14px;
  background: transparent;
  border: none;
  border-radius: 12px;
  color: #666;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.toolbar-btn:hover {
  background: rgba(0, 0, 0, 0.04);
  color: #333;
}

.toolbar-btn .btn-icon {
  font-size: 18px;
  font-weight: 300;
}

.toolbar-btn .icon {
  font-size: 15px;
}

.toolbar-btn .chevron {
  font-size: 10px;
  margin-left: 2px;
}

.submit-btn {
  width: 42px;
  height: 42px;
  background: #111;
  border: none;
  border-radius: 50%;
  color: #fff;
  font-size: 20px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.submit-btn:hover:not(:disabled) {
  background: #333;
  transform: scale(1.05);
}

.submit-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid transparent;
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 600px) {
  .btn-text {
    display: none;
  }
  
  .toolbar-btn {
    padding: 10px;
  }
  
  .prompt-module {
    padding: 20px;
  }
}
</style>
