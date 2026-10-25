<script setup>
import { ref } from 'vue'
import { fetchHello } from '../api/getRt'

const message = ref('')
const error = ref('')

async function callHello() {
  error.value = ''
  try {
    const data = await fetchHello()
    message.value = data.message
  } catch (e) {
    message.value = ''
    error.value = e.message
  }
}
</script>

<template>
  <section>
    <h2>1. Hello API</h2>
    <button @click="callHello">/hello 호출</button>
    <p v-if="message" class="ok">{{ message }}</p>
    <p v-if="error" class="err">{{ error }}</p>
  </section>
</template>