<template>
  <button 
    :class="['btn', variant, size, { 'icon-only': iconOnly }]"
    :disabled="disabled"
    @click="$emit('click', $event)"
  >
    <span v-if="icon && iconPosition === 'left'" class="btn-icon">{{ icon }}</span>
    <span v-if="!iconOnly" class="btn-text"><slot /></span>
    <span v-if="icon && iconPosition === 'right'" class="btn-icon">{{ icon }}</span>
  </button>
</template>

<script setup>
defineProps({
  variant: {
    type: String,
    default: 'primary',
    validator: (v) => ['primary', 'secondary', 'ghost', 'danger', 'tiktok'].includes(v)
  },
  size: {
    type: String,
    default: 'md',
    validator: (v) => ['sm', 'md', 'lg'].includes(v)
  },
  icon: { type: String, default: '' },
  iconPosition: { type: String, default: 'left' },
  iconOnly: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
})

defineEmits(['click'])
</script>

<style scoped>
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: none;
  border-radius: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
  text-decoration: none;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Sizes */
.btn.sm {
  padding: 8px 16px;
  font-size: 13px;
  border-radius: 8px;
}

.btn.md {
  padding: 12px 24px;
  font-size: 14px;
}

.btn.lg {
  padding: 16px 32px;
  font-size: 16px;
}

/* Icon only variants */
.btn.icon-only.sm {
  width: 32px;
  height: 32px;
  padding: 0;
  border-radius: 50%;
}

.btn.icon-only.md {
  width: 44px;
  height: 44px;
  padding: 0;
  border-radius: 50%;
}

.btn.icon-only.lg {
  width: 56px;
  height: 56px;
  padding: 0;
  border-radius: 50%;
}

/* Variants */
.btn.primary {
  background: #111;
  color: #fff;
}

.btn.primary:hover:not(:disabled) {
  background: #333;
}

.btn.secondary {
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
}

.btn.secondary:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.2);
}

.btn.ghost {
  background: transparent;
  color: #fff;
}

.btn.ghost:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.1);
}

.btn.tiktok {
  background: #fe2c55;
  color: #fff;
}

.btn.tiktok:hover:not(:disabled) {
  background: #ff4466;
  transform: scale(1.02);
}

.btn.danger {
  background: #ff4757;
  color: #fff;
}

.btn.danger:hover:not(:disabled) {
  background: #ff6b7a;
}

.btn-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.1em;
}
</style>
