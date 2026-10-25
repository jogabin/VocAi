import { ref, computed } from 'vue'
import { fetchUsers, fetchUser } from '../api/userApi'

export function useUsers(pageSize = 10) {
  /* ---------- 목록 ---------- */
  const users = ref([])
  const loading = ref(false)
  const error = ref('')
  const searched = ref(false) // 한 번이라도 조회했는지
  const page = ref(0)
  const filter = ref({ email: '', name: '' })

  const hasPrev = computed(() => page.value > 0)
  // 받은 건수가 페이지 크기와 같으면 다음 페이지가 있을 수 있다고 판단
  const hasNext = computed(() => users.value.length === pageSize)

  async function load() {
    loading.value = true
    error.value = ''
    try {
      users.value = await fetchUsers({
        email: filter.value.email.trim(),
        name: filter.value.name.trim(),
        limit: pageSize,
        offset: page.value * pageSize,
      })
      searched.value = true
    } catch (e) {
      users.value = []
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  function search() {
    page.value = 0 // 새 검색은 첫 페이지부터
    return load()
  }

  function movePage(delta) {
    page.value += delta
    return load()
  }

  /* ---------- 단건 ---------- */
  const userId = ref('')
  const user = ref(null)
  const userError = ref('')

  async function loadUser() {
    userError.value = ''
    user.value = null
    if (!userId.value) return
    try {
      user.value = await fetchUser(userId.value)
    } catch (e) {
      userError.value = e.message
    }
  }

  return {
    // 목록
    users, loading, error, searched, page, filter,
    hasPrev, hasNext, search, movePage,
    // 단건
    userId, user, userError, loadUser,
  }
}