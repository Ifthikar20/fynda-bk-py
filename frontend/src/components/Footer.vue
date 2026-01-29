<template>
  <footer class="footer">
    <div class="footer-inner">
      <div class="footer-main">
        <div class="footer-brand">
          <div class="footer-logo">
            <span class="logo-icon">⚡</span>
            <span class="logo-text">FetchBot</span>
          </div>
          <p class="footer-tagline">AI-powered deal discovery across all major marketplaces and social media.</p>
        </div>
        
        <div class="footer-links">
          <div class="link-group">
            <h4 class="link-title">Product</h4>
            <a href="#" class="link">How it Works</a>
            <a href="#" class="link">Pricing</a>
            <a href="#" class="link">API Access</a>
          </div>
          
          <div class="link-group">
            <h4 class="link-title">Marketplaces</h4>
            <a href="#" class="link">Amazon</a>
            <a href="#" class="link">eBay</a>
            <a href="#" class="link">Best Buy</a>
            <a href="#" class="link">TikTok Shop</a>
          </div>
          
          <div class="link-group">
            <h4 class="link-title">Company</h4>
            <a href="#" class="link">About</a>
            <a href="#" class="link">Blog</a>
            <a href="#" class="link">Contact</a>
          </div>
          
          <div class="link-group">
            <h4 class="link-title">Legal</h4>
            <a href="#" class="link">Privacy</a>
            <a href="#" class="link">Terms</a>
            <a href="#" class="link">Cookies</a>
          </div>
        </div>
      </div>
      
      <div class="footer-bottom">
        <p class="copyright">© 2026 FetchBot. All rights reserved.</p>
        <div class="social-links">
          <a href="#" class="social-link">Twitter</a>
          <a href="#" class="social-link">GitHub</a>
          <a href="#" class="social-link">Discord</a>
          <a href="#" class="social-link">TikTok</a>
        </div>
      </div>
    </div>
  </footer>
</template>

<script setup>
</script>

<style scoped>
.footer {
  background: #fafafa;
  border-top: 1px solid #eee;
  margin-top: 48px;
  width: 100vw;
  margin-left: calc(-50vw + 50%);
}

.footer-inner {
  max-width: 1400px;
  margin: 0 auto;
  padding: 56px 48px 32px;
}

.footer-main {
  display: flex;
  justify-content: space-between;
  gap: 64px;
  padding-bottom: 40px;
  border-bottom: 1px solid #e8e8e8;
}

.footer-brand {
  max-width: 300px;
}

.footer-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 700;
  font-size: 22px;
  margin-bottom: 14px;
}

.logo-icon {
  font-size: 24px;
}

.logo-text {
  color: #111;
}

.footer-tagline {
  font-size: 14px;
  color: #777;
  line-height: 1.7;
}

.footer-links {
  display: flex;
  gap: 72px;
}

.link-group {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.link-title {
  font-size: 13px;
  font-weight: 600;
  color: #333;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
}

.link {
  font-size: 14px;
  color: #777;
  text-decoration: none;
  transition: color 0.2s ease;
}

.link:hover {
  color: #111;
}

.footer-bottom {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 28px;
}

.copyright {
  font-size: 13px;
  color: #999;
}

.social-links {
  display: flex;
  gap: 28px;
}

.social-link {
  font-size: 13px;
  color: #777;
  text-decoration: none;
  transition: color 0.2s ease;
}

.social-link:hover {
  color: #111;
}

@media (max-width: 1000px) {
  .footer-main {
    flex-direction: column;
    gap: 40px;
  }
  
  .footer-links {
    flex-wrap: wrap;
    gap: 40px;
  }
  
  .link-group {
    min-width: 140px;
  }
}

@media (max-width: 600px) {
  .footer-inner {
    padding: 40px 24px 24px;
  }
  
  .footer-bottom {
    flex-direction: column;
    gap: 16px;
    text-align: center;
  }
  
  .social-links {
    gap: 20px;
  }
}
</style>
