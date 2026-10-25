<script setup>
import { useUsers } from '../composables/useUsers'

const {
  users, loading, error, searched, page, filter,
  hasPrev, hasNext, search, movePage,
  userId, user, userError, loadUser,
} = useUsers(10)

function selectUser(id) {
  userId.value = id
  loadUser()
}

</script>


<template>
  <!-- 목록 조회 -->
  <section>
    <h2>2. Users 목록 조회</h2>
    <div class="row">
      <input v-model="filter.email" placeholder="이메일 (정확히 일치)" @keyup.enter="search" />
      <input v-model="filter.name" placeholder="이름 (포함 검색)" @keyup.enter="search" />
      <button @click="search" :disabled="loading">조회</button>
    </div>

    <p v-if="loading">불러오는 중...</p>
    <p v-if="error" class="err">{{ error }}</p>

    <table v-if="users.length">
      <thead>
        <tr><th>user_id</th><th>name</th><th>email</th></tr>
      </thead>
      <tbody>
        <tr v-for="u in users" :key="u.user_id">
          <td>
            <a href="#" @click.prevent="selectUser(u.user_id)">
              {{ u.user_id }}
            </a>
          </td>
          <td>{{ u.username }}</td>
          <td>{{ u.email }}</td>
        </tr>
      </tbody>
    </table>
    <p v-else-if="searched && !loading && !error">조회 결과가 없습니다.</p>

    <div v-if="searched" class="row">
      <button @click="movePage(-1)" :disabled="!hasPrev || loading">이전</button>
      <span>{{ page + 1 }} 페이지</span>
      <button @click="movePage(1)" :disabled="!hasNext || loading">다음</button>
    </div>
  </section>

  <!-- 단건 조회 -->
  <section>
    <h2>3. User 단건 조회</h2>
    <div class="row">
      <input v-model="userId" type="text" placeholder="user_id" @keyup.enter="loadUser" />
      <button @click="loadUser">조회</button>
    </div>
    <pre v-if="user">{{ user }}</pre>
    <p v-if="userError" class="err">{{ userError }}</p>
  </section>
</template>