<template>
  <nav class="navbar">
    <div class="nav-container">
      <div class="nav-logo">
        <span class="logo-icon">⚡</span>
        <span class="logo-text">FetchBot</span>
      </div>
      
      <div class="nav-actions">
        <button class="nav-btn-outline">Sign In</button>
        <button class="nav-btn">Get Started</button>
      </div>
    </div>
  </nav>
</template>

<script setup>
</script>

<style scoped>
.navbar {
  position: sticky;
  top: 0;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid #f0f0f0;
  z-index: 100;
  padding: 14px 0;
}

.nav-container {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.nav-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 700;
  font-size: 22px;
}

.logo-icon {
  font-size: 24px;
}

.logo-text {
  background: linear-gradient(135deg, #111 0%, #444 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.nav-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.nav-btn-outline {
  padding: 10px 20px;
  border: 1px solid #ddd;
  background: transparent;
  color: #333;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.nav-btn-outline:hover {
  border-color: #111;
  color: #111;
}

.nav-btn {
  padding: 10px 20px;
  border: none;
  background: #111;
  color: #fff;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.nav-btn:hover {
  background: #333;
  transform: translateY(-1px);
}

@media (max-width: 480px) {
  .nav-btn-outline {
    display: none;
  }
}
</style>
