import { ref, onMounted, onBeforeUnmount } from 'vue'

// fn 을 주기적으로 호출. 탭이 숨겨지면 쉬었다가 돌아오면 즉시 갱신
export function usePolling(fn, intervalMs = 3000, { immediate = true } = {}) {
  const enabled = ref(true)
  let timer = null
  let busy = false

  async function tick() {
    if (busy || document.hidden || !enabled.value) return
    busy = true
    try { await fn() } finally { busy = false }
  }
  function start() { stop(); timer = setInterval(tick, intervalMs) }
  function stop() { if (timer) clearInterval(timer); timer = null }
  const onVisible = () => { if (!document.hidden) tick() }

  onMounted(() => {
    if (immediate) tick()
    start()
    document.addEventListener('visibilitychange', onVisible)
  })
  onBeforeUnmount(() => { stop(); document.removeEventListener('visibilitychange', onVisible) })

  return { enabled, refresh: tick, start, stop }
}
